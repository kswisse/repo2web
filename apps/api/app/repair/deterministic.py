"""
Deterministic Repair Provider.

Implements RepairEngine with deterministic rules targeting the 3 failure
classes identified in Phase 2.8:

1. True framework-as-repo — repo IS the framework (express, flask, fastapi)
2. Monorepo/multi-language misidentification — analyzer picks wrong sub-package
3. False positive detection — detects internal dependency instead of identity
"""

import re
from pathlib import Path
from typing import Optional

from app.repair.engine import RepairEngine
from app.repair.types import RepairContext, RepairProposal, RepairType


# Framework-as-repo mappings: repo name → correct framework
FRAMEWORK_AS_REPO = {
    "express": {"framework": "express", "language": "node", "port": 3000},
    "flask": {"framework": "flask", "language": "python", "port": 5000},
    "fastapi": {"framework": "fastapi", "language": "python", "port": 8000},
    "koa": {"framework": "koa", "language": "node", "port": 3000},
    "sanic": {"framework": "sanic", "language": "python", "port": 8000},
    "tornado": {"framework": "tornado", "language": "python", "port": 8888},
    "django": {"framework": "django", "language": "python", "port": 8000},
    "streamlit": {"framework": "streamlit", "language": "python", "port": 8501},
    "gradio": {"framework": "gradio", "language": "python", "port": 7860},
    "fastify": {"framework": "fastify", "language": "node", "port": 3000},
}

# Monorepo app detection: look for app-level config over library-level
MONOREPO_APP_INDICATORS = {
    "next.config.js": "nextjs",
    "next.config.mjs": "nextjs",
    "next.config.ts": "nextjs",
    "nuxt.config.js": "nuxt",
    "nuxt.config.ts": "nuxt",
    "svelte.config.js": "svelte",
    "svelte.config.ts": "svelte",
    "angular.json": "angular",
    "vue.config.js": "vue",
    "vue.config.ts": "vue",
    "vite.config.js": None,  # Need more context
    "vite.config.ts": None,
    "vite.config.mjs": None,
}

# False positive framework names that may be internal dependencies
FALSE_POSITIVE_FRAMEWORKS = {
    "vite": "react",  # vite is a build tool, not the app framework
    "webpack": "react",  # webpack is a build tool
    "rollup": None,  # build tool
    "esbuild": None,  # build tool
    "parcel": None,  # build tool
    "turbo": None,  # build tool
    "lerna": None,  # monorepo tool
}


class DeterministicRepairProvider(RepairEngine):
    """Deterministic repair provider for framework detection failures.

    Uses rule-based logic to fix the 3 failure classes from Phase 2.8:
    1. Framework-as-repo detection
    2. Monorepo misidentification
    3. False positive framework detection
    """

    def generate_repair(
        self,
        context: RepairContext,
        attempt: int,
    ) -> Optional[RepairProposal]:
        """Generate a deterministic repair proposal.

        Args:
            context: Bounded repair context.
            attempt: Current attempt number (0-based).

        Returns:
            RepairProposal if a repair is possible, None otherwise.
        """
        if attempt >= self.max_attempts():
            return None

        # Try each repair strategy in order
        proposal = (
            self._try_framework_as_repo(context)
            or self._try_monorepo_correction(context)
            or self._try_false_positive_correction(context)
            or self._try_health_path_fallback(context)
        )

        return proposal

    def supported_failure_stages(self) -> set[str]:
        """Return supported failure stages."""
        return {"build", "health_checking", "analysis", "planning"}

    def max_attempts(self) -> int:
        """Maximum repair attempts."""
        return 3

    def _try_framework_as_repo(
        self,
        context: RepairContext,
    ) -> Optional[RepairProposal]:
        """Detect framework-as-repo: the repo IS the framework itself.

        Example: github.com/expressjs/express → framework should be 'express'
        """
        # Extract repo name from URL
        repo_name = self._extract_repo_name(context.repository_url)
        if not repo_name:
            return None

        # Check if repo name matches a known framework
        repo_name_lower = repo_name.lower()
        # Strip trailing "js" suffix (e.g. "expressjs" → "express")
        if repo_name_lower.endswith("js"):
            repo_name_lower = repo_name_lower[:-2]
        if repo_name_lower not in FRAMEWORK_AS_REPO:
            return None

        # Check if current detection is wrong or missing
        expected = FRAMEWORK_AS_REPO[repo_name_lower]
        current_framework = context.framework

        if current_framework == expected["framework"]:
            return None  # Already correct

        # Verify by checking if the repo has framework-identifying files
        if not self._has_framework_files(context, expected["framework"]):
            return None

        return RepairProposal(
            repair_type=RepairType.FRAMEWORK_DETECTION,
            target="framework",
            original_value=current_framework or "unknown",
            proposed_value=expected["framework"],
            rationale=(
                f"Repository name '{repo_name}' matches framework '{expected['framework']}'. "
                f"This is likely the framework source itself, not an application using it. "
                f"Current detection is '{current_framework or 'unknown'}' which is incorrect."
            ),
            evidence=[
                f"Repository name: {repo_name}",
                f"Expected framework: {expected['framework']}",
                f"Language should be: {expected['language']}",
            ],
            confidence="HIGH",
        )

    def _try_monorepo_correction(
        self,
        context: RepairContext,
    ) -> Optional[RepairProposal]:
        """Fix monorepo misidentification by detecting app-level configs.

        In monorepos, the analyzer may pick up a library's config instead
        of the app's config. This checks for app-level framework configs.
        """
        # Look for app-level framework config files
        for file_name in context.file_names:
            if file_name in MONOREPO_APP_INDICATORS:
                detected_framework = MONOREPO_APP_INDICATORS[file_name]
                if detected_framework and detected_framework != context.framework:
                    return RepairProposal(
                        repair_type=RepairType.FRAMEWORK_DETECTION,
                        target="framework",
                        original_value=context.framework or "unknown",
                        proposed_value=detected_framework,
                        rationale=(
                            f"Found app-level config file '{file_name}' which indicates "
                            f"framework '{detected_framework}'. Current detection of "
                            f"'{context.framework or 'unknown'}' may be from a sub-package."
                        ),
                        evidence=[
                            f"Config file found: {file_name}",
                            f"Implies framework: {detected_framework}",
                        ],
                        confidence="MEDIUM",
                    )

        return None

    def _try_false_positive_correction(
        self,
        context: RepairContext,
    ) -> Optional[RepairProposal]:
        """Correct false positive framework detection.

        Example: vite is a build tool, not the app framework.
        The actual framework might be React, Vue, etc.
        """
        if not context.framework:
            return None

        framework_lower = context.framework.lower()

        if framework_lower not in FALSE_POSITIVE_FRAMEWORKS:
            return None

        actual_framework = FALSE_POSITIVE_FRAMEWORKS[framework_lower]
        if not actual_framework:
            return None  # Can't determine actual framework

        # Check if the actual framework's dependencies are present
        # This is a heuristic — if we see react-dom, the app is likely React
        if actual_framework == "react":
            # Check for react-like file patterns
            has_react_files = any(
                f.endswith((".jsx", ".tsx")) or "react" in f.lower()
                for f in context.file_names
            )
            if not has_react_files:
                return None

        return RepairProposal(
            repair_type=RepairType.FRAMEWORK_DETECTION,
            target="framework",
            original_value=context.framework,
            proposed_value=actual_framework,
            rationale=(
                f"Detected framework '{context.framework}' is a build tool, "
                f"not the application framework. Based on repository structure, "
                f"the actual application framework appears to be '{actual_framework}'."
            ),
            evidence=[
                f"Current (incorrect) detection: {context.framework}",
                f"Build tool detected instead of app framework",
                f"Corrected to: {actual_framework}",
            ],
            confidence="MEDIUM",
        )

    def _try_health_path_fallback(
        self,
        context: RepairContext,
    ) -> Optional[RepairProposal]:
        """If health check fails, try common alternative paths."""
        # This handles HEALTH_CHECK_FAILED specifically
        if context.failure_stage != "health_checking":
            return None

        current_path = context.health_check_path
        alternatives = ["/", "/health", "/healthz", "/api/health", "/ping"]

        for alt in alternatives:
            if alt != current_path:
                return RepairProposal(
                    repair_type=RepairType.HEALTH_CHECK_PATH,
                    target="health_check_path",
                    original_value=current_path,
                    proposed_value=alt,
                    rationale=(
                        f"Health check at '{current_path}' failed. "
                        f"Trying alternative path '{alt}'."
                    ),
                    evidence=[
                        f"Original path failed: {current_path}",
                        f"Trying alternative: {alt}",
                    ],
                    confidence="LOW",
                )

        return None

    def _extract_repo_name(self, url: str) -> Optional[str]:
        """Extract repository name from GitHub URL."""
        # Strip trailing slash and .git suffix
        url = url.rstrip("/").rstrip("/")
        match = re.search(r"github\.com/[^/]+/([^/]+?)(?:\.git)?$", url)
        if match:
            return match.group(1)
        return None

    def _has_framework_files(
        self,
        context: RepairContext,
        framework: str,
    ) -> bool:
        """Check if repository has files identifying the framework."""
        framework_indicators = {
            "express": ["index.js", "app.js", "server.js", "src/index.js", "src/app.js"],
            "flask": ["app.py", "main.py", "wsgi.py", "src/app.py", "src/main.py"],
            "fastapi": ["main.py", "app.py", "src/main.py", "src/app.py"],
            "koa": ["index.js", "app.js", "server.js"],
            "django": ["manage.py", "settings.py", "wsgi.py"],
            "streamlit": ["app.py", "streamlit_app.py"],
            "gradio": ["app.py", "demo.py"],
            "fastify": ["index.js", "app.js", "server.js"],
            "sanic": ["app.py", "main.py"],
            "tornado": ["app.py", "main.py"],
        }

        indicators = framework_indicators.get(framework, [])
        return any(ind in context.file_names for ind in indicators)
