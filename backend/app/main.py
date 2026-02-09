from __future__ import annotations

from pathlib import Path
import json
import shutil
import zipfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import BASE_DIR
from .graph import run_graph
from .models import ScoreResponse
from .storage import create_job_dir


ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}

app = FastAPI(title="Resume Scoring API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_unique_path(base_path: Path) -> Path:
    if not base_path.exists():
        return base_path
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def save_upload_file(upload_file: UploadFile, dest_path: Path) -> None:
    with dest_path.open("wb") as file_handle:
        shutil.copyfileobj(upload_file.file, file_handle)


def safe_extract_zip(upload_file: UploadFile, dest_dir: Path) -> int:
    extracted = 0
    with zipfile.ZipFile(upload_file.file) as zip_handle:
        for member in zip_handle.infolist():
            if member.is_dir():
                continue
            filename = Path(member.filename).name
            if not filename:
                continue
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            target_path = dest_dir / filename
            target_path = ensure_unique_path(target_path)
            resolved_target = target_path.resolve()
            if dest_dir.resolve() not in resolved_target.parents:
                continue
            with zip_handle.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            extracted += 1
    return extracted


@app.get("/api/v1/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/score", response_model=ScoreResponse)
def score_resumes(
    jd_text: str | None = Form(default=None),
    jd_file: UploadFile | None = File(default=None),
    resumes: list[UploadFile] | None = File(default=None),
    resumes_zip: UploadFile | None = File(default=None),
):
    if jd_text is None and jd_file is None:
        raise HTTPException(status_code=400, detail="Provide jd_text or jd_file.")
    if (resumes is None or len(resumes) == 0) and resumes_zip is None:
        raise HTTPException(status_code=400, detail="Provide resumes or resumes_zip.")

    job_id, job_dir = create_job_dir()
    jd_path = job_dir / "jd.txt"
    resume_dir = job_dir / "resumes"

    if jd_file is not None:
        save_upload_file(jd_file, jd_path)
    else:
        jd_path.write_text(jd_text or "", encoding="utf-8")

    saved_files = 0
    if resumes:
        for resume in resumes:
            ext = Path(resume.filename or "").suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            target_path = ensure_unique_path(resume_dir / resume.filename)
            save_upload_file(resume, target_path)
            saved_files += 1

    if resumes_zip is not None:
        saved_files += safe_extract_zip(resumes_zip, resume_dir)

    if saved_files == 0:
        raise HTTPException(status_code=400, detail="No valid resume files provided.")

    final_state = run_graph(str(jd_path), str(resume_dir))
    output_path = job_dir / "output.json"
    output_path.write_text(json.dumps(final_state, indent=2), encoding="utf-8")

    for folder_name in ("Accepted", "Rejected", "Review"):
        source_dir = resume_dir / folder_name
        if not source_dir.exists():
            continue
        root_target_dir = BASE_DIR.parent / folder_name
        try:
            shutil.copytree(source_dir, root_target_dir, dirs_exist_ok=True)
        except OSError:
            pass

    score_sheet_path = None
    sheets = list((resume_dir / "score_sheets").glob("*.csv"))
    if sheets:
        sheet_path = sheets[0]
        score_sheet_path = str(sheet_path)
        root_target = BASE_DIR.parent / sheet_path.name
        try:
            shutil.copyfile(sheet_path, root_target)
        except OSError:
            pass

    return ScoreResponse(
        job_id=job_id,
        scored_resumes=final_state.get("scored_resumes", []),
        errors=final_state.get("errors", []),
        score_sheet_path=score_sheet_path,
    )
