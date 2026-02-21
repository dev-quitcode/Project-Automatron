"use client";

import { useState, useMemo } from "react";
import { cn } from "@/lib/utils";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { FileText, Edit3, Save, X, CheckCircle, Circle } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface PlanEditorProps {
  planMd: string | null;
  onSave?: (planMd: string) => void;
  readOnly?: boolean;
}

export function PlanEditor({
  planMd,
  onSave,
  readOnly = false,
}: PlanEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState("");

  // Parse progress from plan markdown
  const progress = useMemo(() => {
    if (!planMd) return { total: 0, completed: 0 };
    const allTasks = planMd.match(/- \[[ x]\]/g) || [];
    const done = planMd.match(/- \[x\]/gi) || [];
    return { total: allTasks.length, completed: done.length };
  }, [planMd]);

  const handleEdit = () => {
    setEditContent(planMd || "");
    setIsEditing(true);
  };

  const handleSave = () => {
    onSave?.(editContent);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditContent("");
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold">PLAN.md</h3>
        </div>
        <div className="flex items-center gap-2">
          {progress.total > 0 && (
            <ProgressBar
              total={progress.total}
              completed={progress.completed}
              className="w-32"
              showLabel={false}
            />
          )}
          {!readOnly && !isEditing && planMd && (
            <button
              onClick={handleEdit}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Edit3 className="h-3 w-3" />
              Edit
            </button>
          )}
          {isEditing && (
            <>
              <button
                onClick={handleSave}
                className="flex items-center gap-1.5 rounded-lg bg-green-600 px-2 py-1 text-xs text-white"
              >
                <Save className="h-3 w-3" />
                Save
              </button>
              <button
                onClick={handleCancel}
                className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
              >
                <X className="h-3 w-3" />
                Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {!planMd && !isEditing ? (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
            <FileText className="mb-3 h-10 w-10 opacity-30" />
            <p>No plan generated yet.</p>
            <p className="mt-1 text-xs">
              The Architect will create a plan when the project starts.
            </p>
          </div>
        ) : isEditing ? (
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="h-full w-full resize-none rounded-lg border border-input bg-background p-3 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-ring"
            spellCheck={false}
          />
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown
              components={{
                // Custom checkbox rendering
                li: ({ children, ...props }) => {
                  const text = String(children);
                  const isCheckbox = /^\s*\[[ x]\]/.test(text);
                  if (isCheckbox) {
                    const checked = /^\s*\[x\]/i.test(text);
                    return (
                      <li className="flex items-start gap-2 list-none" {...props}>
                        {checked ? (
                          <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                        ) : (
                          <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                        )}
                        <span className={checked ? "line-through opacity-60" : ""}>
                          {text.replace(/^\s*\[[ x]\]\s*/, "")}
                        </span>
                      </li>
                    );
                  }
                  return <li {...props}>{children}</li>;
                },
              }}
            >
              {planMd}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {/* Footer with progress */}
      {progress.total > 0 && (
        <div className="border-t border-border px-4 py-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {progress.completed}/{progress.total} tasks completed
            </span>
            <span>
              {Math.round((progress.completed / progress.total) * 100)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
