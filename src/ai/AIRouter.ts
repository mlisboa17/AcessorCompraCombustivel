import { ProviderGroq } from "./providers/ProviderGroq";
import { ProviderCerebras } from "./providers/ProviderCerebras";
import { ProviderOpenRouter } from "./providers/ProviderOpenRouter";
import {
  AIContext,
  AIProvider,
  AIProviderError,
  AIProviderName,
  readOptionalNumberEnv,
} from "./types";

const FRIENDLY_AI_ERROR = "Serviço de IA temporariamente indisponível.";
const BACKOFF_MS = [300, 600, 1000];

export class AIRouter {
  private static readonly providers: Record<AIProviderName, AIProvider> = {
    Groq: new ProviderGroq(),
    Cerebras: new ProviderCerebras(),
    OpenRouter: new ProviderOpenRouter(),
  };

  static async handle(input: string, context?: AIContext): Promise<string> {
    const providerOrder = this.resolveProviderOrder();
    let lastError: unknown = null;

    for (const [index, provider] of providerOrder.entries()) {
      console.log(`[AI Service] Iniciando requisição com provedor: ${provider.name}`);

      try {
        return await this.runWithRetries(provider, input, context);
      } catch (error) {
        lastError = error;
        const nextProvider = providerOrder[index + 1];

        if (nextProvider) {
          console.error(
            `[AI Critical] ${provider.name} esgotou tentativas. Chaveando dinamicamente para Fallback ${index + 1}: ${nextProvider.name}`,
          );
        }
      }
    }

    console.error("[AI Critical] Todos os provedores falharam.", lastError);
    return FRIENDLY_AI_ERROR;
  }

  private static async runWithRetries(
    provider: AIProvider,
    input: string,
    context?: AIContext,
  ): Promise<string> {
    const maxAttempts = Math.min(Math.max(readOptionalNumberEnv("AI_PROVIDER_MAX_ATTEMPTS", 3), 2), 3);

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        return await provider.generateResponse(input, context);
      } catch (error) {
        const providerError = this.normalizeError(error, provider.name);
        const isLastAttempt = attempt === maxAttempts;

        if (!providerError.retryable || isLastAttempt) {
          throw providerError;
        }

        const statusText = providerError.statusCode ? `código ${providerError.statusCode}` : providerError.message;
        console.warn(
          `[AI Warning] ${provider.name} falhou com ${statusText}. Tentando novamente (Retry #${attempt})...`,
        );

        await this.sleep(BACKOFF_MS[attempt - 1] ?? BACKOFF_MS[BACKOFF_MS.length - 1]);
      }
    }

    throw new AIProviderError(`${provider.name} esgotou tentativas.`, provider.name, true);
  }

  private static normalizeError(error: unknown, providerName: string): AIProviderError {
    if (error instanceof AIProviderError) {
      return error;
    }

    return new AIProviderError(
      error instanceof Error ? error.message : "Erro desconhecido no provedor.",
      providerName,
      true,
    );
  }

  private static resolveProviderOrder(): AIProvider[] {
    const envOrder = [
      process.env.AI_PROVIDER_PRIMARY,
      process.env.AI_PROVIDER_FALLBACK_1,
      process.env.AI_PROVIDER_FALLBACK_2,
    ];
    const defaultOrder: AIProviderName[] = ["Groq", "Cerebras", "OpenRouter"];
    const selectedNames = envOrder
      .map((name, index) => this.normalizeProviderName(name) ?? defaultOrder[index])
      .filter((name): name is AIProviderName => Boolean(name));

    const uniqueNames = [...new Set(selectedNames)];
    return uniqueNames.map((name) => this.providers[name]);
  }

  private static normalizeProviderName(name?: string): AIProviderName | null {
    const normalized = (name || "").trim().toLowerCase();
    if (!normalized) return null;
    if (normalized === "groq") return "Groq";
    if (normalized === "cerebras") return "Cerebras";
    if (normalized === "openrouter" || normalized === "open-router") return "OpenRouter";
    return null;
  }

  private static sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
