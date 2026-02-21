"use client";

import { useProjectStore } from "@/stores/projectStore";
import { cn } from "@/lib/utils";
import { Wifi, WifiOff, AlertTriangle } from "lucide-react";

export function Header() {
  const { isConnected, currentProject, humanRequired, humanReason, error } =
    useProjectStore();

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-6">
      {/* Left: Project name or page title */}
      <div className="flex items-center gap-3">
        {currentProject ? (
          <>
            <h1 className="text-lg font-semibold">{currentProject.name}</h1>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium capitalize",
                currentProject.status === "completed"
                  ? "bg-green-500/10 text-green-500"
                  : currentProject.status === "error" ||
                    currentProject.status === "frozen"
                  ? "bg-destructive/10 text-destructive"
                  : currentProject.status === "building"
                  ? "bg-amber-500/10 text-amber-500"
                  : "bg-primary/10 text-primary"
              )}
            >
              {currentProject.status}
            </span>
          </>
        ) : (
          <h1 className="text-lg font-semibold">Dashboard</h1>
        )}
      </div>

      {/* Right: Status indicators */}
      <div className="flex items-center gap-4">
        {/* Human intervention alert */}
        {humanRequired && (
          <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 px-3 py-1.5 text-sm text-amber-500">
            <AlertTriangle className="h-4 w-4" />
            <span>{humanReason || "Action required"}</span>
          </div>
        )}

        {/* Error indicator */}
        {error && (
          <div className="max-w-xs truncate rounded-lg bg-destructive/10 px-3 py-1.5 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Connection status */}
        <div
          className={cn(
            "flex items-center gap-1.5 text-xs",
            isConnected ? "text-green-500" : "text-muted-foreground"
          )}
        >
          {isConnected ? (
            <Wifi className="h-3.5 w-3.5" />
          ) : (
            <WifiOff className="h-3.5 w-3.5" />
          )}
          <span>{isConnected ? "Connected" : "Disconnected"}</span>
        </div>
      </div>
    </header>
  );
}
