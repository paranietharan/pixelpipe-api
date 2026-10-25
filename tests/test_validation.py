"""Unit tests for upload and transformation validation."""

import pytest
from errors import BadRequestError
from validation import (
    normalize_content_type,
    resolve_output_format,
    sanitize_filename,
    validate_image_file,
    validate_transform_params,
)


class MockFile:
    def __init__(self, name="photo.jpg", content_type="image/jpeg", size=1024):
        self.name = name
        self.content_type = content_type
        self.size = size


def test_sanitize_filename():
    assert sanitize_filename("photo.jpg") == "photo.jpg"
    assert sanitize_filename("../../../etc/passwd.png") == "passwd.png"
    assert sanitize_filename("hello world!.webp") == "hello_world_.webp"
    assert sanitize_filename("..hidden.gif") == "hidden.gif"
    assert sanitize_filename(None) == "image"
    assert sanitize_filename("") == "image"


def test_normalize_content_type():
    assert normalize_content_type("image/jpeg") == "image/jpeg"
    assert normalize_content_type("image/jpg") == "image/jpeg"
    assert normalize_content_type("IMAGE/PNG; charset=utf-8") == "image/png"
    assert normalize_content_type("image/webp") == "image/webp"
    assert normalize_content_type("image/gif") == "image/gif"
    assert normalize_content_type("image/avif") == "image/avif"
    assert normalize_content_type("") == ""


def test_validate_image_file_success():
    f = MockFile(name="avatar.png", content_type="image/png", size=2048)
    filename, ctype, size = validate_image_file(f)
    assert filename == "avatar.png"
    assert ctype == "image/png"
    assert size == 2048


def test_validate_image_file_missing():
    with pytest.raises(BadRequestError) as exc_info:
        validate_image_file(None)
    assert exc_info.value.code == "FILE_MISSING"

    with pytest.raises(BadRequestError) as exc_info:
        validate_image_file("plain string not a file")
    assert exc_info.value.code == "FILE_MISSING"


def test_validate_image_file_invalid_type():
    f = MockFile(name="doc.pdf", content_type="application/pdf")
    with pytest.raises(BadRequestError) as exc_info:
        validate_image_file(f)
    assert exc_info.value.code == "INVALID_CONTENT_TYPE"


def test_validate_transform_params_success():
    res = validate_transform_params({"width": "800", "height": "600", "fit": "cover", "format": "webp", "quality": "80"})
    assert res["width"] == 800
    assert res["height"] == 600
    assert res["fit"] == "cover"
    assert res["format"] == "webp"
    assert res["quality"] == 80


def test_validate_transform_params_single_dimension():
    # Only width
    res = validate_transform_params({"width": "300"})
    assert res["width"] == 300
    assert res["height"] is None

    # Only height
    res = validate_transform_params({"height": "400"})
    assert res["width"] is None
    assert res["height"] == 400


def test_validate_transform_params_missing_dimensions():
    with pytest.raises(BadRequestError) as exc_info:
        validate_transform_params({"fit": "contain"})
    assert exc_info.value.code == "INVALID_PARAMETER"
    assert "At least one of 'width' or 'height'" in exc_info.value.message


def test_validate_transform_params_invalid_dimensions():
    with pytest.raises(BadRequestError):
        validate_transform_params({"width": "0"})
    with pytest.raises(BadRequestError):
        validate_transform_params({"width": "4001"})
    with pytest.raises(BadRequestError):
        validate_transform_params({"width": "abc"})
    with pytest.raises(BadRequestError):
        validate_transform_params({"height": "-10"})


def test_validate_transform_params_invalid_fit():
    with pytest.raises(BadRequestError) as exc_info:
        validate_transform_params({"width": "100", "fit": "stretch"})
    assert exc_info.value.code == "INVALID_PARAMETER"


def test_validate_transform_params_invalid_format():
    with pytest.raises(BadRequestError) as exc_info:
        validate_transform_params({"width": "100", "format": "bmp"})
    assert exc_info.value.code == "INVALID_PARAMETER"


def test_validate_transform_params_invalid_quality():
    with pytest.raises(BadRequestError):
        validate_transform_params({"width": "100", "quality": "0"})
    with pytest.raises(BadRequestError):
        validate_transform_params({"width": "100", "quality": "101"})


def test_resolve_output_format():
    # Explicit format
    assert resolve_output_format("webp", None) == ("image/webp", False)
    assert resolve_output_format("jpeg", None) == ("image/jpeg", False)
    assert resolve_output_format("png", None) == ("image/png", False)
    assert resolve_output_format("avif", None) == ("image/avif", False)

    # Auto format with Accept headers
    assert resolve_output_format("auto", "image/avif,image/webp,*/*") == ("image/avif", True)
    assert resolve_output_format(None, "image/webp,image/png") == ("image/webp", True)
    assert resolve_output_format("auto", "text/html,image/*") == ("image/jpeg", True)
