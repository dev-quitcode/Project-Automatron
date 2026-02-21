"use client";

import { useEffect, useRef, useCallback } from "react";
import { getSocket, connectSocket, disconnectSocket, joinProjectRoom, leaveProjectRoom } from "@/lib/socket";
import { useProjectStore } from "@/stores/projectStore";
import type {
  WsArchitectMessage,
  WsBuilderLog,
  WsStatusUpdate,
  WsHumanRequired,
  WsPlanUpdated,
  ChatMessage,
  BuilderLog,
} from "@/lib/types";

export function useWebSocket(projectId?: string) {
  const prevProjectId = useRef<string | null>(null);
  const {
    setConnected,
    addChatMessage,
    addBuilderLog,
    updateProjectStatus,
    setHumanRequired,
    setPlanMd,
  } = useProjectStore();

  // Connect & bind global listeners
  useEffect(() => {
    const socket = connectSocket();

    socket.on("connect", () => {
      setConnected(true);
      // Rejoin room if we reconnect
      if (projectId) {
        joinProjectRoom(projectId);
      }
    });

    socket.on("disconnect", () => {
      setConnected(false);
    });

    // ── Architect streaming message ───────────────────────
    socket.on("architect:message", (data: WsArchitectMessage) => {
      if (!data.is_streaming) {
        const msg: ChatMessage = {
          id: crypto.randomUUID(),
          project_id: data.project_id,
          role: "architect",
          content: data.content,
          timestamp: new Date().toISOString(),
        };
        addChatMessage(msg);
      }
    });

    // ── Builder log ───────────────────────────────────────
    socket.on("builder:log", (data: WsBuilderLog) => {
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

    // ── Status update ─────────────────────────────────────
    socket.on("status:update", (data: WsStatusUpdate) => {
      updateProjectStatus(data.project_id, data.status);
    });

    // ── Human intervention required ───────────────────────
    socket.on("human:required", (data: WsHumanRequired) => {
      setHumanRequired(true, data.reason);
    });

    // ── Plan updated ──────────────────────────────────────
    socket.on("plan:updated", (data: WsPlanUpdated) => {
      setPlanMd(data.plan_md);
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
  }, []);

  // Join/leave project rooms
  useEffect(() => {
    if (prevProjectId.current && prevProjectId.current !== projectId) {
      leaveProjectRoom(prevProjectId.current);
    }
    if (projectId) {
      joinProjectRoom(projectId);
    }
    prevProjectId.current = projectId || null;

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

      // Optimistic local add
      const msg: ChatMessage = {
        id: crypto.randomUUID(),
        project_id: projectId,
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };
      addChatMessage(msg);
    },
    [projectId, addChatMessage]
  );

  return { sendMessage };
}
