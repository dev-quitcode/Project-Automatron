"use client";

import Link from "next/link";
import { cn, formatDate } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ArrowRight, Trash2 } from "lucide-react";
import type { Project } from "@/lib/types";

interface ProjectCardProps {
  project: Project;
  onDelete?: (id: string) => void;
}

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  return (
    <div className="group relative rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/30">
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <h3 className="font-semibold">{project.name}</h3>
          <p className="text-sm text-muted-foreground line-clamp-2">
            {project.description}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      {/* Meta row */}
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>Created {formatDate(project.created_at)}</span>
        <div className="flex items-center gap-2">
          {onDelete && (
            <button
              onClick={(e) => {
                e.preventDefault();
                onDelete(project.id);
              }}
              className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
          <Link
            href={`/project/${project.id}`}
            className="flex items-center gap-1 text-primary hover:underline"
          >
            Open
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    </div>
  );
}
