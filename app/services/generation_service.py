
"""LLM-powered QA test generation and JSON persistence."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from pydantic import ValidationError

from app.schemas.generation import QATestCaseOutput

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
STORE_PATH = ROOT_DIR / "data" / "generations.json"
MODEL_NAME = "openai/gpt-oss-120b"


def _read_store() -> dict:
    """Read the JSON generation store."""
    if not STORE_PATH.exists():
        return {"generations": []}

    with STORE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict) or not isinstance(
        data.get("generations"), list
    ):
        raise ValueError("generations.json has an invalid structure.")

    return data


def _write_store(data: dict) -> None:
    """Write JSON atomically to reduce the risk of partial files."""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = STORE_PATH.with_suffix(".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    temporary_path.replace(STORE_PATH)


def generate_test_cases(
    selection_id: int,
    document_id: int,
    source_version: int,
    sections: list[dict],
) -> dict:
    """
    Generate QA ideas from version-pinned section content.

    Each section must include logical_id, heading, body_text,
    and content_hash.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing from .env.")

    if not sections:
        raise ValueError("The selection contains no sections.")

    # Capture the exact source used for this generation.
    source_hashes = {
        str(section["logical_id"]): str(section["content_hash"])
        for section in sections
    }

    source_text = []
    for section in sections:
        source_text.append(
            {
                "node_id": section["logical_id"],
                "heading": section["heading"],
                "content": section["body_text"],
                "content_hash": section["content_hash"],
            }
        )

    prompt = f"""
You are a QA engineer creating test-case ideas from a technical manual.

Use only the supplied manual content. Do not invent product behavior,
requirements, numeric limits, or specifications that are not stated.
If the content is ambiguous, make the uncertainty clear in the test case.

Generate between 3 and 5 distinct QA test cases.

Return a JSON object with this exact structure:
{{
  "test_cases": [
    {{
      "title": "Short test title",
      "objective": "What this test verifies",
      "preconditions": ["Required setup"],
      "steps": ["Action 1", "Action 2"],
      "expected_result": "Expected outcome supported by the manual",
      "priority": "Low"
    }}
  ]
}}

Rules:
- priority must be Low, Medium, or High.
- Include at least one precondition and one step per test.
- Expected results must be grounded in the provided text.
- Do not include Markdown fences or additional text.

Manual sections:
{json.dumps(source_text, ensure_ascii=False)}
"""

    client = Groq(api_key=api_key)
    last_error = None
    validated = None

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return only valid JSON matching the requested "
                            "schema. Never invent manual requirements."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if not content:
                raise ValueError("The model returned an empty response.")

            parsed = json.loads(content)
            validated = QATestCaseOutput.model_validate(parsed)

            # Enforce the allowed priority values.
            for case in validated.test_cases:
                if case.priority not in {"Low", "Medium", "High"}:
                    raise ValueError(
                        f"Invalid priority: {case.priority}"
                    )

            break

        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            last_error = exc

            if attempt == 0:
                prompt += (
                    "\nYour previous response was invalid. Correct the "
                    "JSON structure, include 3-5 complete test cases, "
                    "and use only Low, Medium, or High for priority."
                )

        except Exception as exc:
            # API/network errors are not treated as malformed model output.
            raise RuntimeError(
                f"Groq generation request failed: {type(exc).__name__}: {exc}"
            ) from exc

    if validated is None:
        raise ValueError(
            f"LLM returned invalid test cases after retry: {last_error}"
        )

    record = {
        "generation_id": str(uuid.uuid4()),
        "selection_id": selection_id,
        "document_id": document_id,
        "source_version": source_version,
        "node_ids": list(source_hashes.keys()),
        "content_hashes": source_hashes,
        "test_cases": [
            case.model_dump() for case in validated.test_cases
        ],
        "model": MODEL_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_stale": False,
        "stale_reasons": [],
    }

    store = _read_store()

    # Policy: repeated requests for the same selection reuse its existing
    # generation. This avoids unnecessary LLM calls and duplicate records.
    for existing in store["generations"]:
        if existing["selection_id"] == selection_id:
            return existing

    store["generations"].append(record)
    _write_store(store)

    return record
