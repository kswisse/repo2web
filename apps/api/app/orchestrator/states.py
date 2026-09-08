"""
Deployment states.

Defines all possible states in the deployment lifecycle.
"""

from enum import Enum


class DeploymentState(Enum):
    """All possible deployment states.
    
    State transitions:
    queued -> cloning -> analyzing -> planning -> building -> starting -> health_checking -> running
    
    Terminal states:
    - running: Successfully deployed
    - clone_failed: Repository cloning failed
    - analysis_failed: Repository analysis failed
    - plan_failed: Execution plan generation failed
    - build_failed: Build process failed
    - start_failed: Runtime startup failed
    - health_check_failed: Health check failed
    - security_blocked: Security policy violation
    - timeout: Operation timed out
    - cancelled: Deployment cancelled by user
    """
    
    # Initial state
    QUEUED = "queued"
    
    # Pipeline states
    CLONING = "cloning"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    BUILDING = "building"
    STARTING = "starting"
    HEALTH_CHECKING = "health_checking"
    
    # Success state
    RUNNING = "running"
    
    # Failure states
    CLONE_FAILED = "clone_failed"
    ANALYSIS_FAILED = "analysis_failed"
    PLAN_FAILED = "plan_failed"
    BUILD_FAILED = "build_failed"
    START_FAILED = "start_failed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    
    # Repair states
    REPAIRING = "repairing"
    VALIDATING_REPAIR = "validating_repair"
    REPAIR_EXHAUSTED = "repair_exhausted"

    # Security/Timeout states
    SECURITY_BLOCKED = "security_blocked"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

    @classmethod
    def is_terminal(cls, state: "DeploymentState") -> bool:
        """Check if state is terminal (no further transitions)."""
        terminal_states = {
            cls.RUNNING,
            cls.CLONE_FAILED,
            cls.ANALYSIS_FAILED,
            cls.PLAN_FAILED,
            cls.BUILD_FAILED,
            cls.START_FAILED,
            cls.HEALTH_CHECK_FAILED,
            cls.REPAIR_EXHAUSTED,
            cls.SECURITY_BLOCKED,
            cls.TIMEOUT,
            cls.CANCELLED,
        }
        return state in terminal_states

    @classmethod
    def is_success(cls, state: "DeploymentState") -> bool:
        """Check if state represents successful deployment."""
        return state == cls.RUNNING

    @classmethod
    def is_failure(cls, state: "DeploymentState") -> bool:
        """Check if state represents a failure."""
        failure_states = {
            cls.CLONE_FAILED,
            cls.ANALYSIS_FAILED,
            cls.PLAN_FAILED,
            cls.BUILD_FAILED,
            cls.START_FAILED,
            cls.HEALTH_CHECK_FAILED,
            cls.REPAIR_EXHAUSTED,
            cls.SECURITY_BLOCKED,
            cls.TIMEOUT,
        }
        return state in failure_states

    @classmethod
    def get_valid_transitions(cls, state: "DeploymentState") -> set["DeploymentState"]:
        """Get valid transitions from a given state."""
        transitions = {
            cls.QUEUED: {cls.CLONING, cls.CANCELLED},
            cls.CLONING: {cls.ANALYZING, cls.CLONE_FAILED},
            cls.ANALYZING: {cls.PLANNING, cls.ANALYSIS_FAILED},
            cls.PLANNING: {cls.BUILDING, cls.PLAN_FAILED},
            cls.BUILDING: {cls.STARTING, cls.BUILD_FAILED, cls.SECURITY_BLOCKED, cls.REPAIRING},
            cls.STARTING: {cls.HEALTH_CHECKING, cls.START_FAILED, cls.REPAIRING},
            cls.HEALTH_CHECKING: {cls.RUNNING, cls.HEALTH_CHECK_FAILED, cls.TIMEOUT, cls.REPAIRING},
            cls.REPAIRING: {cls.VALIDATING_REPAIR, cls.REPAIR_EXHAUSTED},
            cls.VALIDATING_REPAIR: {cls.BUILDING, cls.REPAIR_EXHAUSTED},
        }
        return transitions.get(state, set())
