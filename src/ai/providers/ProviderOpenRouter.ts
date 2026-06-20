import {
  AIContext,
  AIProvider,
  AIProviderError,
  buildMessages,
  isRetryableStatus,
  readOptionalNumberEnv,
  readRequiredEnv,
} from "../types";

export class ProviderOpenRouter implements AIProvider {
  public readonly name = "OpenRouter" as const;

  async generateResponse(input: string, context?: AIContext): Promise<string> {
    const apiUrl = readRequiredEnv("OPENROUTER_API_URL", this.name);
    const apiKey = readRequiredEnv("OPENROUTER_API_KEY", this.name);
    const model = process.env.OPENROUTER_MODEL || "meta-llama/llama-3.1-8b-instruct:free";

    const response = await this.postJson(apiUrl, apiKey, {
      model,
      messages: buildMessages(input, context),
      temperature: context?.temperature ?? 0.2,
      max_tokens: context?.maxTokens ?? readOptionalNumberEnv("AI_MAX_TOKENS", 700),
    });

    const content = response?.choices?.[0]?.message?.content;
    if (!content || typeof content !== "string") {
      throw new AIProviderError("Resposta invalida recebida do OpenRouter.", this.name, false);
    }

    return content.trim();
  }

  private async postJson(apiUrl: string, apiKey: string, body: unknown): Promise<any> {
    const timeoutMs = readOptionalNumberEnv("AI_PROVIDER_TIMEOUT_MS", 7000);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": process.env.OPENROUTER_SITE_URL || "https://fuelguard360.streamlit.app",
          "X-Title": process.env.OPENROUTER_APP_NAME || "FuelGuard360",
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new AIProviderError(
          `OpenRouter falhou com HTTP ${response.status}.`,
          this.name,
          isRetryableStatus(response.status),
          response.status,
        );
      }

      return response.json();
    } catch (error) {
      if (error instanceof AIProviderError) throw error;
      const isTimeout = error instanceof Error && error.name === "AbortError";
      throw new AIProviderError(
        isTimeout ? "Timeout ao chamar OpenRouter." : "Falha de rede ao chamar OpenRouter.",
        this.name,
        true,
      );
    } finally {
      clearTimeout(timeout);
    }
  }
}
