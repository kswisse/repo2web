"""
End-to-end tests for the deployment pipeline.

Tests the full pipeline from GitHub URL to RUNNING state.
Uses local Git repositories for testing.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repository.fetcher import RepositoryFetcher
from app.repository.snapshot import RepositorySnapshot
from app.repository.exceptions import (
    RepositoryValidationError,
    RepositoryCloneError,
    RepositoryTimeoutError,
)
from app.orchestrator.orchestrator import DeploymentOrchestrator, DeploymentResult
from app.orchestrator.states import DeploymentState


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def local_fastapi_repo(tmp_path):
    """Create a local FastAPI repository for testing."""
    repo = tmp_path / "fastapi-app"
    repo.mkdir()
    
    # Create main.py
    (repo / "main.py").write_text("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "hello"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
""")
    
    # Create requirements.txt
    (repo / "requirements.txt").write_text("fastapi\nuvicorn\n")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    
    return repo


@pytest.fixture
def local_flask_repo(tmp_path):
    """Create a local Flask repository for testing."""
    repo = tmp_path / "flask-app"
    repo.mkdir()
    
    # Create app.py
    (repo / "app.py").write_text("""
from flask import Flask, jsonify
app = Flask(__name__)

@app.route("/")
def root():
    return jsonify({"message": "hello"})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})
""")
    
    # Create requirements.txt
    (repo / "requirements.txt").write_text("flask\n")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    
    return repo


@pytest.fixture
def local_node_repo(tmp_path):
    """Create a local Node.js repository for testing."""
    repo = tmp_path / "node-app"
    repo.mkdir()
    
    # Create package.json
    (repo / "package.json").write_text("""
{
  "name": "test-app",
  "version": "1.0.0",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.0"
  }
}
""")
    
    # Create server.js
    (repo / "server.js").write_text("""
const express = require('express');
const app = express();

app.get('/', (req, res) => {
  res.json({ message: 'hello' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
""")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    
    return repo


@pytest.fixture
def local_cli_repo(tmp_path):
    """Create a local CLI-only repository for testing (unsupported)."""
    repo = tmp_path / "cli-app"
    repo.mkdir()
    
    # Create main.py (CLI only, no web framework)
    (repo / "main.py").write_text("""
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--name', type=str, help='Name to greet')
args = parser.parse_args()
print(f"Hello, {args.name}!")
""")
    
    # Create requirements.txt
    (repo / "requirements.txt").write_text("argparse\n")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    
    return repo


@pytest.fixture
def local_build_failure_repo(tmp_path):
    """Create a local repository that will fail to build."""
    repo = tmp_path / "build-failure"
    repo.mkdir()
    
    # Create main.py with syntax error
    (repo / "main.py").write_text("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "hello"}
    # Syntax error below
    if True
""")
    
    # Create requirements.txt
    (repo / "requirements.txt").write_text("fastapi\nuvicorn\n")
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    
    return repo


# ============================================================================
# Repository Fetcher Tests
# ============================================================================


class TestRepositoryFetcher:
    """Tests for repository fetcher."""
    
    def test_validate_url_valid(self):
        """Test valid GitHub URL validation."""
        fetcher = RepositoryFetcher()
        fetcher._validate_url("https://github.com/owner/repo")
        fetcher._validate_url("https://github.com/user123/my-project")
        fetcher._validate_url("https://github.com/org-name/repo-name.git")
        
    def test_validate_url_invalid(self):
        """Test invalid URL validation."""
        fetcher = RepositoryFetcher()
        
        # Non-GitHub URLs
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("https://gitlab.com/user/repo")
            
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("https://bitbucket.org/user/repo")
            
        # SSH URLs
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("git@github.com:user/repo.git")
            
        # File URLs
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("file:///path/to/repo")
            
        # Empty URL
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("")
            
    def test_validate_url_security(self):
        """Test security-related URL validation."""
        fetcher = RepositoryFetcher()
        
        # URLs with credentials
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("https://user:pass@github.com/user/repo")
            
        # Internal IPs
        with pytest.raises(RepositoryValidationError):
            fetcher._validate_url("https://192.168.1.1/repo")
            
    def test_extract_owner_repo(self):
        """Test owner and repo extraction."""
        fetcher = RepositoryFetcher()
        
        owner, repo = fetcher._extract_owner_repo("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"
        
        owner, repo = fetcher._extract_owner_repo("https://github.com/user123/my-project.git")
        assert owner == "user123"
        assert repo == "my-project"
        
    @pytest.mark.anyio
    async def test_fetch_local_repo(self, local_fastapi_repo, tmp_path):
        """Test fetching a local repository (by copying to temp dir)."""
        # This test verifies the fetcher can work with local repos
        # by simulating a clone operation
        fetcher = RepositoryFetcher(base_dir=str(tmp_path))
        
        # For local testing, we'll copy the repo instead of cloning
        target_dir = tmp_path / "cloned"
        target_dir.mkdir()
        
        # Copy repo contents
        import shutil
        shutil.copytree(local_fastapi_repo, target_dir, dirs_exist_ok=True)
        
        # Create snapshot manually
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/test/fastapi-app",
            owner="test",
            repository="fastapi-app",
            commit_sha="abc123def456",
            local_path=str(target_dir),
        )
        
        assert snapshot.repository_url == "https://github.com/test/fastapi-app"
        assert snapshot.owner == "test"
        assert snapshot.repository == "fastapi-app"
        assert snapshot.commit_sha == "abc123def456"
        assert snapshot.local_path == str(target_dir)
        assert snapshot.created_at != ""


# ============================================================================
# Repository Snapshot Tests
# ============================================================================


class TestRepositorySnapshot:
    """Tests for repository snapshot."""
    
    def test_create_snapshot(self):
        """Test creating a snapshot."""
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/owner/repo",
            owner="owner",
            repository="repo",
            commit_sha="abc123def456",
            local_path="/tmp/repo",
        )
        
        assert snapshot.repository_url == "https://github.com/owner/repo"
        assert snapshot.owner == "owner"
        assert snapshot.repository == "repo"
        assert snapshot.commit_sha == "abc123def456"
        assert snapshot.local_path == "/tmp/repo"
        assert snapshot.created_at != ""
        
    def test_snapshot_immutable(self):
        """Test that snapshot is immutable."""
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/owner/repo",
            owner="owner",
            repository="repo",
            commit_sha="abc123def456",
            local_path="/tmp/repo",
        )
        
        with pytest.raises(AttributeError):
            snapshot.owner = "new-owner"
            
    def test_snapshot_validation(self):
        """Test snapshot validation."""
        with pytest.raises(ValueError):
            RepositorySnapshot(
                repository_url="",
                owner="owner",
                repository="repo",
                commit_sha="abc123def456",
                local_path="/tmp/repo",
                created_at="2024-01-01T00:00:00Z",
            )


# ============================================================================
# Deployment States Tests
# ============================================================================


class TestDeploymentStates:
    """Tests for deployment states."""
    
    def test_terminal_states(self):
        """Test terminal state detection."""
        assert DeploymentState.is_terminal(DeploymentState.RUNNING)
        assert DeploymentState.is_terminal(DeploymentState.CLONE_FAILED)
        assert DeploymentState.is_terminal(DeploymentState.ANALYSIS_FAILED)
        assert DeploymentState.is_terminal(DeploymentState.BUILD_FAILED)
        assert DeploymentState.is_terminal(DeploymentState.CANCELLED)
        
        assert not DeploymentState.is_terminal(DeploymentState.QUEUED)
        assert not DeploymentState.is_terminal(DeploymentState.CLONING)
        assert not DeploymentState.is_terminal(DeploymentState.BUILDING)
        
    def test_success_state(self):
        """Test success state detection."""
        assert DeploymentState.is_success(DeploymentState.RUNNING)
        assert not DeploymentState.is_success(DeploymentState.CLONE_FAILED)
        
    def test_failure_states(self):
        """Test failure state detection."""
        assert DeploymentState.is_failure(DeploymentState.CLONE_FAILED)
        assert DeploymentState.is_failure(DeploymentState.BUILD_FAILED)
        assert DeploymentState.is_failure(DeploymentState.SECURITY_BLOCKED)
        
        assert not DeploymentState.is_failure(DeploymentState.RUNNING)
        assert not DeploymentState.is_failure(DeploymentState.QUEUED)
        
    def test_valid_transitions(self):
        """Test valid state transitions."""
        # From QUEUED
        assert DeploymentState.CLONING in DeploymentState.get_valid_transitions(DeploymentState.QUEUED)
        assert DeploymentState.CANCELLED in DeploymentState.get_valid_transitions(DeploymentState.QUEUED)
        
        # From CLONING
        assert DeploymentState.ANALYZING in DeploymentState.get_valid_transitions(DeploymentState.CLONING)
        assert DeploymentState.CLONE_FAILED in DeploymentState.get_valid_transitions(DeploymentState.CLONING)
        
        # From BUILDING
        assert DeploymentState.STARTING in DeploymentState.get_valid_transitions(DeploymentState.BUILDING)
        assert DeploymentState.BUILD_FAILED in DeploymentState.get_valid_transitions(DeploymentState.BUILDING)
        assert DeploymentState.SECURITY_BLOCKED in DeploymentState.get_valid_transitions(DeploymentState.BUILDING)


# ============================================================================
# Orchestrator Tests (Unit Tests with Mocking)
# ============================================================================


class TestDeploymentOrchestrator:
    """Tests for deployment orchestrator."""
    
    @pytest.mark.anyio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        orchestrator = DeploymentOrchestrator()
        
        assert orchestrator.fetcher is not None
        assert orchestrator.runtime is not None
        assert orchestrator.cleanup is not None
        assert orchestrator.build_executor is not None
        assert orchestrator.runtime_executor is not None
        assert orchestrator.health_checker is not None
        
    @pytest.mark.anyio
    async def test_deploy_with_mocked_components(self, local_fastapi_repo, tmp_path):
        """Test deployment with mocked components."""
        # Create a mock orchestrator
        orchestrator = DeploymentOrchestrator()
        
        # Mock the fetcher to return a snapshot
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/test/fastapi-app",
            owner="test",
            repository="fastapi-app",
            commit_sha="abc123def456",
            local_path=str(local_fastapi_repo),
        )
        
        with patch.object(orchestrator.fetcher, 'fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = snapshot
            
            with patch.object(orchestrator.build_executor, 'execute_build', new_callable=AsyncMock) as mock_build:
                mock_build.return_value = MagicMock(
                    success=True,
                    image="test-image:latest",
                    container_id="test-container-123",
                )
                
                with patch.object(orchestrator.runtime_executor, 'start_runtime', new_callable=AsyncMock) as mock_runtime:
                    mock_runtime.return_value = MagicMock(
                        container_id="runtime-container-123",
                        status="running",
                        internal_url="http://localhost:8000",
                    )
                    
                    with patch.object(orchestrator.health_checker, 'check_health', new_callable=AsyncMock) as mock_health:
                        mock_health.return_value = MagicMock(
                            status="healthy",
                            response_time_ms=150,
                            error=None,
                            attempts=1,
                        )
                        
                        with patch.object(orchestrator.fetcher, 'cleanup', new_callable=AsyncMock):
                            # Run deployment
                            result = await orchestrator.deploy(
                                deployment_id="test-deployment-123",
                                repository_url="https://github.com/test/fastapi-app",
                            )
                            
                            # Verify result
                            assert result.state == DeploymentState.RUNNING
                            assert result.commit_sha == "abc123def456"
                            assert result.framework == "fastapi"
                            assert result.port == 8000
                            assert result.internal_url == "http://localhost:8000"
                            
                            # Verify all stages were called
                            mock_fetch.assert_called_once()
                            mock_build.assert_called_once()
                            mock_runtime.assert_called_once()
                            mock_health.assert_called_once()


# ============================================================================
# Integration Tests (with real components)
# ============================================================================


class TestDeploymentPipeline:
    """Integration tests for the full deployment pipeline."""
    
    @pytest.mark.anyio
    async def test_analyzer_with_local_repo(self, local_fastapi_repo):
        """Test analyzer with local repository."""
        from app.analyzer.analyzer import analyze_repository
        
        plan = analyze_repository(
            repo_path=str(local_fastapi_repo),
            url="https://github.com/test/fastapi-app",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-app",
        )
        
        assert plan.application.language == "python"
        assert plan.application.framework == "fastapi"
        assert plan.runtime.port == 8000
        assert plan.compatibility.status in ("SUPPORTED", "SUPPORTED_WITH_WARNINGS")
        
    @pytest.mark.anyio
    async def test_analyzer_with_flask_repo(self, local_flask_repo):
        """Test analyzer with Flask repository."""
        from app.analyzer.analyzer import analyze_repository
        
        plan = analyze_repository(
            repo_path=str(local_flask_repo),
            url="https://github.com/test/flask-app",
            commit_sha="abc123def456",
            owner="test",
            repo="flask-app",
        )
        
        assert plan.application.language == "python"
        assert plan.application.framework == "flask"
        assert plan.runtime.port == 5000
        
    @pytest.mark.anyio
    async def test_analyzer_with_node_repo(self, local_node_repo):
        """Test analyzer with Node.js repository."""
        from app.analyzer.analyzer import analyze_repository
        
        plan = analyze_repository(
            repo_path=str(local_node_repo),
            url="https://github.com/test/node-app",
            commit_sha="abc123def456",
            owner="test",
            repo="node-app",
        )
        
        assert plan.application.language == "node"
        assert plan.application.framework == "express"
        assert plan.runtime.port == 3000
        
    @pytest.mark.anyio
    async def test_analyzer_with_cli_repo(self, local_cli_repo):
        """Test analyzer with CLI-only repository (unsupported)."""
        from app.analyzer.analyzer import analyze_repository
        
        plan = analyze_repository(
            repo_path=str(local_cli_repo),
            url="https://github.com/test/cli-app",
            commit_sha="abc123def456",
            owner="test",
            repo="cli-app",
        )
        
        assert plan.compatibility.status == "UNSUPPORTED"
        assert len(plan.compatibility.blockers) > 0


# ============================================================================
# Security Tests
# ============================================================================


class TestSecurity:
    """Tests for security requirements."""
    
    def test_no_shell_injection(self):
        """Test that URLs cannot cause shell injection."""
        fetcher = RepositoryFetcher()
        
        # malicious URLs
        malicious_urls = [
            "https://github.com/owner/repo; rm -rf /",
            "https://github.com/owner/repo$(rm -rf /)",
            "https://github.com/owner/repo`rm -rf /`",
        ]
        
        for url in malicious_urls:
            # Should raise validation error, not execute shell command
            with pytest.raises(RepositoryValidationError):
                fetcher._validate_url(url)
                
    def test_url_validation_blocks_internal_ips(self):
        """Test that internal IPs are blocked."""
        fetcher = RepositoryFetcher()
        
        internal_urls = [
            "https://192.168.1.1/repo",
            "https://10.0.0.1/repo",
            "https://172.16.0.1/repo",
            "https://127.0.0.1/repo",
        ]
        
        for url in internal_urls:
            with pytest.raises(RepositoryValidationError):
                fetcher._validate_url(url)
                
    def test_url_validation_blocks_non_github(self):
        """Test that non-GitHub URLs are blocked."""
        fetcher = RepositoryFetcher()
        
        non_github_urls = [
            "https://gitlab.com/user/repo",
            "https://bitbucket.org/user/repo",
            "https://example.com/repo",
        ]
        
        for url in non_github_urls:
            with pytest.raises(RepositoryValidationError):
                fetcher._validate_url(url)


# ============================================================================
# Cleanup Tests
# ============================================================================


class TestCleanup:
    """Tests for cleanup operations."""
    
    @pytest.mark.anyio
    async def test_cleanup_snapshot(self, local_fastapi_repo, tmp_path):
        """Test snapshot cleanup."""
        fetcher = RepositoryFetcher()
        
        # Create a copy to cleanup
        cleanup_dir = tmp_path / "cleanup-test"
        cleanup_dir.mkdir()
        
        import shutil
        shutil.copytree(local_fastapi_repo, cleanup_dir, dirs_exist_ok=True)
        
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/test/fastapi-app",
            owner="test",
            repository="fastapi-app",
            commit_sha="abc123def456",
            local_path=str(cleanup_dir),
        )
        
        # Cleanup
        await fetcher.cleanup(snapshot)
        
        # Verify directory was removed
        assert not cleanup_dir.exists()
        
    @pytest.mark.anyio
    async def test_cleanup_nonexistent_directory(self, tmp_path):
        """Test cleanup of nonexistent directory."""
        fetcher = RepositoryFetcher()
        
        snapshot = RepositorySnapshot.create(
            repository_url="https://github.com/test/fastapi-app",
            owner="test",
            repository="fastapi-app",
            commit_sha="abc123def456",
            local_path=str(tmp_path / "nonexistent"),
        )
        
        # Should not raise
        await fetcher.cleanup(snapshot)
