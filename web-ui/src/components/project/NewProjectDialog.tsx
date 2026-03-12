"use client";

import { useEffect, useState } from "react";
import * as api from "@/lib/api";
import {
  cloneProjectLlmConfig,
  defaultProjectLlmConfig,
  llmProviders,
} from "@/lib/llmOptions";
import type {
  LlmProvider,
  ProjectLlmConfig,
  ProviderModelCatalog,
} from "@/lib/types";
import { useProjectStore } from "@/stores/projectStore";
import { X } from "lucide-react";

interface NewProjectDialogProps {
  open: boolean;
  onClose: () => void;
}

export function NewProjectDialog({ open, onClose }: NewProjectDialogProps) {
  const [name, setName] = useState("");
  const [intakeText, setIntakeText] = useState("");
  const [llmConfig, setLlmConfig] = useState<ProjectLlmConfig>(
    cloneProjectLlmConfig(defaultProjectLlmConfig)
  );
  const [providerCatalogs, setProviderCatalogs] = useState<
    Partial<Record<LlmProvider, ProviderModelCatalog>>
  >({});
  const [loadingProviders, setLoadingProviders] = useState<
    Partial<Record<LlmProvider, boolean>>
  >({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { createProject } = useProjectStore();

  if (!open) return null;

  const loadProviderCatalog = async (
    provider: LlmProvider,
    forceRefresh = false
  ): Promise<ProviderModelCatalog | null> => {
    if (!forceRefresh && providerCatalogs[provider]) {
      return providerCatalogs[provider] ?? null;
    }

    setLoadingProviders((current) => ({ ...current, [provider]: true }));
    try {
      const catalog = await api.getProviderModels(provider, forceRefresh);
      setProviderCatalogs((current) => ({ ...current, [provider]: catalog }));
      return catalog;
    } catch {
      return null;
    } finally {
      setLoadingProviders((current) => ({ ...current, [provider]: false }));
    }
  };

  useEffect(() => {
    if (!open) {
      return;
    }
    const providers = new Set<LlmProvider>(
      Object.values(llmConfig).map((config) => config.provider)
    );
    providers.forEach((provider) => {
      void loadProviderCatalog(provider);
    });
  }, [open]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !intakeText.trim()) return;

    setIsSubmitting(true);
    try {
      await createProject(name.trim(), intakeText.trim(), llmConfig);
      setName("");
      setIntakeText("");
      setLlmConfig(cloneProjectLlmConfig(defaultProjectLlmConfig));
      onClose();
    } catch {
      // Error is handled in the store.
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateRoleProvider = async (
    role: keyof ProjectLlmConfig,
    provider: LlmProvider
  ) => {
    setLlmConfig((current) => ({
      ...current,
      [role]: {
        provider,
        model: "",
      },
    }));
    const catalog = await loadProviderCatalog(provider);
    setLlmConfig((current) => ({
      ...current,
      [role]: {
        provider,
        model: catalog?.models[0]?.id ?? "",
      },
    }));
  };

  const modelOptionsFor = (provider: LlmProvider) =>
    providerCatalogs[provider]?.models ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-2xl">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">New Project</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Paste raw Solomon intake. Automatron will turn it into a
              technical implementation plan.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium">
              Project Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g., Client onboarding portal"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium">
              Solomon Intake
            </label>
            <textarea
              value={intakeText}
              onChange={(event) => setIntakeText(event.target.value)}
              placeholder="Describe the MVP, actors, flows, constraints, and the outcome you want to demo."
              rows={9}
              className="w-full resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="rounded-xl border border-border bg-background/60 p-4">
            <div>
              <h3 className="text-sm font-semibold">LLM Configuration</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Select provider and model for planning, building, and review.
              </p>
            </div>

            <div className="mt-4 space-y-4">
              {(["architect", "builder", "reviewer"] as const).map((role) => (
                <div key={role} className="grid gap-3 md:grid-cols-[160px_1fr_1.3fr]">
                  <div className="self-center text-sm font-medium capitalize">{role}</div>

                  <label className="space-y-1 text-sm">
                    <span className="text-muted-foreground">Provider</span>
                    <select
                      value={llmConfig[role].provider}
                      onChange={(event) => {
                        const provider = event.target.value as LlmProvider;
                        void updateRoleProvider(role, provider);
                      }}
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                    >
                      {llmProviders.map((provider) => (
                        <option key={provider.value} value={provider.value}>
                          {provider.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="space-y-1 text-sm">
                    <span className="text-muted-foreground">Model</span>
                    <select
                      value={llmConfig[role].model}
                      onChange={(event) =>
                        setLlmConfig((current) => ({
                          ...current,
                          [role]: {
                            ...current[role],
                            model: event.target.value,
                          },
                        }))
                      }
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                      disabled={loadingProviders[llmConfig[role].provider]}
                    >
                      <option value="">
                        {loadingProviders[llmConfig[role].provider]
                          ? "Loading models..."
                          : modelOptionsFor(llmConfig[role].provider).length > 0
                          ? "Select model"
                          : "No models available"}
                      </option>
                      {modelOptionsFor(llmConfig[role].provider).map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.label}
                        </option>
                      ))}
                    </select>
                    {providerCatalogs[llmConfig[role].provider]?.error && (
                      <p className="text-xs text-amber-500">
                        {providerCatalogs[llmConfig[role].provider]?.error}
                      </p>
                    )}
                  </label>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || !intakeText.trim() || isSubmitting}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              {isSubmitting ? "Creating..." : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
