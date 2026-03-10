"""Tests for deployment command generation and failure handling."""

from __future__ import annotations

import subprocess

from orchestrator.deployment.manager import DeploymentManager


def test_build_remote_command_contains_clone_pull_and_compose():
    manager = DeploymentManager()

    command = manager.build_remote_command(
        "https://example.com/repo.git",
        "/srv/app",
        "main",
    )

    assert "git clone --branch main" in command
    assert "git fetch origin" in command
    assert "git pull origin main" in command
    assert "docker compose -f deploy/docker-compose.yml up -d --build" in command


def test_deploy_skips_health_check_when_ssh_command_fails(monkeypatch):
    manager = DeploymentManager()

    def fake_ssh_command(host: str, user: str, port: int, command: str):
        return subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout="stdout",
            stderr="stderr",
        )

    def fail_health_check(target):
        raise AssertionError("health check should not run on failed ssh deploy")

    monkeypatch.setattr(manager, "_run_ssh_command", fake_ssh_command)
    monkeypatch.setattr(manager, "_health_check", fail_health_check)

    result = manager.deploy(
        "https://example.com/repo.git",
        {"host": "example.com", "user": "deploy", "deploy_path": "/srv/app"},
        branch="main",
    )

    assert result.status == "failed"
    assert "stderr" in result.output
