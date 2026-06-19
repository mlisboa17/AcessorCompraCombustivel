import { AIRouter } from "./AIRouter";
import { AIContext } from "./types";

export class AIService {
  async generate(input: string, context?: AIContext): Promise<string> {
    return AIRouter.handle(input, context);
  }
}

export const aiService = new AIService();
