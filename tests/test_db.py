"""Unit tests for database model formatting."""

from db import format_image_response, row_to_dict


def test_format_image_response_hides_r2_key():
    record = {
        "id": "img_12345",
        "filename": "vacation.png",
        "key": "originals/img_12345/vacation.png",
        "content_type": "image/png",
        "size": 54321,
        "created_at": "2026-10-25T12:00:00Z",
    }
    formatted = format_image_response(record)

    assert formatted == {
        "id": "img_12345",
        "filename": "vacation.png",
        "contentType": "image/png",
        "size": 54321,
        "createdAt": "2026-10-25T12:00:00Z",
    }
    # Crucial security check: internal storage key is NEVER exposed
    assert "key" not in formatted


def test_row_to_dict():
    assert row_to_dict(None) is None

    d = {"id": "1", "filename": "test.jpg"}
    assert row_to_dict(d) == d

    class MockRow:
        id = "2"
        filename = "row.png"
        key = "originals/2/row.png"
        content_type = "image/png"
        size = 100
        created_at = "now"

    converted = row_to_dict(MockRow())
    assert converted["id"] == "2"
    assert converted["filename"] == "row.png"
    assert converted["key"] == "originals/2/row.png"
