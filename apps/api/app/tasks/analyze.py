import tempfile
import subprocess
from pathlib import Path

from app.tasks.celery_app import celery_app
from app.services.analyzer import detect_framework, detect_languages


@celery_app.task(bind=True, max_retries=3, time_limit=300)
def analyze_repository_task(self, repo_url: str, commit_sha: str, snapshot_id: str):
    builds_dir = Path(tempfile.gettempdir()) / "repo2web_builds"
    builds_dir.mkdir(exist_ok=True)
    dest = builds_dir / commit_sha[:12]

    try:
        subprocess.run(
            [
                "git", "clone", "--no-local", "--no-hardlinks",
                "--config", "core.hooksPath=/dev/null",
                repo_url, str(dest),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )

        framework, confidence = detect_framework(str(dest))
        languages = detect_languages(str(dest))

        return {
            "snapshot_id": snapshot_id,
            "framework": framework,
            "detected_languages": languages,
            "confidence_score": confidence,
            "status": "completed",
        }
    except subprocess.TimeoutExpired:
        return {"snapshot_id": snapshot_id, "status": "timeout"}
    except Exception as e:
        return {"snapshot_id": snapshot_id, "status": "failed", "error": str(e)}
