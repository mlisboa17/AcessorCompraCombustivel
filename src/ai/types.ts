export type AIProviderName = "Groq" | "Cerebras" | "OpenRouter";

export interface AIProvider {
  name: AIProviderName;
  generateResponse(input: string, context?: any): Promise<string>;
}

export interface AIContext {
  systemPrompt?: string;
  userId?: string;
  metadata?: Record<string, unknown>;
  temperature?: number;
  maxTokens?: number;
}

export interface ProviderRequestOptions {
  timeoutMs: number;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export class AIProviderError extends Error {
  public readonly provider: string;
  public readonly statusCode?: number;
  public readonly retryable: boolean;

  constructor(message: string, provider: string, retryable: boolean, statusCode?: number) {
    super(message);
    this.name = "AIProviderError";
    this.provider = provider;
    this.retryable = retryable;
    this.statusCode = statusCode;
  }
}

export function buildMessages(input: string, context?: AIContext): ChatMessage[] {
  const messages: ChatMessage[] = [];

  if (context?.systemPrompt) {
    messages.push({ role: "system", content: context.systemPrompt });
  }

  messages.push({ role: "user", content: input });
  return messages;
}

export function isRetryableStatus(statusCode: number): boolean {
  return statusCode === 429 || statusCode >= 500;
}

export function readRequiredEnv(key: string, provider: string): string {
  const value = process.env[key];
  if (!value) {
    throw new AIProviderError(`Variavel de ambiente ausente: ${key}`, provider, false);
  }
  return value;
}

export function readOptionalNumberEnv(key: string, fallback: number): number {
  const value = Number(process.env[key]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}
