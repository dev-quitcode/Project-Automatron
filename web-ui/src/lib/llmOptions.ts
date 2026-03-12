import type { LlmProvider, ProjectLlmConfig } from "./types";

export const llmProviders: { value: LlmProvider; label: string }[] = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google" },
];

export const defaultProjectLlmConfig: ProjectLlmConfig = {
  architect: {
    provider: "openai",
    model: "gpt-4.1",
  },
  builder: {
    provider: "openai",
    model: "gpt-4.1-mini",
  },
  reviewer: {
    provider: "openai",
    model: "gpt-4.1-mini",
  },
};

export function cloneProjectLlmConfig(config: ProjectLlmConfig): ProjectLlmConfig {
  return {
    architect: { ...config.architect },
    builder: { ...config.builder },
    reviewer: { ...config.reviewer },
  };
}
