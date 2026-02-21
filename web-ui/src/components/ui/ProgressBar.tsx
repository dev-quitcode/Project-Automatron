"use client";

import { cn } from "@/lib/utils";

interface ProgressBarProps {
  total: number;
  completed: number;
  className?: string;
  showLabel?: boolean;
}

export function ProgressBar({
  total,
  completed,
  className,
  showLabel = true,
}: ProgressBarProps) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className={cn("space-y-1.5", className)}>
      {showLabel && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {completed} / {total} tasks
          </span>
          <span>{percentage}%</span>
        </div>
      )}
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            percentage === 100
              ? "bg-green-500"
              : percentage > 50
              ? "bg-primary"
              : "bg-amber-500"
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
