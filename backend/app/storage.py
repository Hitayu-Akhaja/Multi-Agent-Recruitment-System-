from pathlib import Path
import uuid

from .config import STORAGE_DIR


def ensure_storage_dir() -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def create_job_dir() -> tuple[str, Path]:
    ensure_storage_dir()
    job_id = uuid.uuid4().hex
    job_dir = STORAGE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=False)
    (job_dir / "resumes").mkdir(parents=True, exist_ok=True)
    return job_id, job_dir
