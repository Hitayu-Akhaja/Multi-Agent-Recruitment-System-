import { useMemo, useState } from "react";
import PixelTrailBackground from "./PixelTrailBackground.jsx";

const API_BASE =
  import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

const DEFAULT_ERRORS = [];

const formatScore = (value) => {
  if (value === null || value === undefined) return "-";
  if (Number.isNaN(Number(value))) return String(value);
  return Number(value).toFixed(2);
};

export default function App() {
  const [jdText, setJdText] = useState("");
  const [jdFile, setJdFile] = useState(null);
  const [resumeFiles, setResumeFiles] = useState([]);
  const [resumeZip, setResumeZip] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const canSubmit = useMemo(() => {
    const hasJd = Boolean(jdText.trim()) || Boolean(jdFile);
    const hasResumes = resumeFiles.length > 0 || Boolean(resumeZip);
    return hasJd && hasResumes && !isSubmitting;
  }, [jdText, jdFile, resumeFiles, resumeZip, isSubmitting]);

  const resetOutputs = () => {
    setResult(null);
    setError("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    resetOutputs();

    const hasJd = Boolean(jdText.trim()) || Boolean(jdFile);
    const hasResumes = resumeFiles.length > 0 || Boolean(resumeZip);
    if (!hasJd || !hasResumes) {
      setError("Please provide a JD and at least one resume (or a zip).");
      return;
    }

    const formData = new FormData();
    if (jdFile) {
      formData.append("jd_file", jdFile);
    } else {
      formData.append("jd_text", jdText.trim());
    }
    resumeFiles.forEach((file) => formData.append("resumes", file));
    if (resumeZip) {
      formData.append("resumes_zip", resumeZip);
    }

    setIsSubmitting(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/score`, {
        method: "POST",
        body: formData
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail = payload.detail || "Failed to score resumes.";
        throw new Error(detail);
      }
      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="page">
      <PixelTrailBackground />
      <div className="content-layer">
        <header className="hero">
          <div className="hero-copy">
            <p className="eyebrow">AI Resume Scoring</p>
            <h1>
              Score resumes against job descriptions with consistent, structured
              evaluations.
            </h1>
            <p className="subtext">
              Reduce manual screening time and keep every decision traceable with
              LLM + LangGraph workflows.
            </p>
          </div>
          <div className="metrics-card">
            <div className="metric">
              <span className="metric-value">3x</span>
              <span className="metric-label">Faster screening cycles</span>
            </div>
            <div className="metric">
              <span className="metric-value">100%</span>
              <span className="metric-label">Structured outputs</span>
            </div>
            <div className="metric">
              <span className="metric-value">LLM</span>
              <span className="metric-label">Evidence-backed scoring</span>
            </div>
          </div>
        </header>

        <main className="layout">
          <section className="card">
            <div className="card-header">
              <h2>Guided input flow</h2>
              <p>Follow the steps to run a scoring job.</p>
            </div>

            <form className="form" onSubmit={handleSubmit}>
              <div className="step">
                <div className="step-title">
                  <span className="step-number">1</span>
                  Job description
                </div>
                <div className="field">
                  <label>Paste job description</label>
                  <textarea
                    value={jdText}
                    onChange={(event) => setJdText(event.target.value)}
                    placeholder="Paste the job description here..."
                    rows={6}
                  />
                  <span className="hint">Or upload a JD file below.</span>
                </div>
                <div className="field">
                  <label>Upload JD file</label>
                  <input
                    type="file"
                    accept=".txt"
                    onChange={(event) => setJdFile(event.target.files?.[0] || null)}
                  />
                </div>
              </div>

              <div className="step">
                <div className="step-title">
                  <span className="step-number">2</span>
                  Resume upload
                </div>
                <div className="field">
                  <label>Resume files</label>
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.docx,.txt"
                    onChange={(event) =>
                      setResumeFiles(Array.from(event.target.files || []))
                    }
                  />
                  <span className="hint">Add multiple files if needed.</span>
                </div>
                <div className="field">
                  <label>Or upload a zip</label>
                  <input
                    type="file"
                    accept=".zip"
                    onChange={(event) =>
                      setResumeZip(event.target.files?.[0] || null)
                    }
                  />
                  <span className="hint">
                    Zip should contain .pdf, .docx, or .txt resumes.
                  </span>
                </div>
              </div>

              <div className="step">
                <div className="step-title">
                  <span className="step-number">3</span>
                  Run evaluation
                </div>
                <div className="actions">
                  <button type="submit" disabled={!canSubmit}>
                    {isSubmitting ? "Scoring..." : "Run evaluation"}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => {
                      setJdText("");
                      setJdFile(null);
                      setResumeFiles([]);
                      setResumeZip(null);
                      resetOutputs();
                    }}
                  >
                    Clear
                  </button>
                  </div>
                </div>
              </form>

              {error && <div className="alert error">{error}</div>}
              {result?.errors?.length > 0 && (
                <div className="alert warn">
                  <strong>Processing warnings:</strong>
                  <ul>
                    {result.errors.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>

            <section className="card results">
              <div className="card-header">
                <h2>Results</h2>
                <p>Structured scoring output for each candidate.</p>
              </div>

              {!result && (
                <div className="empty-state">
                  <span className="empty-icon">✨</span>
                  <p>No results yet. Submit a scoring job to see output.</p>
                </div>
              )}

              {result && (
                <>
                  <div className="candidate-list">
                    {(result.scored_resumes || DEFAULT_ERRORS).map((item) => (
                      <div className="candidate-card" key={item.filename}>
                        <div className="candidate-header">
                          <div>
                            <div className="candidate-name">
                              {item.evaluation?.candidate_name ||
                                "Unknown candidate"}
                            </div>
                            <div className="candidate-file">{item.filename}</div>
                          </div>
                          <div className="score-pill">
                            {formatScore(item.evaluation?.total_weighted_score)}
                          </div>
                        </div>
                        <div className="gap-list">
                          <span className="gap-title">Skill gaps</span>
                          <ul>
                            {(item.evaluation?.gap_analysis || []).length > 0 ? (
                              item.evaluation.gap_analysis.map((gap) => (
                                <li key={gap}>{gap}</li>
                              ))
                            ) : (
                              <li>No critical gaps found.</li>
                            )}
                          </ul>
                        </div>
                      </div>
                    ))}
                  </div>

                  <details className="raw-output">
                    <summary>View raw JSON</summary>
                    <pre>{JSON.stringify(result, null, 2)}</pre>
                  </details>
                </>
              )}
            </section>
          </main>
        </div>
    </div>
  );
}
