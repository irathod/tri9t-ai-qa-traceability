
from app.services.pdf_parser import (
    build_document_tree,
    parse_heading,
)


def test_deep_heading_with_skipped_level():
    """A heading numbered 2.1.1.1 should still be recognized."""
    result = parse_heading("2.1.1.1 Battery Life Under Typical Use")

    assert result is not None
    assert result["number"] == "2.1.1.1"
    assert result["level"] == 4


def test_numbered_classification_is_not_a_heading():
    """A numbered classification item must remain ordinary content."""
    result = parse_heading(
        "1. Normal: systolic < 120 and diastolic < 80"
    )

    assert result is None


def test_duplicate_headings_remain_distinct():
    """Repeated heading names under different sections need unique IDs."""
    lines = [
        {"page": 1, "text": "4. Alarms and Safety Behavior"},
        {"page": 1, "text": "4.2 Error Codes"},
        {"page": 1, "text": "7. Troubleshooting"},
        {"page": 2, "text": "7.1 Error Codes"},
    ]

    tree = build_document_tree(lines, "test_manual")

    all_nodes = []

    def collect(node):
        all_nodes.append(node)
        for child in node["children"]:
            collect(child)

    collect(tree)

    error_nodes = [
        node for node in all_nodes
        if node.get("title") == "Error Codes"
    ]

    assert len(error_nodes) == 2
    assert error_nodes[0]["id"] != error_nodes[1]["id"]
