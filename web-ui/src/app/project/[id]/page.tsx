"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppLayout } from "@/components/layout";
import { ChatPanel } from "@/components/project/ChatPanel";
import { PlanEditor } from "@/components/project/PlanEditor";
import { AlertPanel, LogStream } from "@/components/ui";
import { useProjectStore } from "@/stores/projectStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  Play,
  Square,
  ArrowLeft,
  ExternalLink,
  RotateCcw,
} from "lucide-react";
import { getPreviewUrl } from "@/lib/api";

type ActiveTab = "chat" | "plan" | "logs";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const {
    currentProject,
    chatMessages,
    builderLogs,
    planMd,
    humanRequired,
    humanReason,
    isLoading,
    fetchProject,
    fetchChatHistory,
    fetchPlan,
    startProject,
    stopProject,
    approveProject,
    updatePlan,
    clearBuilderLogs,
    setHumanRequired,
  } = useProjectStore();

  // WebSocket connection for this project
  const { sendMessage } = useWebSocket(projectId);

  // Load project data
  useEffect(() => {
    if (projectId) {
      fetchProject(projectId);
      fetchChatHistory(projectId);
      fetchPlan(projectId);
      clearBuilderLogs();

      // Check for preview URL
      getPreviewUrl(projectId)
        .then((res) => setPreviewUrl(res.url))
        .catch(() => {});
    }
  }, [projectId]);

  const handleStart = () => startProject(projectId);
  const handleStop = () => stopProject(projectId);
  const handleApprove = (feedback?: string) => approveProject(projectId, feedback);
  const handleSavePlan = (md: string) => updatePlan(projectId, md);

  const isActive = ["planning", "building", "reviewing"].includes(
    currentProject?.status || ""
  );

  if (isLoading && !currentProject) {
    return (
      <AppLayout>
        <div className="flex h-full items-center justify-center text-muted-foreground">
          Loading project...
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      {/* Top bar */}
      <div className="mb-4 flex items-center justify-between">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to projects
        </button>

        <div className="flex items-center gap-2">
          {/* Preview link */}
          {previewUrl && (
            <a
              href={previewUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Preview
            </a>
          )}

          {/* Control buttons */}
          {!isActive && currentProject?.status !== "completed" && (
            <button
              onClick={handleStart}
              className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
            >
              <Play className="h-4 w-4" />
              {currentProject?.status === "pending" ? "Start" : "Resume"}
            </button>
          )}
          {isActive && (
            <button
              onClick={handleStop}
              className="flex items-center gap-2 rounded-lg bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90"
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Human intervention alert */}
      {humanRequired && (
        <div className="mb-4">
          <AlertPanel
            reason={humanReason || "The system needs your review before continuing."}
            onApprove={handleApprove}
            onDismiss={() => setHumanRequired(false)}
          />
        </div>
      )}

      {/* Tab bar */}
      <div className="mb-4 flex gap-1 rounded-lg border border-border bg-muted p-1">
        {(["chat", "plan", "logs"] as ActiveTab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab}
            {tab === "logs" && builderLogs.length > 0 && (
              <span className="ml-1.5 rounded-full bg-primary/10 px-1.5 py-0.5 text-xs text-primary">
                {builderLogs.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="h-[calc(100vh-16rem)]">
        {activeTab === "chat" && (
          <ChatPanel
            messages={chatMessages}
            onSendMessage={sendMessage}
            disabled={!isActive && currentProject?.status !== "paused"}
          />
        )}
        {activeTab === "plan" && (
          <PlanEditor
            planMd={planMd}
            onSave={handleSavePlan}
            readOnly={isActive}
          />
        )}
        {activeTab === "logs" && (
          <LogStream logs={builderLogs} maxHeight="100%" />
        )}
      </div>
    </AppLayout>
  );
}
