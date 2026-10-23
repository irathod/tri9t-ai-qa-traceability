# Tri9T AI Document Traceability API

A version-aware document traceability API developed for the Tri9T AI Engineering Internship assignment. The application manages technical manual versions, organizes document sections, tracks content changes, and supports LLM-powered QA test-case generation.

## Features

- PDF ingestion and hierarchical section extraction.
- Document and version management using SQLite.
- Section browsing and search.
- Version comparison and change detection.
- Named selections pinned to a document version.
- Groq-powered QA test-case generation.
- Pydantic validation of generated test cases.
- JSON persistence for generated outputs.
- Content hashes to support change and staleness analysis.

## Technology Stack

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- SQLite
- Groq API
- JSON
- Pytest

## Project Structure

```text
app/
  main.py
  database.py
  models/
  schemas/
  services/
data/
  ct200_manual.pdf
  ct200_manual_v2.pdf
  generations.json
scripts/
tests/
README.md
approach.md
requirements.txt
```

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/irathod/tri9t-ai-qa-traceability.git
cd tri9t-ai-qa-traceability
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the API key

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
```

Replace the placeholder with a valid key. Never commit `.env` or expose API credentials.

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

## Testing

Run the automated tests:

```bash
python -m pytest -q
```

The current development run completed with five passing tests. The suite should be rerun after changes.

## Document Version Workflow

1. Ingest the original CT-200 manual.
2. Ingest the revised manual as a separate version.
3. Browse sections using the document and version endpoints.
4. Compare versions to identify changes.
5. Create a named selection using valid section logical IDs.
6. Generate QA test-case ideas for the selection.
7. Inspect generated records and evaluate whether their source content has changed.

Use the actual endpoint parameters and ingestion commands implemented in the repository.

## QA Generation

The generation service uses the Groq chat-completion API to request structured test cases. It validates the response against Pydantic schemas and retries once when the returned content is malformed. Generated outputs are stored in `data/generations.json` with selection and source-version metadata.

## Design Decisions and Limitations

- SQLite stores document versions, section nodes, and selections.
- A separate JSON file stores generated outputs.
- Content hashes help identify source-content changes.
- Hash-based checks indicate that source content changed; they do not independently prove that a generated test case is semantically incorrect.
- JSON-file persistence is suitable for a local demonstration but requires stronger concurrency and transactional guarantees for production.
- Complex PDF tables, unusual formatting, and ambiguous source text may require additional parser improvements.
- LLM-generated test cases should be reviewed against the source manual.

## Future Improvements

- Complete and expand end-to-end tests for generation, retrieval, and staleness.
- Add more robust PDF table and heading extraction.
- Improve semantic node matching and change explanations.
- Move generated outputs to a dedicated database such as MongoDB.
- Add authentication, concurrency safeguards, deployment configuration, and monitoring.

## Repository

https://github.com/irathod/tri9t-ai-qa-traceability
