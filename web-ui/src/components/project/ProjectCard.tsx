"use client";

import Link from "next/link";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatDate } from "@/lib/utils";
import type { Project } from "@/lib/types";
import { ArrowRight, Trash2 } from "lucide-react";

interface ProjectCardProps {
  project: Project;
  onDelete?: (id: string) => void;
}

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  return (
    <div className="group relative rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/30">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h3 className="font-semibold">{project.name}</h3>
          <p className="text-sm text-muted-foreground line-clamp-3">
            {project.description}
          </p>
          <div className="flex flex-wrap gap-2 pt-1 text-xs text-muted-foreground">
            <span className="rounded-full bg-muted px-2 py-0.5">
              {project.intake_source}
            </span>
            <span className="rounded-full bg-muted px-2 py-0.5">
              {project.project_stage.replace(/_/g, " ")}
            </span>
            {project.feature_branch && (
              <span className="rounded-full bg-muted px-2 py-0.5">
                {project.feature_branch}
              </span>
            )}
          </div>
        </div>
        <StatusBadge status={project.status} />
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          Created {formatDate(project.created_at)}
          {project.preview_url ? " • preview ready" : ""}
        </span>
        <div className="flex items-center gap-2">
          {onDelete && (
            <button
              onClick={(event) => {
                event.preventDefault();
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
