"""Deployment manager for client VPS rollout over SSH."""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from orchestrator.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    status: str
    output: str
    branch: str


class DeploymentManager:
    """Runs remote git/docker-compose deployment commands over SSH."""

    def deploy(
        self,
        repo_clone_url: str,
        target: dict[str, Any],
        branch: str = "main",
    ) -> DeployResult:
        host = target.get("host")
        user = target.get("user")
        deploy_path = target.get("deploy_path")
        if not host or not user or not deploy_path:
            raise RuntimeError("Deploy target must include host, user, and deploy_path")

        clone_url = self._authenticated_clone_url(repo_clone_url)
        remote_command = self.build_remote_command(clone_url, str(deploy_path), branch)
        completed = self._run_ssh_command(
            str(host),
            str(user),
            int(target.get("port", 22) or 22),
            remote_command,
        )

        status = "deployed" if completed.returncode == 0 else "failed"
        output = completed.stdout + ("\n--- STDERR ---\n" + completed.stderr if completed.stderr else "")
        if status == "deployed":
            self._health_check(target)
        return DeployResult(status=status, output=output, branch=branch)

    def build_remote_command(self, clone_url: str, deploy_path: str, branch: str) -> str:
        quoted_path = shlex.quote(deploy_path)
        quoted_repo = shlex.quote(clone_url)
        quoted_branch = shlex.quote(branch)
        return (
            f"mkdir -p {quoted_path} && "
            f"if [ ! -d {quoted_path}/.git ]; then "
            f"git clone --branch {quoted_branch} {quoted_repo} {quoted_path}; "
            f"fi && "
            f"cd {quoted_path} && "
            f"git fetch origin && "
            f"git checkout {quoted_branch} && "
            f"git pull origin {quoted_branch} && "
            f"docker compose -f deploy/docker-compose.yml up -d --build"
        )

    def _run_ssh_command(
        self,
        host: str,
        user: str,
        port: int,
        command: str,
    ) -> subprocess.CompletedProcess[str]:
        ssh_command = ["ssh", "-p", str(port), "-o", "StrictHostKeyChecking=no"]
        if settings.deploy_ssh_key_path:
            ssh_command.extend(["-i", str(Path(settings.deploy_ssh_key_path))])
        if settings.deploy_ssh_options:
            ssh_command.extend(shlex.split(settings.deploy_ssh_options))
        ssh_command.append(f"{user}@{host}")
        ssh_command.append(command)

        return subprocess.run(
            ssh_command,
            text=True,
            capture_output=True,
            check=False,
        )

    def _authenticated_clone_url(self, repo_clone_url: str) -> str:
        if not settings.github_token or "https://" not in repo_clone_url:
            return repo_clone_url
        return repo_clone_url.replace(
            "https://",
            f"https://x-access-token:{settings.github_token}@",
            1,
        )

    def _health_check(self, target: dict[str, Any]) -> None:
        app_url = target.get("app_url")
        if not app_url:
            return

        health_path = str(target.get("health_path", "") or "")
        url = str(app_url).rstrip("/")
        if health_path:
            url += health_path if health_path.startswith("/") else f"/{health_path}"

        try:
            response = httpx.get(url, timeout=10)
            if response.status_code >= 400:
                raise RuntimeError(f"Health check failed: {response.status_code} {response.text[:200]}")
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Health check failed for {url}: {exc}") from exc
