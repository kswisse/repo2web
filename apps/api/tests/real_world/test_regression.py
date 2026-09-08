"""Phase 2.8 — Regression tests for compatibility improvements."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.analyzer.analyzer import analyze_repository
from app.analyzer.file_inventory import scan_repository
from app.analyzer.manifest_parser import detect_package_manager


class TestMonorepoDetection:
    """Test monorepo detection and package merging."""

    def test_detect_pnpm_workspace(self, tmp_path):
        """Test detection of pnpm workspace monorepo."""
        # Create a pnpm workspace structure
        root_pkg = {"name": "monorepo-root", "private": True}
        (tmp_path / "package.json").write_text(json.dumps(root_pkg))
        (tmp_path / "pnpm-workspace.yaml").write_text(
            "packages:\n  - 'packages/*'\n"
        )

        # Create a sub-package
        packages_dir = tmp_path / "packages" / "my-app"
        packages_dir.mkdir(parents=True)
        sub_pkg = {
            "name": "my-app",
            "dependencies": {"express": "^4.18.0"},
        }
        (packages_dir / "package.json").write_text(json.dumps(sub_pkg))

        # Scan the repository
        inventory = scan_repository(str(tmp_path))

        assert inventory.is_monorepo is True
        assert len(inventory.monorepo_packages) > 0

        # Verify that sub-package dependencies are merged into root
        root_content = inventory.key_files.get("package.json")
        assert root_content is not None
        root_data = json.loads(root_content)
        assert "express" in root_data.get("dependencies", {})

    def test_detect_npm_workspaces(self, tmp_path):
        """Test detection of npm/yarn workspaces monorepo."""
        root_pkg = {
            "name": "monorepo-root",
            "workspaces": ["packages/*"],
        }
        (tmp_path / "package.json").write_text(json.dumps(root_pkg))

        # Create a sub-package
        packages_dir = tmp_path / "packages" / "my-app"
        packages_dir.mkdir(parents=True)
        sub_pkg = {
            "name": "my-app",
            "dependencies": {"react": "^18.0.0"},
        }
        (packages_dir / "package.json").write_text(json.dumps(sub_pkg))

        inventory = scan_repository(str(tmp_path))

        assert inventory.is_monorepo is True

        # Verify dependencies merged
        root_content = inventory.key_files.get("package.json")
        root_data = json.loads(root_content)
        assert "react" in root_data.get("dependencies", {})

    def test_non_monorepo_not_flagged(self, tmp_path):
        """Test that non-monorepo repos are not flagged."""
        root_pkg = {
            "name": "simple-app",
            "dependencies": {"express": "^4.18.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(root_pkg))

        inventory = scan_repository(str(tmp_path))

        assert inventory.is_monorepo is False
        assert len(inventory.monorepo_packages) == 0


class TestPackageManagerDetection:
    """Test improved package manager detection."""

    def test_pnpm_lockfile_priority(self):
        """Test that pnpm lockfile is detected correctly."""
        key_files = {
            "package.json": "{}",
            "pnpm-lock.yaml": "lockfileVersion: '6.0'",
        }
        assert detect_package_manager(key_files) == "pnpm"

    def test_yarn_lockfile_priority(self):
        """Test that yarn lockfile is detected correctly."""
        key_files = {
            "package.json": "{}",
            "yarn.lock": "# yarn lockfile",
        }
        assert detect_package_manager(key_files) == "yarn"

    def test_npm_lockfile_priority(self):
        """Test that npm lockfile is detected correctly."""
        key_files = {
            "package.json": "{}",
            "package-lock.json": "{}",
        }
        assert detect_package_manager(key_files) == "npm"

    def test_poetry_lockfile(self):
        """Test that poetry lockfile is detected correctly."""
        key_files = {
            "pyproject.toml": "[tool.poetry]",
            "poetry.lock": "",
        }
        assert detect_package_manager(key_files) == "poetry"

    def test_pipenv_lockfile(self):
        """Test that pipenv lockfile is detected correctly."""
        key_files = {
            "Pipfile": "[packages]",
            "Pipfile.lock": "{}",
        }
        assert detect_package_manager(key_files) == "pipenv"


class TestAnalyzerRegression:
    """Regression tests for analyzer improvements."""

    def test_fastapi_app_detected(self, tmp_path):
        """Test that a simple FastAPI app is correctly detected."""
        # Create a minimal FastAPI app
        main_py = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
'''
        (tmp_path / "main.py").write_text(main_py)
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")

        plan = analyze_repository(
            repo_path=str(tmp_path),
            url="https://github.com/test/fastapi-test",
            commit_sha="abc123def456",
            owner="test",
            repo="fastapi-test",
        )

        assert plan.application.language == "python"
        assert plan.application.framework == "fastapi"
        assert plan.build.package_manager == "pip"
        assert plan.runtime.port == 8000

    def test_express_app_detected(self, tmp_path):
        """Test that a simple Express app is correctly detected."""
        pkg_json = {
            "name": "test-app",
            "dependencies": {"express": "^4.18.0"},
            "scripts": {"start": "node server.js"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg_json))
        (tmp_path / "package-lock.json").write_text("{}")
        (tmp_path / "server.js").write_text(
            "const express = require('express');\n"
            "const app = express();\n"
            "app.get('/', (req, res) => res.send('Hello'));\n"
            "app.listen(3000);\n"
        )

        plan = analyze_repository(
            repo_path=str(tmp_path),
            url="https://github.com/test/express-test",
            commit_sha="abc123def456",
            owner="test",
            repo="express-test",
        )

        assert plan.application.language == "node"
        assert plan.application.framework == "express"
        assert plan.build.package_manager == "npm"
        assert plan.runtime.port == 3000

    def test_flask_app_detected(self, tmp_path):
        """Test that a simple Flask app is correctly detected."""
        app_py = '''
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World"
'''
        (tmp_path / "app.py").write_text(app_py)
        (tmp_path / "requirements.txt").write_text("flask\n")

        plan = analyze_repository(
            repo_path=str(tmp_path),
            url="https://github.com/test/flask-test",
            commit_sha="abc123def456",
            owner="test",
            repo="flask-test",
        )

        assert plan.application.language == "python"
        assert plan.application.framework == "flask"
        assert plan.runtime.port == 5000
