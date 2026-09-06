import os
from pathlib import Path
from typing import Optional

from app.models.analysis import AnalysisResult, ExecutionPlan


FRAMEWORK_DETECTORS = {
    "streamlit": {"files": ["requirements.txt"], "deps": ["streamlit"], "port": 8501},
    "django": {"files": ["requirements.txt", "manage.py"], "deps": ["django"], "port": 8000},
    "flask": {"files": ["requirements.txt"], "deps": ["flask"], "port": 5000},
    "fastapi": {"files": ["requirements.txt"], "deps": ["fastapi", "uvicorn"], "port": 8000},
    "nextjs": {"files": ["package.json"], "deps": ["next"], "port": 3000},
    "react": {"files": ["package.json"], "deps": ["react", "react-dom"], "port": 3000},
    "vue": {"files": ["package.json"], "deps": ["vue"], "port": 3000},
    "express": {"files": ["package.json"], "deps": ["express"], "port": 3000},
}


def detect_framework(repo_path: str) -> tuple[Optional[str], float]:
    path = Path(repo_path)

    for framework, rules in FRAMEWORK_DETECTORS.items():
        has_files = all((path / f).exists() for f in rules["files"])
        if not has_files:
            continue

        deps = _read_dependencies(path, rules["files"])
        matched = any(d in " ".join(deps) for d in rules["deps"])
        if matched:
            return framework, 0.9

    return None, 0.0


def detect_languages(repo_path: str) -> list[dict]:
    path = Path(repo_path)
    ext_counts: dict[str, int] = {}

    for root, _, files in os.walk(repo_path):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in (".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb"):
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    total = sum(ext_counts.values()) or 1
    ext_to_lang = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".jsx": "React", ".tsx": "React TSX", ".go": "Go",
        ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
    }

    return [
        {"name": ext_to_lang.get(ext, ext), "percentage": round(count / total, 2)}
        for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1])
    ]


def _read_dependencies(path: Path, files: list[str]) -> list[str]:
    deps = []
    for f in files:
        filepath = path / f
        if not filepath.exists():
            continue
        content = filepath.read_text(errors="ignore").lower()
        deps.append(content)
    return deps


def generate_execution_plan(analysis: AnalysisResult) -> dict:
    framework = analysis.framework
    plan = {
        "runtime": "docker",
        "framework": framework or "unknown",
        "install_steps": [],
        "build_steps": [],
        "run_command": "",
        "port": 3000,
        "environment": {},
        "resource_requirements": {
            "cpu_limit": "1.0",
            "memory_limit": "512m",
            "storage_limit": "1g",
        },
        "network_requirements": {
            "allowed_hosts": [],
            "port": 3000,
            "expose_externally": False,
        },
    }

    if framework in ("streamlit", "django", "flask", "fastapi"):
        plan["install_steps"] = [{"name": "install", "command": "pip install -r requirements.txt"}]
        plan["run_command"] = _get_python_run_command(framework, analysis)
        plan["port"] = FRAMEWORK_DETECTORS.get(framework, {}).get("port", 8000)

    elif framework in ("nextjs", "react", "vue", "express"):
        plan["install_steps"] = [{"name": "install", "command": "npm install"}]
        plan["build_steps"] = [{"name": "build", "command": "npm run build"}]
        plan["run_command"] = "npm start"
        plan["port"] = FRAMEWORK_DETECTORS.get(framework, {}).get("port", 3000)

    return plan


def _get_python_run_command(framework: str, analysis: AnalysisResult) -> str:
    if framework == "streamlit":
        entry = analysis.entrypoint or "app.py"
        return f"streamlit run {entry}"
    elif framework == "django":
        return "python manage.py runserver 0.0.0.0:8000"
    elif framework == "flask":
        entry = analysis.entrypoint or "app.py"
        return f"python {entry}"
    elif framework == "fastapi":
        entry = analysis.entrypoint or "main.py"
        return f"uvicorn {entry.replace('.py', '')}:app --host 0.0.0.0 --port 8000"
    return "python app.py"
