"use client";

import { useCallback, useEffect, useRef } from "react";
import {
  connectSocket,
  disconnectSocket,
  getSocket,
  joinProjectRoom,
  leaveProjectRoom,
} from "@/lib/socket";
import { useProjectStore } from "@/stores/projectStore";
import type {
  BuilderLog,
  ChatMessage,
  WsArchitectMessage,
  WsBuilderLog,
  WsHumanRequired,
  WsPlanUpdated,
  WsStatusUpdate,
} from "@/lib/types";

export function useWebSocket(projectId?: string) {
  const previousProjectId = useRef<string | null>(null);
  const {
    addBuilderLog,
    addChatMessage,
    patchProject,
    setConnected,
    setHumanRequired,
    setPlanMd,
    setProgress,
  } = useProjectStore();

  useEffect(() => {
    const socket = connectSocket();

    socket.on("connect", () => {
      setConnected(true);
      if (projectId) {
        joinProjectRoom(projectId);
      }
    });

    socket.on("disconnect", () => {
      setConnected(false);
    });

    socket.on("architect:message", (data: WsArchitectMessage) => {
      if (projectId && data.project_id !== projectId) {
        return;
      }
      if (data.is_streaming) {
        return;
      }
      const message: ChatMessage = {
        id: crypto.randomUUID(),
        project_id: data.project_id,
        role: "architect",
        content: data.content,
        timestamp: new Date().toISOString(),
      };
      addChatMessage(message);
    });

    socket.on("builder:log", (data: WsBuilderLog) => {
      if (projectId && data.project_id !== projectId) {
        return;
      }
      const log: BuilderLog = {
        project_id: data.project_id,
        task_index: data.task_index,
        task_text: data.task_text,
        status: data.status,
        output: data.output,
        error_detail: null,
        timestamp: new Date().toISOString(),
      };
      addBuilderLog(log);
    });

    socket.on("status:update", (data: WsStatusUpdate) => {
      patchProject(data.project_id, {
        status: data.status,
        project_stage: data.stage,
        preview_url: data.preview_url ?? null,
      });

      if (!projectId || data.project_id === projectId) {
        const total = data.progress?.total ?? 0;
        const completed = data.progress?.completed ?? 0;
        setProgress({
          total,
          completed,
          percentage: total > 0 ? Math.round((completed / total) * 100) : 0,
        });
      }
    });

    socket.on("human:required", (data: WsHumanRequired) => {
      if (!projectId || data.project_id === projectId) {
        setHumanRequired(true, data.reason, data.stage ?? null);
      }
      if (data.stage) {
        patchProject(data.project_id, { project_stage: data.stage });
      }
    });

    socket.on("plan:updated", (data: WsPlanUpdated) => {
      patchProject(data.project_id, { plan_md: data.plan_md });
      if (!projectId || data.project_id === projectId) {
        setPlanMd(data.plan_md);
      }
    });

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("architect:message");
      socket.off("builder:log");
      socket.off("status:update");
      socket.off("human:required");
      socket.off("plan:updated");
      disconnectSocket();
    };
  }, [
    addBuilderLog,
    addChatMessage,
    patchProject,
    projectId,
    setConnected,
    setHumanRequired,
    setPlanMd,
    setProgress,
  ]);

  useEffect(() => {
    if (previousProjectId.current && previousProjectId.current !== projectId) {
      leaveProjectRoom(previousProjectId.current);
    }

    if (projectId) {
      joinProjectRoom(projectId);
    }
    previousProjectId.current = projectId || null;

    return () => {
      if (projectId) {
        leaveProjectRoom(projectId);
      }
    };
  }, [projectId]);

  const sendMessage = useCallback(
    (message: string) => {
      if (!projectId) return;

      const socket = getSocket();
      socket.emit("chat:message", { project_id: projectId, message });

      const optimisticMessage: ChatMessage = {
        id: crypto.randomUUID(),
        project_id: projectId,
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };
      addChatMessage(optimisticMessage);
    },
    [addChatMessage, projectId]
  );

  return { sendMessage };
}
