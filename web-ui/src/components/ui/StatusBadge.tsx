"use client";

import { cn, getStatusColor, getStatusBgColor } from "@/lib/utils";
import type { ProjectStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: ProjectStatus;
  size?: "sm" | "md";
  pulse?: boolean;
}

const activeStatuses: ProjectStatus[] = ["planning", "building", "reviewing"];

export function StatusBadge({
  status,
  size = "sm",
  pulse = true,
}: StatusBadgeProps) {
  const isActive = activeStatuses.includes(status);

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium capitalize",
        getStatusBgColor(status),
        getStatusColor(status),
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"
      )}
    >
      {pulse && isActive && (
        <span className="relative flex h-2 w-2">
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              status === "planning"
                ? "bg-blue-400"
                : status === "building"
                ? "bg-amber-400"
                : "bg-purple-400"
            )}
          />
          <span
            className={cn(
              "relative inline-flex h-2 w-2 rounded-full",
              status === "planning"
                ? "bg-blue-500"
                : status === "building"
                ? "bg-amber-500"
                : "bg-purple-500"
            )}
          />
        </span>
      )}
      {status}
    </span>
  );
}
