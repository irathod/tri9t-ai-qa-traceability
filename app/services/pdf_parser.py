
"""
PDF parser for the Tri9T AI assignment.

Responsibilities:
- Extract text blocks from PDF pages.
- Identify numbered and unnumbered headings.
- Reconstruct parent-child section relationships.
- Preserve paragraphs and page references.
- Compute stable content hashes for later version comparison.

This is the first parser iteration. Table reconstruction and OCR
will be added after we validate it against the supplied PDFs.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


# Matches headings such as:
# 1. Device Overview
# 1.1 Intended Use
# 2.1.1.1 Battery Life Under Typical Use
NUMBERED_HEADING = re.compile(
    r"^\s*(\d+(?:\.\d+)*\.?)\s+(.+?)\s*$"
)

# Common headings in technical documents.
KNOWN_UNNUMBERED_HEADINGS = {
    "references",
    "appendix",
    "appendices",
    "glossary",
    "index",
}


def normalize_text(text: str) -> str:
    """Normalize text for matching and content hashing."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    """Return a SHA-256 hash of normalized content."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()



def parse_heading(text: str) -> dict[str, Any] | None:
    """
    Identify numbered section headings without treating ordinary
    numbered list items as document sections.
    """
    normalized = normalize_text(text)
    match = NUMBERED_HEADING.match(normalized)

    if not match:
        return None

    number = match.group(1).rstrip(".")
    title = match.group(2).strip()
    parts = number.split(".")

    # Numbered lists such as "1. Normal: ..." are not section headings.
    # A section title should not look like a sentence or list description.
    if len(parts) == 1:
        if ":" in title:
            return None

        # Avoid classifying numbered list items as top-level sections.
        if title.split()[0].lower() in {
            "normal", "elevated", "hypertension", "hypertensive"
        }:
            return None

    if len(title) > 140 or len(title.split()) > 18:
        return None

    return {
        "number": number,
        "title": title,
        "level": len(parts),
        "heading": normalized,
    }



def extract_pdf_lines(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract text lines in page order.

    PyMuPDF supplies text blocks. We retain page numbers and sort
    blocks by their vertical and horizontal positions.

    This is suitable for the first pass; complex tables and columns
    will require more layout-aware processing.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    extracted: list[dict[str, Any]] = []

    try:
        with fitz.open(pdf_path) as document:
            if document.is_encrypted:
                raise ValueError("Encrypted PDFs are not supported.")

            for page_number, page in enumerate(document, start=1):
                blocks = page.get_text("blocks", sort=True)

                for block in blocks:
                    # PyMuPDF block fields:
                    # x0, y0, x1, y1, text, block_no, block_type
                    if len(block) < 7 or block[6] != 0:
                        continue

                    text = block[4].strip()

                    if not text:
                        continue

                    # Split multiline blocks so headings can be found.
                    for line in text.splitlines():
                        line = normalize_text(line)

                        if line:
                            extracted.append({
                                "page": page_number,
                                "text": line,
                            })

    except fitz.FileDataError as exc:
        raise ValueError(
            f"Could not read PDF {pdf_path.name}: {exc}"
        ) from exc

    return extracted


def build_document_tree(
    lines: list[dict[str, Any]],
    document_name: str,
) -> dict[str, Any]:
    """
    Convert extracted lines into a hierarchical section tree.

    Parent selection uses heading depth and document order. When
    numbering skips levels, the closest preceding shallower heading
    becomes the parent.

    Duplicate heading titles are allowed because nodes have unique IDs.
    """
    root: dict[str, Any] = {
        "id": "root",
        "heading": document_name,
        "number": None,
        "level": 0,
        "parent_id": None,
        "page_start": None,
        "content": [],
        "children": [],
    }

    stack = [root]
    node_counter = 0

    for item in lines:
        text = item["text"]
        page = item["page"]
        heading_info = parse_heading(text)

        if heading_info:
            level = heading_info["level"]

            # Pop sections at the same or deeper level.
            while len(stack) > 1 and stack[-1]["level"] >= level:
                stack.pop()

            parent = stack[-1]
            node_counter += 1

            node = {
                "id": f"node_{node_counter}",
                "heading": heading_info["heading"],
                "number": heading_info["number"],
                "title": heading_info["title"],
                "level": level,
                "parent_id": parent["id"],
                "page_start": page,
                "content": [],
                "children": [],
            }

            parent["children"].append(node)
            stack.append(node)
            continue

        # Keep content attached to the current section.
        current = stack[-1]
        current["content"].append({
            "text": text,
            "page": page,
            "content_hash": content_hash(text),
        })

    return root


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """Public entry point for parsing a PDF."""
    lines = extract_pdf_lines(pdf_path)

    tree = build_document_tree(
        lines=lines,
        document_name=pdf_path.stem,
    )

    tree["source_file"] = pdf_path.name
    tree["source_hash"] = content_hash(
        "\n".join(item["text"] for item in lines)
    )

    return tree


def print_tree(
    node: dict[str, Any],
    indent: int = 0,
) -> None:
    """Print headings recursively for debugging."""
    if node["id"] != "root":
        print(
            "  " * indent
            + f"- {node['heading']} "
            + f"(page {node['page_start']})"
        )

    for child in node["children"]:
        print_tree(child, indent + 1)
