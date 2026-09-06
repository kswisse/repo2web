"""Observability and resource accounting

Revision ID: 003_observability
Revises: 002_async_deployment
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_observability"
down_revision: Union[str, None] = "002_async_deployment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create deployment_metrics table
    op.create_table(
        "deployment_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "deployment_id",
            sa.String(36),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cpu_usage_percent", sa.Float(), nullable=True),
        sa.Column("memory_usage_bytes", sa.Integer(), nullable=True),
        sa.Column("memory_limit_bytes", sa.Integer(), nullable=True),
        sa.Column("memory_percent", sa.Float(), nullable=True),
        sa.Column("network_rx_bytes", sa.Integer(), nullable=True),
        sa.Column("network_tx_bytes", sa.Integer(), nullable=True),
        sa.Column("container_status", sa.String(50), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create deployment_health table
    op.create_table(
        "deployment_health",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "deployment_id",
            sa.String(36),
            sa.ForeignKey("deployments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column(
            "attempt_number", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_final", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Add health and observability columns to deployments table
    op.add_column(
        "deployments",
        sa.Column(
            "health_status", sa.String(20), nullable=True, server_default="pending"
        ),
    )
    op.add_column(
        "deployments",
        sa.Column("health_response_time_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "deployments",
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Remove health columns from deployments
    op.drop_column("deployments", "last_health_check_at")
    op.drop_column("deployments", "health_response_time_ms")
    op.drop_column("deployments", "health_status")

    # Drop observability tables
    op.drop_table("deployment_health")
    op.drop_table("deployment_metrics")
