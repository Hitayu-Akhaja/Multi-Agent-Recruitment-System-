# Multi-Agent Recruitment System

An end-to-end resume scoring system that uses an LLM-driven, multi-step workflow to
generate a rubric from a job description, parse resumes, score candidates, and
export results. The backend is FastAPI + LangGraph, and the frontend is React + Vite.

## Features

- Upload a job description (text or file) and multiple resumes (files or a ZIP)
- LLM-generated scoring rubric with structured output
- Structured resume extraction (skills, experience, education, projects)
- LLM based weighted scoring and gap analysis per candidate
- Automatic categorization: Accepted, Review, Rejected
- CSV score sheet export
- Simple UI to run evaluations and view results

## Architecture Overview
![Multi agent recruitment graph](Multi%20agent%20recruitment%20graph.png)
### High-level flow

1. User submits a job description and resumes from the UI
2. Backend creates a job workspace and saves uploaded files
3. LangGraph workflow runs:
   - Load JD
   - Generate rubric
   - Validate rubric (retry on failure)
   - Parse resumes
   - Extract structured resume data
   - Score against rubric
   - Categorize results and write CSV
4. Backend returns JSON results and CSV path
5. UI renders ranked candidates with gap analysis

### Key components

- Backend entry point: `backend/app/main.py`
- Workflow graph: `backend/app/graph.py`
- Storage helper: `backend/app/storage.py`
- Frontend entry point: `frontend/src/main.jsx`
- Main UI: `frontend/src/App.jsx`

## Tech Stack

- **Backend:** Python, FastAPI, LangGraph, LangChain Groq, Pydantic
- **Frontend:** React, Vite
- **Parsing:** PyPDF2, python-docx

## Repo Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── graph.py
│   │   ├── models.py
│   │   ├── config.py
│   │   └── storage.py
│   |
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── PixelTrailBackground.jsx
│   │   └── styles.css
│   ├── package.json
│   └── README.md
|__ requirements.txt
└── README.md
```

## Setup

### Prerequisites

- **Python** 3.10+ recommended
- **Node.js** 18+ recommended
- A **Groq API key**

### Backend setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` (or set environment variables):

```
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-safeguard-20b
APP_STORAGE_DIR=backend/storage
```

Run the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend setup

```bash
cd frontend
npm install
```

Optional `.env` for API base:

```
VITE_API_BASE=http://localhost:8000
```

Run the frontend:

```bash
npm run dev
```

## API

### Health check

```
GET /api/v1/health
```

### Score resumes

```
POST /api/v1/score
```

Multipart form-data:

- `jd_text` (string) OR `jd_file` (file)
- `resumes` (file, multiple) OR `resumes_zip` (zip)

Example using curl:

```bash
curl -X POST http://localhost:8000/api/v1/score \
  -F "jd_text=Senior Backend Engineer with Python and FastAPI" \
  -F "resumes=@resume_1.pdf" \
  -F "resumes=@resume_2.docx"
```

Response (simplified):

```json
{
  "job_id": "20240209_120000_abcd",
  "scored_resumes": [
    {
      "candidate_name": "Jane Doe",
      "total_weighted_score": 87.5,
      "gap_analysis": ["Kafka experience"]
    }
  ],
  "errors": [],
  "score_sheet_path": "backend/storage/.../score_sheets/scores.csv"
}
```

## Scoring Logic

- A rubric is generated from the job description with weighted requirements
- Each resume is parsed and structured (skills, experience, education, projects)
- Skills and experience are matched against the rubric
- Total weighted score is calculated
- Category thresholds:
  - **Accepted:** 85+
  - **Review:** 50-84
  - **Rejected:** below 50

## Output Artifacts

Each run creates a job folder under `backend/storage` (or `APP_STORAGE_DIR`):

```
job_id/
├── jd.txt
├── resumes/
│   ├── score_sheets/
│   │   └── scores.csv
│   ├── Accepted/
│   ├── Review/
│   └── Rejected/
└── output.json
```

Selected output files and categories are also copied to the repo root for convenience.

## Troubleshooting

- **Push errors with GitHub**: pull the remote first (`git pull origin main --rebase`)
- **CORS issues**: frontend is allowed on `http://localhost:5173`
- **No valid resumes**: only `.pdf`, `.docx`, `.txt` are accepted
- **Missing API key**: set `GROQ_API_KEY` in your environment or `.env`

## Security Notes

- Do not commit your `.env` file
- Keep API keys out of version control

## License

Add a license file if you plan to open source this project.
