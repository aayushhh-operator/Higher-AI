# Higher AI

Higher AI is a FastAPI-based candidate matching prototype that compares candidates against job descriptions and returns ranked matches with lightweight explanations. The current system is intentionally simple: it combines deterministic rules, semantic similarity, and a small amount of domain knowledge to produce a score that is easier to inspect than a black-box ranking model.

## What The System Does

The backend currently:

- Loads candidate data from a CSV source file
- Loads job descriptions from a PDF source file
- Normalizes both into Python dictionaries with a consistent structure
- Persists candidates and jobs into a local PostgreSQL database named `Higher AI`
- Scores each candidate against a selected job description
- Returns a ranked list of matches with structured and plain-English explanations

The frontend is a single `index.html` file that calls the FastAPI API directly.

## High-Level Architecture

The main pieces are:

- [main.py](/D:/Higher%20AI/app/main.py): FastAPI app and API endpoints
- [data_loader.py](/D:/Higher%20AI/app/data_loader.py): source ingestion, normalization, and PostgreSQL sync
- [scorer.py](/D:/Higher%20AI/app/services/scorer.py): scoring pipeline
- [skill_engine.py](/D:/Higher%20AI/app/services/skill_engine.py): simple related-skill expansion
- [embeddings.py](/D:/Higher%20AI/app/services/embeddings.py): sentence embedding similarity
- [explanation.py](/D:/Higher%20AI/app/services/explanation.py): structured and readable explanation helpers
- [index.html](/D:/Higher%20AI/index.html): self-contained frontend

## Data Flow

### Candidate Ingestion

Candidates are loaded from the CSV file under `Data/`. During loading, the system:

- reads each row with `csv.DictReader`
- converts the candidate id and name into strings
- turns parsed skill text into a Python list
- converts experience into a float
- derives a simple `projects` list from the parsed summary field

The normalized candidate shape is:

```python
{
    "id": str,
    "name": str,
    "skills": list[str],
    "experience": float,
    "projects": list[str],
}
```

The full original row is also retained in PostgreSQL as `raw_data` so that normalization can stay simple without losing source detail.

### Job Description Ingestion

Job descriptions are loaded from the PDF file under `Data/`. The current parser:

- extracts text from all PDF pages using `PyPDF2`
- joins the pages into one string
- splits the combined text into two job descriptions
- assigns ids manually as `jd_1` and `jd_2`
- detects a small set of known skills from text
- extracts experience if a `Minimum X years` pattern exists

The normalized JD shape is:

```python
{
    "id": str,
    "title": str,
    "skills": [
        {"name": str, "weight": float, "required": bool}
    ],
    "experience": float,
    "description": str,
}
```

This is intentionally deterministic and easy to debug.

## PostgreSQL Design

The system now writes into your local PostgreSQL database `Higher AI` using two schemas:

- `candidates.candidates`
- `jobs.jobs`

### Why Schemas Instead Of Separate Databases

Earlier iterations were aimed at separate databases, but your current setup uses one database. Schemas are the cleaner fit because they:

- keep job and candidate data logically separated
- live inside one database connection context
- are easier to manage, query, back up, and evolve together

### Persistence Behavior

Whenever the loaders run, they upsert data into PostgreSQL:

- existing rows are updated if the same id appears again
- new rows are inserted automatically
- duplicate rows are not created for the same id

This means the source files remain the source of truth right now, and PostgreSQL acts as the synchronized storage layer.

## Matching Approach

The ranking system is implemented in [scorer.py](/D:/Higher%20AI/app/services/scorer.py). It is built from several small scoring signals instead of one monolithic score.

### 1. Skill Overlap Score

`skill_overlap_score(jd, candidate)` measures direct skill coverage.

It works by:

- taking skill names from `jd["skills"]`
- expanding candidate skills through a small related-skill map
- intersecting JD skills with expanded candidate skills
- dividing the overlap count by the number of JD skills

Formula:

```text
skill_overlap = |JD skills ∩ expanded candidate skills| / |JD skills|
```

This gives a score between `0` and `1`.

### 2. Skill Expansion / Skill Intelligence

`skill_engine.py` adds lightweight adjacency knowledge. Example mappings include:

- `FastAPI -> Backend, Python`
- `Docker -> DevOps, Containerization`
- `Python -> Backend, Scripting`
- `React -> Frontend, JavaScript`
- `PostgreSQL -> SQL, Database`

This allows partial credit for related knowledge. For example, a candidate listing `FastAPI` can receive credit on a JD looking for `Python` or `Backend`.

This is deliberately small and hand-authored. The goal is not completeness; the goal is interpretability.

### 3. Semantic Similarity Score

`semantic_score(jd, candidate)` uses sentence embeddings.

It works by:

- taking the full JD description as text
- joining candidate skills into one string
- embedding both using `SentenceTransformer("all-MiniLM-L6-v2")`
- comparing them with cosine similarity

This captures meaning beyond exact token overlap. For example:

- a candidate may not match a JD term verbatim
- but their skill profile may still be semantically close to the JD language

### 4. Experience Score

Experience is currently a very simple ratio:

```text
experience_score = min(candidate_experience / jd_experience, 1.0)
```

This gives:

- full credit if the candidate meets or exceeds the requested years
- partial credit if the candidate falls short

### 5. Penalty / Bonus Layer

`penalty_bonus(jd, candidate)` adjusts the weighted score.

Penalty:

- `0.1` is subtracted for each required JD skill that is missing from the candidate's raw skill list

Bonus:

- `0.02` is added for each extra candidate skill not explicitly listed in the JD
- the bonus is capped at `0.1`

This is an intentionally opinionated bias:

- missing required skills should matter
- breadth beyond the JD should help, but only a little

### 6. Final Score

`final_score(jd, candidate)` combines all signals:

```text
score =
    0.5 * skill_overlap_score
  + 0.3 * semantic_score
  + 0.2 * experience_score

score = score - penalty + bonus
score = clamp(score, 0.0, 1.0)
```

### Why These Weights

The weights are hand-tuned, not learned.

The reasoning is:

- `0.5` on skill overlap because explicit skill coverage is the strongest current signal
- `0.3` on semantic similarity because wording and meaning matter, but should not dominate direct skills
- `0.2` on experience because years are useful but often noisy and imperfectly comparable

These values are reasonable defaults for an early-stage prototype, not final production-calibrated coefficients.

## Explanations And Transparency

The system exposes two explanation layers.

### Structured Explanation

`structured_explanation(jd, candidate)` returns:

```python
{
    "matched": [...],
    "missing": [...],
    "extra": [...],
}
```

This is simple but important because it makes the score inspectable.

### Plain-English Explanation

`llm_explanation(jd, candidate, structured)` turns the structured result into a readable sentence that explains:

- who the candidate is
- which role they are being compared against
- what they matched
- what they are missing
- which extra skills they bring

Despite the name, this function does not call an LLM. It is currently deterministic string formatting.

## Design Decisions

### 1. Start With Simple, Inspectable Logic

The current system favors logic that can be explained line by line:

- overlap can be inspected
- penalties can be counted
- bonuses can be counted
- experience math is transparent

This makes debugging and stakeholder review much easier than using a purely opaque ranking model from day one.

### 2. Keep Parsing Deterministic

The loaders use fixed parsing heuristics rather than dynamic extraction pipelines. That keeps the prototype:

- repeatable
- predictable
- easier to maintain

The tradeoff is lower recall and less resilience to format changes.

### 3. Use Embeddings As A Supporting Signal, Not The Only Signal

Embeddings are useful but can be hard to reason about in isolation. In this project, semantic similarity is one part of the final score rather than the entire decision.

### 4. Store Raw Source Data Alongside Normalized Data

For candidates, the app stores normalized fields for matching and raw CSV content for auditability. This avoids forcing the matcher to depend on every source column while preserving the original data.

### 5. Upsert Instead Of Blind Insert

The PostgreSQL sync uses `ON CONFLICT DO UPDATE`, which is important because the data loaders may run repeatedly. This makes the sync idempotent enough for local development and repeated API usage.

## Current API Behavior

At the moment, the verified backend routes in this workspace are:

- `GET /`
- `GET /jds`
- `GET /match/{jd_id}`

The frontend was designed to also support a richer detail endpoint:

- `GET /match/{jd_id}/{cand_id}`

but that endpoint is not currently implemented in the FastAPI app in this workspace.

## Known Limitations

### Data Source Limitations

- Candidate data is still sourced from CSV, not entered through the app
- JD data is still sourced from PDF, with hardcoded parsing assumptions
- the project currently assumes only two job descriptions from the PDF

### Skill Intelligence Limitations

- the skill map is tiny and manually curated
- it does not handle synonyms broadly
- it does not understand proficiency level
- it does not model skill recency
- expansion is one-hop only

### Scoring Limitations

- weights are hand-tuned, not learned from hiring outcomes
- the bonus for extra skills can reward irrelevant breadth
- the penalty checks raw candidate skills, not expanded skills
- experience is reduced to a simple year ratio
- no education logic is currently part of backend scoring even though some frontend slots anticipate richer score breakdowns

### Semantic Similarity Limitations

- the embedding model may need an initial download before use
- semantic score compares JD description to joined candidate skills only
- it does not use project descriptions, work history, or richer candidate narrative text

### Parsing Limitations

- PDF extraction is fragile to formatting changes
- JD skills are currently detected from a short hardcoded list
- job ids are assigned manually rather than coming from source metadata

### Database Limitations

- PostgreSQL is currently a synchronized store, not the primary runtime read path
- the app still loads from files first and writes to the database during loader execution
- there is no migration framework yet
- there are no timestamps, versioning fields, or soft-delete mechanics

### API / Product Limitations

- no authentication
- no pagination
- no admin UI for adding candidates or jobs
- no direct create/update/delete APIs for the database-backed entities
- no implemented single-candidate detail match endpoint in the backend at the time of writing

## Why This Approach Still Makes Sense

Even with the limitations above, this design is useful for an early product stage because it gives:

- fast iteration
- explainable rankings
- predictable behavior
- simple local setup
- a clean path to future improvements

It is much easier to improve a visible, inspectable baseline than to debug a sophisticated matching model with no operational transparency.

## Recommended Next Steps

The highest-value next improvements would be:

- move read paths to PostgreSQL so the database becomes the primary store
- add explicit create/update APIs for candidates and jobs
- implement `GET /match/{jd_id}/{cand_id}`
- return a richer backend `score_breakdown` object from the API
- expand skill normalization and synonym handling
- add education scoring only if the source data is reliable enough
- add tests for loader behavior, scoring behavior, and database sync
- introduce migrations for schema evolution

## Running The Project

Install dependencies:

```powershell
venv\Scripts\python -m pip install -r requirements.txt
```

Run the API:

```powershell
venv\Scripts\python -m uvicorn app.main:app --reload
```

Open the frontend:

- Open [index.html](/D:/Higher%20AI/index.html) directly in a browser

## Final Note

Higher AI is currently best understood as an explainable matching prototype rather than a finished hiring system. Its value right now is clarity: you can see how candidates are loaded, how they are scored, why they rank where they do, and where the system still needs stronger data and smarter modeling.
