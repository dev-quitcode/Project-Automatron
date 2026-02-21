"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, X, CheckCircle, Send } from "lucide-react";

interface AlertPanelProps {
  reason: string;
  context?: string;
  onApprove: (feedback?: string) => void;
  onDismiss?: () => void;
}

export function AlertPanel({
  reason,
  context,
  onApprove,
  onDismiss,
}: AlertPanelProps) {
  const [feedback, setFeedback] = useState("");

  return (
    <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2 text-amber-500">
          <AlertTriangle className="h-5 w-5" />
          <h3 className="font-semibold">Human Review Required</h3>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Reason */}
      <p className="mt-2 text-sm text-foreground">{reason}</p>

      {/* Context */}
      {context && (
        <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs text-muted-foreground">
          {context}
        </pre>
      )}

      {/* Feedback input */}
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          placeholder="Optional feedback or instructions..."
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onApprove(feedback || undefined);
          }}
          className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          onClick={() => onApprove(feedback || undefined)}
          className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700"
        >
          <CheckCircle className="h-4 w-4" />
          Approve & Continue
        </button>
      </div>
    </div>
  );
}
