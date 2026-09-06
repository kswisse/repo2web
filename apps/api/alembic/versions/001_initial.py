"""Initial migration

Revision ID: 001_initial
Revises:
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("url", sa.String(500), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(100), nullable=False, server_default="main"),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "repository_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), nullable=False, index=True),
        sa.Column("commit_sha", sa.String(40), nullable=False, index=True),
        sa.Column("branch", sa.String(100), nullable=False),
        sa.Column("cloned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("repository_snapshots.id"), unique=True, nullable=False, index=True),
        sa.Column("detected_languages", sa.JSON(), nullable=False),
        sa.Column("framework", sa.String(100), nullable=True),
        sa.Column("package_manager", sa.String(100), nullable=True),
        sa.Column("entrypoint", sa.String(500), nullable=True),
        sa.Column("install_command", sa.String(500), nullable=True),
        sa.Column("build_command", sa.String(500), nullable=True),
        sa.Column("run_command", sa.String(500), nullable=True),
        sa.Column("expected_port", sa.Integer(), nullable=True),
        sa.Column("environment_variables", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("unsupported_requirements", sa.JSON(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "execution_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("analysis_results.id"), unique=True, nullable=False, index=True),
        sa.Column("runtime", sa.String(50), nullable=False, server_default="docker"),
        sa.Column("framework", sa.String(100), nullable=False),
        sa.Column("install_steps", sa.JSON(), nullable=False),
        sa.Column("build_steps", sa.JSON(), nullable=False),
        sa.Column("run_command", sa.String(500), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("environment", sa.JSON(), nullable=False),
        sa.Column("resource_requirements", sa.JSON(), nullable=False),
        sa.Column("network_requirements", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "deployments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repository_id", sa.String(36), sa.ForeignKey("repositories.id"), nullable=False, index=True),
        sa.Column("snapshot_id", sa.String(36), sa.ForeignKey("repository_snapshots.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("state", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "build_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("execution_plans.id"), nullable=False, index=True),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id"), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("container_id", sa.String(100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "build_steps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("build_job_id", sa.String(36), sa.ForeignKey("build_jobs.id"), nullable=False, index=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("command", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "build_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("build_step_id", sa.String(36), sa.ForeignKey("build_steps.id"), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
    )

    op.create_table(
        "runtime_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("build_job_id", sa.String(36), sa.ForeignKey("build_jobs.id"), unique=True, nullable=False, index=True),
        sa.Column("container_id", sa.String(100), nullable=False),
        sa.Column("internal_url", sa.String(500), nullable=False),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="starting"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "health_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("runtime_id", sa.String(36), sa.ForeignKey("runtime_instances.id"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id"), nullable=False, index=True),
        sa.Column("cpu_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("memory_mb_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("storage_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("network_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("health_checks")
    op.drop_table("runtime_instances")
    op.drop_table("build_logs")
    op.drop_table("build_steps")
    op.drop_table("build_jobs")
    op.drop_table("deployments")
    op.drop_table("execution_plans")
    op.drop_table("analysis_results")
    op.drop_table("repository_snapshots")
    op.drop_table("repositories")
    op.drop_table("users")
