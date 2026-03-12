"""Tests for repository manager helpers."""

from __future__ import annotations

from orchestrator.repository.manager import RepositoryManager


def test_create_feature_branch_name_slugifies_project_name():
    manager = RepositoryManager()

    branch = manager.create_feature_branch_name("Client Portal MVP", run_seq=3)

    assert branch == "feature/3-client-portal-mvp"


def test_validate_deploy_artifacts_reports_missing_files(tmp_path):
    manager = RepositoryManager()
    manager.workspace_root = tmp_path

    result = manager.validate_deploy_artifacts("project-1")

    codes = {issue.code for issue in result.blocking_issues}
    assert not result.ok
    assert "artifact_dockerfile_missing" in codes
    assert "artifact_env_example_missing" in codes
    assert "artifact_deploy_compose_missing" in codes
    assert "artifact_deploy_md_missing" in codes
    assert "artifact_ci_workflow_missing" in codes
    assert "artifact_deploy_workflow_missing" in codes


def test_ensure_deploy_supporting_docs_creates_expected_files(tmp_path):
    manager = RepositoryManager()
    manager.workspace_root = tmp_path

    manager.ensure_deploy_supporting_docs("project-1", "Client Portal MVP")
    workspace = manager.workspace_path("project-1")

    assert (workspace / ".env.example").read_text(encoding="utf-8") == "APP_PORT=3000\n"
    assert "Client Portal MVP" in (workspace / "DEPLOY.md").read_text(encoding="utf-8")
    assert (workspace / "deploy" / "docker-compose.yml").exists()
    assert (workspace / ".github" / "workflows" / "ci.yml").exists()
    assert (workspace / ".github" / "workflows" / "deploy.yml").exists()


def test_validate_deploy_artifacts_checks_file_shapes(tmp_path):
    manager = RepositoryManager()
    manager.workspace_root = tmp_path
    workspace = manager.workspace_path("project-1")
    (workspace / "deploy").mkdir(parents=True, exist_ok=True)
    (workspace / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    (workspace / "Dockerfile").write_text("FROM node:22\n", encoding="utf-8")
    (workspace / ".env.example").write_text("# empty\n", encoding="utf-8")
    (workspace / "deploy" / "docker-compose.yml").write_text("services:\n  worker:\n    image: app\n", encoding="utf-8")
    (workspace / "DEPLOY.md").write_text("No deploy command here\n", encoding="utf-8")
    (workspace / ".github" / "workflows" / "ci.yml").write_text("name: CI\non: push\n", encoding="utf-8")
    (workspace / ".github" / "workflows" / "deploy.yml").write_text("name: Deploy\n", encoding="utf-8")

    result = manager.validate_deploy_artifacts("project-1")
    codes = {issue.code for issue in result.blocking_issues}

    assert "artifact_dockerfile_entrypoint_missing" in codes
    assert "artifact_env_example_invalid" in codes
    assert "artifact_deploy_compose_missing_app" in codes
    assert "artifact_deploy_md_command_missing" in codes
    assert "artifact_ci_workflow_branches_missing" in codes
    assert "artifact_deploy_workflow_main_missing" in codes
