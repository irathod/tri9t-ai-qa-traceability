
from app.services.versioning import match_nodes


def test_matching_preserves_identity_when_section_moves():
    previous = [
        {
            "node_key": "old_1",
            "parent_node_key": None,
            "heading": "3.3 Result Display and Classification",
            "section_number": "3.3",
            "logical_id": "logical_result",
        }
    ]

    current = [
        {
            "node_key": "new_1",
            "parent_node_key": None,
            "heading": "3.3 Result Display and Classification",
            "section_number": "3.3",
        }
    ]

    matches = match_nodes(previous, current)

    assert matches["new_1"] == "logical_result"


def test_duplicate_headings_are_not_guessed():
    previous = [
        {
            "node_key": "old_1",
            "parent_node_key": None,
            "heading": "Error Codes",
            "section_number": None,
            "logical_id": "logical_1",
        },
        {
            "node_key": "old_2",
            "parent_node_key": None,
            "heading": "Error Codes",
            "section_number": None,
            "logical_id": "logical_2",
        },
    ]

    current = [
        {
            "node_key": "new_1",
            "parent_node_key": None,
            "heading": "Error Codes",
            "section_number": None,
        }
    ]

    matches = match_nodes(previous, current)

    assert "new_1" not in matches
