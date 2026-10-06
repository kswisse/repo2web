"""
Tests for execution observability and resource accounting.

Tests resource metrics collection, persistence, health check persistence,
and API serialization of observability data.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.runtime.metrics import ResourceCollector, ContainerMetrics


# ============================================================================
# Resource Collector Abstraction Tests
# ============================================================================


class TestContainerMetrics:
    """Test ContainerMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating a ContainerMetrics instance."""
        metrics = ContainerMetrics(
            container_id="abc123",
            timestamp=datetime.now(timezone.utc),
            cpu_usage_percent=45.5,
            memory_usage_bytes=256 * 1024 * 1024,
            memory_limit_bytes=512 * 1024 * 1024,
            memory_percent=50.0,
            network_rx_bytes=1024,
            network_tx_bytes=2048,
            block_io_read_bytes=4096,
            block_io_write_bytes=8192,
            pids=5,
        )
        assert metrics.container_id == "abc123"
        assert metrics.cpu_usage_percent == 45.5
        assert metrics.memory_percent == 50.0
        assert metrics.status == "unknown"
        assert metrics.exit_code is None

    def test_metrics_frozen(self):
        """Test that ContainerMetrics is immutable."""
        metrics = ContainerMetrics(
            container_id="abc123",
            timestamp=datetime.now(timezone.utc),
            cpu_usage_percent=0.0,
            memory_usage_bytes=0,
            memory_limit_bytes=0,
            memory_percent=0.0,
            network_rx_bytes=0,
            network_tx_bytes=0,
            block_io_read_bytes=0,
            block_io_write_bytes=0,
            pids=0,
        )
        with pytest.raises(AttributeError):
            metrics.cpu_usage_percent = 99.0

    def test_metrics_with_optional_fields(self):
        """Test ContainerMetrics with optional fields."""
        metrics = ContainerMetrics(
            container_id="abc123",
            timestamp=datetime.now(timezone.utc),
            cpu_usage_percent=0.0,
            memory_usage_bytes=0,
            memory_limit_bytes=0,
            memory_percent=0.0,
            network_rx_bytes=0,
            network_tx_bytes=0,
            block_io_read_bytes=0,
            block_io_write_bytes=0,
            pids=0,
            uptime_seconds=3600,
            status="running",
            exit_code=0,
        )
        assert metrics.uptime_seconds == 3600
        assert metrics.status == "running"
        assert metrics.exit_code == 0


class TestResourceCollector:
    """Test ResourceCollector abstract interface."""

    def test_cannot_instantiate_abstract(self):
        """Test that ResourceCollector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ResourceCollector()


# ============================================================================
# Docker Resource Collector Tests
# ============================================================================


class TestDockerResourceCollector:
    """Test DockerResourceCollector."""

    @patch("app.infrastructure.docker_metrics.docker", None)
    def test_unavailable_when_docker_not_installed(self):
        """Test that collector is unavailable when docker is not installed."""
        from app.infrastructure.docker_metrics import DockerResourceCollector
        collector = DockerResourceCollector()
        assert collector.available is False

    @pytest.mark.asyncio
    async def test_collect_metrics_returns_none_when_unavailable(self):
        """Test collect_metrics returns None when Docker is unavailable."""
        from app.infrastructure.docker_metrics import DockerResourceCollector
        collector = DockerResourceCollector()
        collector.available = False
        result = await collector.collect_metrics("test-container")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_container_stats_returns_empty_when_unavailable(self):
        """Test get_container_stats returns empty dict when unavailable."""
        from app.infrastructure.docker_metrics import DockerResourceCollector
        collector = DockerResourceCollector()
        collector.available = False
        result = await collector.get_container_stats("test-container")
        assert result == {}


# ============================================================================
# Deployment Metrics Model Tests
# ============================================================================


class TestDeploymentMetricsModel:
    """Test DeploymentMetrics SQLAlchemy model."""

    def test_model_has_required_columns(self):
        """Test that DeploymentMetrics model has required columns."""
        from app.models.deployment_metrics import DeploymentMetrics
        columns = {c.name for c in DeploymentMetrics.__table__.columns}
        expected = {
            'id', 'deployment_id', 'timestamp', 'cpu_usage_percent',
            'memory_usage_bytes', 'memory_limit_bytes', 'memory_percent',
            'network_rx_bytes', 'network_tx_bytes', 'container_status',
            'exit_code', 'uptime_seconds', 'created_at',
        }
        assert expected.issubset(columns)

    def test_model_tablename(self):
        """Test DeploymentMetrics table name."""
        from app.models.deployment_metrics import DeploymentMetrics
        assert DeploymentMetrics.__tablename__ == "deployment_metrics"


# ============================================================================
# Deployment Health Model Tests
# ============================================================================


class TestDeploymentHealthModel:
    """Test DeploymentHealth SQLAlchemy model."""

    def test_model_has_required_columns(self):
        """Test that DeploymentHealth model has required columns."""
        from app.models.deployment_health import DeploymentHealth
        columns = {c.name for c in DeploymentHealth.__table__.columns}
        expected = {
            'id', 'deployment_id', 'status', 'response_time_ms',
            'status_code', 'error_message', 'attempt_number',
            'checked_at', 'is_final', 'created_at',
        }
        assert expected.issubset(columns)

    def test_model_tablename(self):
        """Test DeploymentHealth table name."""
        from app.models.deployment_health import DeploymentHealth
        assert DeploymentHealth.__tablename__ == "deployment_health"


# ============================================================================
# Deployment Model Health Fields Tests
# ============================================================================


class TestDeploymentModelHealthFields:
    """Test that Deployment model has health observability fields."""

    def test_has_health_status(self):
        """Test Deployment has health_status column."""
        from app.models.deployment import Deployment
        columns = {c.name for c in Deployment.__table__.columns}
        assert 'health_status' in columns

    def test_has_health_response_time_ms(self):
        """Test Deployment has health_response_time_ms column."""
        from app.models.deployment import Deployment
        columns = {c.name for c in Deployment.__table__.columns}
        assert 'health_response_time_ms' in columns

    def test_has_last_health_check_at(self):
        """Test Deployment has last_health_check_at column."""
        from app.models.deployment import Deployment
        columns = {c.name for c in Deployment.__table__.columns}
        assert 'last_health_check_at' in columns


# ============================================================================
# Deployment Result Health Fields Tests
# ============================================================================


class TestDeploymentResultHealthFields:
    """Test that DeploymentResult includes health fields."""

    def test_result_has_health_fields(self):
        """Test DeploymentResult dataclass has health fields."""
        from app.orchestrator.orchestrator import DeploymentResult
        result = DeploymentResult(
            deployment_id="test-id",
            state=MagicMock(),
            repository_url="https://github.com/test/repo",
            health_status="healthy",
            health_response_time_ms=150,
        )
        assert result.health_status == "healthy"
        assert result.health_response_time_ms == 150
        assert result.resource_metrics is None

    def test_result_has_resource_metrics_field(self):
        """Test DeploymentResult has resource_metrics field."""
        from app.orchestrator.orchestrator import DeploymentResult
        metrics = ContainerMetrics(
            container_id="test",
            timestamp=datetime.now(timezone.utc),
            cpu_usage_percent=10.0,
            memory_usage_bytes=1024,
            memory_limit_bytes=2048,
            memory_percent=50.0,
            network_rx_bytes=0,
            network_tx_bytes=0,
            block_io_read_bytes=0,
            block_io_write_bytes=0,
            pids=1,
        )
        result = DeploymentResult(
            deployment_id="test-id",
            state=MagicMock(),
            repository_url="https://github.com/test/repo",
            resource_metrics=metrics,
        )
        assert result.resource_metrics is not None
        assert result.resource_metrics.cpu_usage_percent == 10.0


# ============================================================================
# API Schema Tests
# ============================================================================


class TestDeploymentSchemas:
    """Test deployment API schemas."""

    def test_response_has_health_fields(self):
        """Test DeploymentResponse schema includes health fields."""
        from app.schemas.deployment import DeploymentResponse
        schema = DeploymentResponse(
            id="test-id",
            state="running",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            health_status="healthy",
            health_response_time_ms=100,
            last_health_check_at=datetime.now(timezone.utc),
        )
        assert schema.health_status == "healthy"
        assert schema.health_response_time_ms == 100
        assert schema.last_health_check_at is not None

    def test_detail_response_has_resource_metrics(self):
        """Test DeploymentDetailResponse includes resource_metrics."""
        from app.schemas.deployment import DeploymentDetailResponse, ResourceMetricsResponse
        metrics = ResourceMetricsResponse(
            cpu_usage_percent=25.0,
            memory_usage_bytes=512 * 1024 * 1024,
            memory_limit_bytes=1024 * 1024 * 1024,
            memory_percent=50.0,
            container_status="running",
            uptime_seconds=3600,
            timestamp=datetime.now(timezone.utc),
        )
        schema = DeploymentDetailResponse(
            id="test-id",
            state="running",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            resource_metrics=metrics,
        )
        assert schema.resource_metrics is not None
        assert schema.resource_metrics.cpu_usage_percent == 25.0
        assert schema.resource_metrics.memory_percent == 50.0

    def test_resource_metrics_schema_optional_fields(self):
        """Test ResourceMetricsResponse with only optional fields."""
        from app.schemas.deployment import ResourceMetricsResponse
        schema = ResourceMetricsResponse()
        assert schema.cpu_usage_percent is None
        assert schema.memory_usage_bytes is None


# ============================================================================
# Frontend Type Tests
# ============================================================================


class TestFrontendTypes:
    """Verify frontend TypeScript types match backend API."""

    TS_FILE = Path(__file__).resolve().parents[2] / "web" / "src" / "lib" / "api" / "deployments.ts"

    def test_frontend_deployment_has_health_fields(self):
        """Verify the deployment TS type includes health fields."""
        # This is a structural check - verify the fields exist in the TS file
        ts_file = self.TS_FILE.read_text()
        assert "health_status" in ts_file
        assert "health_response_time_ms" in ts_file
        assert "last_health_check_at" in ts_file

    def test_frontend_has_resource_metrics_interface(self):
        """Verify ResourceMetrics interface exists in TS file."""
        ts_file = self.TS_FILE.read_text()
        assert "interface ResourceMetrics" in ts_file
        assert "cpu_usage_percent" in ts_file
        assert "memory_percent" in ts_file
        assert "uptime_seconds" in ts_file
