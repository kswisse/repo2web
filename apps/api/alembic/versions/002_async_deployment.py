"""Async deployment support

Revision ID: 002_async_deployment
Revises: 001_initial
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002_async_deployment"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create deployment_logs table
    op.create_table(
        "deployment_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deployment_id", sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("stage", sa.String(50), nullable=False, index=True),
        sa.Column("level", sa.String(20), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sequence", sa.Integer(), nullable=False),
    )
    
    # Add new columns to deployments table
    op.add_column("deployments", sa.Column("container_id", sa.String(100), nullable=True))
    op.add_column("deployments", sa.Column("build_container_id", sa.String(100), nullable=True))
    op.add_column("deployments", sa.Column("snapshot_path", sa.String(500), nullable=True))
    op.add_column("deployments", sa.Column("celery_task_id", sa.String(36), nullable=True))
    
    # Make foreign keys nullable for URL-based deployments
    op.alter_column("deployments", "repository_id", nullable=True)
    op.alter_column("deployments", "snapshot_id", nullable=True)
    op.alter_column("deployments", "user_id", nullable=True)


def downgrade() -> None:
    # Restore foreign key constraints
    op.alter_column("deployments", "user_id", nullable=False)
    op.alter_column("deployments", "snapshot_id", nullable=False)
    op.alter_column("deployments", "repository_id", nullable=False)
    
    # Drop new columns
    op.drop_column("deployments", "celery_task_id")
    op.drop_column("deployments", "snapshot_path")
    op.drop_column("deployments", "build_container_id")
    op.drop_column("deployments", "container_id")
    
    # Drop deployment_logs table
    op.drop_table("deployment_logs")