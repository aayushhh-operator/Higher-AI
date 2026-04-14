import csv
import json
import os
import re
from pathlib import Path

import psycopg2
from PyPDF2 import PdfReader


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
CANDIDATES_CSV_PATH = DATA_DIR / "Sample Candidate Data - combined_candidates.csv"
JDS_PDF_PATH = DATA_DIR / "Job Descriptions.pdf"
ENV_PATH = BASE_DIR / ".env"


def _split_csv_value(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_projects(row):
    summary = row.get("parsed_summary", "").strip()
    if not summary:
        return []
    cleaned = summary.strip("{}")
    return [
        item.strip().strip('"')
        for item in cleaned.split('","')
        if item.strip().strip('"')
    ]


def _candidate_payload(row):
    skills_source = row.get("parsed_skills") or ",".join(
        filter(
            None,
            [
                row.get("programming_languages", ""),
                row.get("backend_frameworks", ""),
                row.get("frontend_technologies", ""),
                row.get("mobile_technologies", ""),
            ],
        )
    )
    experience_source = (
        row.get("years_of_experience")
        or row.get("parsed_metadata_calculated_years_experience")
        or 0
    )
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "skills": _split_csv_value(skills_source),
        "experience": float(experience_source),
        "projects": _parse_projects(row),
    }


def _read_env_file():
    values = {}
    if not ENV_PATH.exists():
        return values

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _env_setting(name, default=None):
    return os.getenv(name) or _read_env_file().get(name, default)


def _postgres_settings(database=None):
    return {
        "host": _env_setting("PGHOST", "127.0.0.1"),
        "port": int(_env_setting("PGPORT", "5432")),
        "user": _env_setting("PGUSER", "postgres"),
        "password": _env_setting("PGPASSWORD"),
        "dbname": database or _env_setting("PGDATABASE", "Higher AI"),
    }


def _get_app_connection():
    password = _env_setting("PGPASSWORD")
    if not password:
        return False
    return psycopg2.connect(**_postgres_settings())


def _ensure_storage(connection):
    with connection.cursor() as cursor:
        cursor.execute("CREATE SCHEMA IF NOT EXISTS candidates")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS jobs")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates.candidates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                skills JSONB NOT NULL,
                experience DOUBLE PRECISION NOT NULL,
                projects JSONB NOT NULL,
                raw_data JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs.jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                skills JSONB NOT NULL,
                experience DOUBLE PRECISION NOT NULL,
                description TEXT NOT NULL
            )
            """
        )


def _sync_candidates_to_postgres(candidates, source_rows):
    connection = _get_app_connection()
    if not connection:
        return

    try:
        with connection:
            _ensure_storage(connection)
            with connection.cursor() as cursor:
                for candidate, row in zip(candidates, source_rows):
                    cursor.execute(
                        """
                        INSERT INTO candidates.candidates (id, name, skills, experience, projects, raw_data)
                        VALUES (%s, %s, %s::jsonb, %s, %s::jsonb, %s::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            name = EXCLUDED.name,
                            skills = EXCLUDED.skills,
                            experience = EXCLUDED.experience,
                            projects = EXCLUDED.projects,
                            raw_data = EXCLUDED.raw_data
                        """,
                        (
                            candidate["id"],
                            candidate["name"],
                            json.dumps(candidate["skills"]),
                            candidate["experience"],
                            json.dumps(candidate["projects"]),
                            json.dumps(row),
                        ),
                    )
    finally:
        connection.close()


def _sync_jds_to_postgres(jds):
    connection = _get_app_connection()
    if not connection:
        return

    try:
        with connection:
            _ensure_storage(connection)
            with connection.cursor() as cursor:
                for jd in jds:
                    cursor.execute(
                        """
                        INSERT INTO jobs.jobs (id, title, skills, experience, description)
                        VALUES (%s, %s, %s::jsonb, %s, %s)
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            skills = EXCLUDED.skills,
                            experience = EXCLUDED.experience,
                            description = EXCLUDED.description
                        """,
                        (
                            jd["id"],
                            jd["title"],
                            json.dumps(jd["skills"]),
                            jd["experience"],
                            jd["description"],
                        ),
                    )
    finally:
        connection.close()


def load_candidates():
    source_rows = []
    candidates = []

    with CANDIDATES_CSV_PATH.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            source_rows.append(row)
            candidates.append(_candidate_payload(row))

    try:
        _sync_candidates_to_postgres(candidates, source_rows)
    except psycopg2.Error:
        pass

    return candidates


def _normalize_pdf_text(text):
    text = text.replace("\u25cf", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_experience(text):
    match = re.search(r"Minimum\s+(\d+(?:\.\d+)?)\s+years", text, re.IGNORECASE)
    return float(match.group(1)) if match else 2.0


def _build_skills(text, title):
    skill_specs = []
    ordered_skills = []

    if title == "AI Engineer":
        ordered_skills = [
            ("Python", 0.5, True),
            ("FastAPI", 0.3, True),
            ("RAG", 0.2, False),
            ("Docker", 0.2, False),
        ]
    else:
        ordered_skills = [
            ("Node.js", 0.5, True),
            ("FastAPI", 0.2, False),
            ("Microservices", 0.2, True),
            ("Docker", 0.1, False),
        ]

    for name, weight, required in ordered_skills:
        if name.lower() in text.lower():
            skill_specs.append(
                {"name": name, "weight": float(weight), "required": required}
            )

    return skill_specs


def load_jds():
    with JDS_PDF_PATH.open("rb") as pdf_file:
        reader = PdfReader(pdf_file)
        combined_text = "\n".join((page.extract_text() or "") for page in reader.pages)

    normalized_text = _normalize_pdf_text(combined_text)
    parts = normalized_text.split("Backend Engineer Overview", maxsplit=1)

    ai_text = parts[0].strip()
    backend_text = f"Backend Engineer Overview {parts[1].strip()}" if len(parts) > 1 else ""

    jds = [
        {
            "id": "jd_1",
            "title": "AI Engineer",
            "skills": _build_skills(ai_text, "AI Engineer"),
            "experience": _extract_experience(ai_text),
            "description": ai_text,
        },
        {
            "id": "jd_2",
            "title": "Backend Engineer",
            "skills": _build_skills(backend_text, "Backend Engineer"),
            "experience": _extract_experience(backend_text),
            "description": backend_text,
        },
    ]

    try:
        _sync_jds_to_postgres(jds)
    except psycopg2.Error:
        pass

    return jds


def get_candidates():
    return load_candidates()


def get_jds():
    return load_jds()


def get_jd_by_id(jd_id):
    return next(jd for jd in get_jds() if jd["id"] == jd_id)


def get_candidate_by_id(candidate_id):
    return next(c for c in get_candidates() if c["id"] == candidate_id)
