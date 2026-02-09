from __future__ import annotations

from typing import Annotated, Dict, List, NotRequired, Optional, TypedDict
import csv
import glob
import operator
import os
import shutil

from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader
from docx import Document

from .config import MODEL_NAME


def update_resumes(existing: list, new: list) -> list:
    combined = {item["filename"]: item for item in existing}
    for item in new:
        combined[item["filename"]] = item
    return list(combined.values())


def merge_unique_errors(left: List[str], right: List[str]) -> List[str]:
    return list(set(left + right))


class AgentState(TypedDict):
    job_description: NotRequired[str]
    jd_file_path: str
    jd_scoring_rubric: NotRequired[dict]
    _internal_counter: NotRequired[int]
    _jd_rubric_error: Annotated[list[str], operator.add]
    resume_folder_path: str
    parsed_resumes: Annotated[list[dict], update_resumes]
    current_resume: Optional[Dict]
    scored_resumes: Annotated[list[dict], update_resumes]
    errors: Annotated[list[str], merge_unique_errors]
    current_evaluation: NotRequired[Optional[Dict]]
    current_candidate: NotRequired[Optional[Dict]]
    current_status: NotRequired[Optional[str]]
    structured_resumes: Annotated[list[dict], update_resumes]


class Requirement(BaseModel):
    skill: str = Field(description="The specific skill or qualification required.")
    importance: str = Field(description="Level of importance: 'Required' or 'Preferred'.")
    weightage: int = Field(description="Score value from 1 to 10 based on importance.")


class JDRubric(BaseModel):
    job_title: str
    technical_skills: List[Requirement]
    soft_skills: List[Requirement]
    experience_requirements: List[Requirement]


class JobEntry(BaseModel):
    job_title: str = Field(description="The job title held by the candidate")
    experience_details: str = Field(
        description="Full description of roles, duties, and metrics for this job"
    )


class ExtractedResume(BaseModel):
    candidate_name: str = Field(description="Full name of the candidate")
    email: Optional[str] = Field(description="Contact Email Address")
    total_year_experience: Optional[float] = Field(
        default=None, description="Total years of professional experience"
    )
    experience: Dict[str, JobEntry] = Field(
        default_factory=dict,
        description="Dictionary with keys like 'experience_1', 'experience_2', etc.",
    )
    technical_skills: List[str] = Field(
        default_factory=list, description="List of technical skills"
    )
    projects: List[str] = Field(
        default_factory=list,
        description="List all the projects with title and description",
    )
    education: List[str] = Field(
        default_factory=list, description="List of degrees or certifications"
    )


class SkillMatch(BaseModel):
    skill_name: str
    match_found: bool
    score_assigned: int = Field(
        description="Score from 0 to maximum weightage defined in rubric"
    )
    reasoning: str = Field(
        description="Explanation for the score given based on resume evidence"
    )


class CandidateEvaluation(BaseModel):
    candidate_name: str
    technical_score: List[SkillMatch]
    soft_skill_score: List[SkillMatch]
    experience_score: List[SkillMatch]
    total_weighted_score: float
    gap_analysis: List[str] = Field(
        description="List of critical requirements missing in the resume"
    )


def jdloader_node(state: AgentState) -> AgentState:
    if "errors" not in state:
        state["errors"] = []
    if "_jd_rubric_error" not in state:
        state["_jd_rubric_error"] = []

    path = state.get("jd_file_path", "jd.txt")

    if os.path.isdir(path):
        final_path = os.path.join(path, "jd.txt")
    else:
        final_path = path

    try:
        with open(final_path, "r", encoding="utf-8") as jdtxt:
            content = jdtxt.read()
            state["job_description"] = content
        if not content.strip():
            state["errors"].append("Job Description file is empty")
            return state
    except FileNotFoundError:
        state["errors"].append(f"file not found at {final_path}")
        return state
    except Exception as exc:
        state["errors"].append(f"Error reading file: {str(exc)}")
        return state
    return state


def rubric_generator_node(state: AgentState) -> AgentState:
    current_count = state.get("_internal_counter", 0)
    state["_internal_counter"] = current_count + 1

    llm = ChatGroq(model=MODEL_NAME)
    structured_llm = llm.with_structured_output(JDRubric)

    jd_text = state.get("job_description")
    if not jd_text:
        state["errors"].append("No Job Description found to generate rubric.")
        return state

    prompt = f"""
    Analyze the following Job Description and create a structured scoring rubric.
    Break down requirements into technical skills, soft skills, and experience.
    Assign a weightage (1-10) to each item based on how central it is to the role.

    Job Description:
    {jd_text}
    """

    try:
        rubric_response = structured_llm.invoke(prompt)
        state["jd_scoring_rubric"] = rubric_response.model_dump()
    except Exception as exc:
        state["errors"].append(f"Error generating rubric: {str(exc)}")

    return state


def validation_node(state: AgentState) -> AgentState:
    rubric = state.get("jd_scoring_rubric", {})
    required_keys = [
        "job_title",
        "technical_skills",
        "soft_skills",
        "experience_requirements",
    ]
    missing = [key for key in required_keys if not rubric.get(key)]

    if missing:
        error_msg = f"Validation Failed: Missing rubric sections: {', '.join(missing)}"
        state["_jd_rubric_error"].append(error_msg)
    return state


def should_continue(state: AgentState):
    max_retries = 3
    count = state.get("_internal_counter", 0)
    if not state.get("_jd_rubric_error"):
        return "continue"
    if count < max_retries:
        return "retry"
    return END


@tool
def resume_parser_tool(file_path: str) -> str:
    """Parses the content of the resume file given its local path."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            reader = PdfReader(file_path)
            return " ".join(
                [page.extract_text() for page in reader.pages if page.extract_text()]
            )
        if ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        if ext == ".docx":
            doc = Document(file_path)
            return " ".join([para.text for para in doc.paragraphs])
        return (
            f"Unsupported file type {ext}. Supported files types are PDF, WORD file, TEXT"
        )
    except Exception as exc:
        return f"Error parsing {os.path.basename(file_path)}: {str(exc)}"


def resume_ingestion_node(state: AgentState) -> AgentState:
    if "errors" not in state:
        state["errors"] = []
    state["current_evaluation"] = None
    state["current_candidate"] = None
    state["current_status"] = None

    resume_folder_path = state.get("resume_folder_path")
    if not resume_folder_path or not os.path.exists(resume_folder_path):
        state["errors"].append(f"Folder not found at {resume_folder_path}.")
        return state

    files: list[str] = []
    for ext in ["*.pdf", "*.txt", "*.docx"]:
        files.extend(glob.glob(os.path.join(resume_folder_path, ext)))

    if not files:
        state["errors"].append("No resumes found in the specified folder.")
        return state

    file_path = files[0]
    filename = os.path.basename(file_path)

    text = resume_parser_tool.invoke(file_path)
    if "Error parsing" in text or "Unsupported" in text:
        state["errors"].append(text)
        error_dir = os.path.join(resume_folder_path, "processing_errors")
        os.makedirs(error_dir, exist_ok=True)
        try:
            shutil.move(file_path, os.path.join(error_dir, filename))
        except Exception as exc:
            state["errors"].append(f"Failed to archive bad input {filename}: {str(exc)}")
        return state

    output_directory = os.path.join(resume_folder_path, "parsed_output")
    os.makedirs(output_directory, exist_ok=True)

    state["parsed_resumes"] = [{"filename": filename, "content": text}]
    state["current_resume"] = {"filename": filename, "content": text}

    save_path = os.path.join(output_directory, f"{filename}.txt")
    with open(save_path, "w", encoding="utf-8") as file_handle:
        file_handle.write(text)

    input_archive = os.path.join(resume_folder_path, "input_archive")
    os.makedirs(input_archive, exist_ok=True)
    try:
        shutil.move(file_path, os.path.join(input_archive, filename))
    except Exception as exc:
        state["errors"].append(f"Failed to archive input {filename}: {str(exc)}")

    return state


def structured_resume_extractor_node(state: AgentState) -> AgentState:
    if "structured_resumes" not in state or state["structured_resumes"] is None:
        state["structured_resumes"] = []
    if "errors" not in state:
        state["errors"] = []

    resume_folder_path = state.get("resume_folder_path")
    parsed_dir = os.path.join(resume_folder_path, "parsed_output")
    processed_dir = os.path.join(parsed_dir, "processed_archive")
    os.makedirs(processed_dir, exist_ok=True)

    text_files = glob.glob(os.path.join(parsed_dir, "*.txt"))
    if not text_files:
        return state

    current_file_path = text_files[0]
    filename = os.path.basename(current_file_path)

    try:
        with open(current_file_path, "r", encoding="utf-8") as file_handle:
            content = file_handle.read()

        llm = ChatGroq(model=MODEL_NAME, temperature=0)
        structured_llm = llm.with_structured_output(
            ExtractedResume, method="json_schema"
        )

        prompt = f"""
        Extract professional information from the following resume text.
        For the 'experience' dictionary:
        1. Use keys like 'experience_1', 'experience_2', etc., in chronological order.
        2. For each entry, include the 'job_title' and a detailed 'experience_details'.

        Resume Text:
        {content}
        """
        structured_data = structured_llm.invoke(prompt)

        state["structured_resumes"].append(
            {"filename": filename, "data": structured_data.model_dump()}
        )

        shutil.move(current_file_path, os.path.join(processed_dir, filename))
    except Exception as exc:
        error_msg = f"Extraction failed for {filename}: {str(exc)}"
        state["errors"].append(error_msg)
        error_dir = os.path.join(parsed_dir, "processing_errors")
        os.makedirs(error_dir, exist_ok=True)
        shutil.move(current_file_path, os.path.join(error_dir, filename))

    return state


def check_folder_queue_node(state: AgentState):
    resume_folder_path = state.get("resume_folder_path")
    remaining_files: list[str] = []
    for ext in ["*.pdf", "*.txt", "*.docx"]:
        remaining_files.extend(glob.glob(os.path.join(resume_folder_path, ext)))
    if remaining_files:
        return "next_resume"
    return "complete"


def rubric_matcher_node(state: AgentState) -> AgentState:
    if "scored_resumes" not in state or state["scored_resumes"] is None:
        state["scored_resumes"] = []
    state["current_evaluation"] = None
    state["current_candidate"] = None
    state["current_status"] = None

    rubric = state.get("jd_scoring_rubric")
    if not state.get("structured_resumes"):
        state["errors"].append("No structured resume found to match.")
        return state

    resume_entry = state["structured_resumes"][-1]
    candidate_data = resume_entry["data"]

    llm = ChatGroq(model=MODEL_NAME, temperature=0)
    structured_llm = llm.with_structured_output(
        CandidateEvaluation, method="json_schema"
    )

    prompt = f"""
    You are an experienced HR professional and talent evaluator.
    Evaluate the candidate '{candidate_data['candidate_name']}' based on the Scoring Rubric.

    Scoring Rubric:
    {rubric}

    Candidate Structured Data:
    {candidate_data}

    Instructions:
    1. For each requirement in the rubric, check if the candidate possesses it.
    2. Assign a score for each item up to its defined weightage.
    3. Calculate a final weighted score.
    4. List specific gaps where the candidate does not meet 'Required' importance.
    5. Also give importance to the candidate's experience.
    """

    try:
        evaluation = structured_llm.invoke(prompt)
        eval_dict = evaluation.model_dump()

        state["scored_resumes"].append(
            {"filename": resume_entry["filename"], "evaluation": eval_dict}
        )
        state["current_evaluation"] = {
            "filename": resume_entry["filename"],
            "score": eval_dict["total_weighted_score"],
        }
        state["current_candidate"] = {
            "filename": resume_entry["filename"],
            "candidate_name": candidate_data.get("candidate_name", ""),
            "email": candidate_data.get("email") or "",
        }
    except Exception as exc:
        state["errors"].append(f"Matching failed: {str(exc)}")

    return state


def resume_sorter_node(state: AgentState) -> AgentState:
    eval_data = state.get("current_evaluation")
    if not eval_data:
        return state

    score = eval_data["score"]
    filename = eval_data["filename"]
    base_path = state.get("resume_folder_path")

    if score >= 85:
        target = "Accepted"
    elif 50 <= score < 85:
        target = "Review"
    else:
        target = "Rejected"

    state["current_status"] = target

    src = os.path.join(base_path, "parsed_output", "processed_archive", filename)
    dest_dir = os.path.join(base_path, target)
    os.makedirs(dest_dir, exist_ok=True)

    if not os.path.exists(src):
        state["errors"].append(f"Physical move failed: source not found for {filename}")
        return state

    try:
        shutil.move(src, os.path.join(dest_dir, filename))
    except Exception as exc:
        state["errors"].append(f"Physical move failed: {str(exc)}")

    return state


def spreadsheet_update_node(state: AgentState) -> AgentState:
    candidate = state.get("current_candidate") or {}
    eval_data = state.get("current_evaluation") or {}
    status = state.get("current_status")

    if not candidate or status is None or not eval_data:
        return state

    full_name = (candidate.get("candidate_name") or "").strip()
    name_parts = [part for part in full_name.split(" ") if part]
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[-1] if len(name_parts) > 1 else ""

    email = candidate.get("email") or ""
    score = eval_data.get("score", "")
    filename = candidate.get("filename") or ""

    jd_path = state.get("jd_file_path", "jd.txt")
    if os.path.isdir(jd_path):
        jd_path = os.path.join(jd_path, "jd.txt")
    jd_id = os.path.splitext(os.path.basename(jd_path))[0] or "jd"

    resume_folder_path = state.get("resume_folder_path", ".")
    sheet_dir = os.path.join(resume_folder_path, "score_sheets")
    os.makedirs(sheet_dir, exist_ok=True)
    sheet_path = os.path.join(sheet_dir, f"{jd_id}_scores.csv")

    headers = ["First Name", "Last Name", "Email", "Score", "Status", "Filename"]
    rows: list[dict] = []

    if os.path.exists(sheet_path):
        with open(sheet_path, "r", newline="", encoding="utf-8") as file_handle:
            reader = csv.DictReader(file_handle)
            rows = list(reader)

    updated = False
    for row in rows:
        same_file = filename and row.get("Filename") == filename
        same_email = email and row.get("Email") == email
        if same_file or same_email:
            row.update(
                {
                    "First Name": first_name,
                    "Last Name": last_name,
                    "Email": email,
                    "Score": score,
                    "Status": status,
                    "Filename": filename,
                }
            )
            updated = True
            break

    if not updated:
        rows.append(
            {
                "First Name": first_name,
                "Last Name": last_name,
                "Email": email,
                "Score": score,
                "Status": status,
                "Filename": filename,
            }
        )

    with open(sheet_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("jdloader_node", jdloader_node)
    graph.add_node("rubric_generator_node", rubric_generator_node)
    graph.add_node("validation_node", validation_node)
    graph.add_node("resume_ingestion_node", resume_ingestion_node)
    graph.add_node("structured_resume_extractor_node", structured_resume_extractor_node)
    graph.add_node("rubric_matcher_node", rubric_matcher_node)
    graph.add_node("resume_sorter_node", resume_sorter_node)
    graph.add_node("spreadsheet_update_node", spreadsheet_update_node)

    graph.add_edge(START, "jdloader_node")
    graph.add_edge("jdloader_node", "rubric_generator_node")
    graph.add_edge("rubric_generator_node", "validation_node")
    graph.add_conditional_edges(
        "validation_node",
        should_continue,
        {
            "continue": "resume_ingestion_node",
            "retry": "rubric_generator_node",
            END: END,
        },
    )
    graph.add_edge("resume_ingestion_node", "structured_resume_extractor_node")
    graph.add_edge("structured_resume_extractor_node", "rubric_matcher_node")
    graph.add_edge("rubric_matcher_node", "resume_sorter_node")
    graph.add_edge("resume_sorter_node", "spreadsheet_update_node")
    graph.add_conditional_edges(
        "spreadsheet_update_node",
        check_folder_queue_node,
        {
            "next_resume": "resume_ingestion_node",
            "complete": END,
        },
    )
    return graph.compile()


def run_graph(jd_file_path: str, resume_folder_path: str) -> AgentState:
    graph = build_graph()
    initial_state: AgentState = {
        "jd_file_path": jd_file_path,
        "resume_folder_path": resume_folder_path,
        "parsed_resumes": [],
        "structured_resumes": [],
        "scored_resumes": [],
        "errors": [],
        "_jd_rubric_error": [],
    }
    return graph.invoke(initial_state)
