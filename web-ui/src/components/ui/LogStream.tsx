"use client";

import { useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import type { BuilderLog } from "@/lib/types";

interface LogStreamProps {
  logs: BuilderLog[];
  className?: string;
  maxHeight?: string;
}

export function LogStream({
  logs,
  className,
  maxHeight = "400px",
}: LogStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border border-border bg-card p-8 text-sm text-muted-foreground",
          className
        )}
      >
        No builder logs yet. Start the project to see activity.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "log-stream overflow-auto rounded-lg border border-border bg-card p-4",
        className
      )}
      style={{ maxHeight }}
    >
      {logs.map((log, i) => (
        <div key={i} className="mb-3 last:mb-0">
          {/* Task header */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground">
              Task #{log.task_index}
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-medium",
                log.status === "SUCCESS"
                  ? "bg-green-500/10 text-green-500"
                  : log.status === "BLOCKER"
                  ? "bg-red-500/10 text-red-500"
                  : "bg-amber-500/10 text-amber-500"
              )}
            >
              {log.status}
            </span>
            <span className="text-muted-foreground/60">{log.task_text}</span>
          </div>
          {/* Output */}
          {log.output && (
            <pre className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">
              {log.output.slice(-2000)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
