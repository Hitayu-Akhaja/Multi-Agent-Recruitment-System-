# Resume Scoring Backend

FastAPI backend that runs the LangGraph resume scoring workflow.

## Setup

1. Create a virtual environment and install dependencies:
   - `pip install -r requirements.txt`
2. Set environment variables:
   - `GROQ_API_KEY` (required for Groq model)
   - `GROQ_MODEL` (optional, defaults to `openai/gpt-oss-safeguard-20b`)
   - `APP_STORAGE_DIR` (optional, defaults to `backend/storage`)

## Run

`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## API

### POST `/api/v1/score`

Multipart form-data:
- `jd_text` (string) or `jd_file` (file)
- `resumes` (file, multiple) or `resumes_zip` (zip file)

Returns:
- `job_id`
- `scored_resumes`
- `errors`
- `score_sheet_path`
