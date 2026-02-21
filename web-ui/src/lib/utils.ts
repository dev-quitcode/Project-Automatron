import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + "...";
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    pending: "text-muted-foreground",
    planning: "text-blue-500",
    building: "text-amber-500",
    reviewing: "text-purple-500",
    paused: "text-yellow-500",
    frozen: "text-red-500",
    completed: "text-green-500",
    error: "text-destructive",
  };
  return colors[status] || "text-muted-foreground";
}

export function getStatusBgColor(status: string): string {
  const colors: Record<string, string> = {
    pending: "bg-muted",
    planning: "bg-blue-500/10",
    building: "bg-amber-500/10",
    reviewing: "bg-purple-500/10",
    paused: "bg-yellow-500/10",
    frozen: "bg-red-500/10",
    completed: "bg-green-500/10",
    error: "bg-destructive/10",
  };
  return colors[status] || "bg-muted";
}
