"""Route handlers for the PixelPipe API."""

import datetime
import json
import uuid

from config import CACHE_CONTROL_HEADER, SERVICE_NAME
from cors import apply_cors_to_headers
from db import delete_image_by_id, format_image_response, get_image_by_id, insert_image
from errors import BadRequestError, NotFoundError, Response
from validation import (
    parse_query_params,
    resolve_output_format,
    validate_image_file,
    validate_transform_params,
)


def json_response(data: dict, status: int = 200, headers: dict | None = None) -> Response:
    """Helper to return a JSON Response."""
    resp_headers = {"content-type": "application/json"}
    if headers:
        resp_headers.update(headers)
    if hasattr(Response, "from_json"):
        return Response.from_json(data, status=status, headers=resp_headers)
    return Response(json.dumps(data), status=status, headers=resp_headers)


async def health_handler(request, env) -> Response:
    """GET /health - Service health check."""
    return json_response({
        "status": "ok",
        "service": SERVICE_NAME,
    })


async def upload_image_handler(request, env) -> Response:
    """
    POST /v1/images - Upload an image via multipart/form-data.
    Streams image to R2 and records metadata in D1.
    """
    content_type_header = ""
    if hasattr(request, "headers") and hasattr(request.headers, "get"):
        content_type_header = request.headers.get("content-type") or ""

    if "multipart/form-data" not in content_type_header.lower():
        raise BadRequestError(
            code="INVALID_CONTENT_TYPE",
            message="Content-Type must be 'multipart/form-data'",
        )

    # Parse multipart form data
    try:
        if hasattr(request, "form_data"):
            form_data = await request.form_data()
        elif hasattr(request, "formData"):
            form_data = await request.formData()
        else:
            raise BadRequestError("INVALID_REQUEST", "Unable to parse form data from request")
    except Exception as exc:
        if isinstance(exc, BadRequestError):
            raise
        raise BadRequestError("INVALID_REQUEST", f"Failed to parse multipart/form-data: {str(exc)}")

    file_obj = form_data.get("file")
    filename, content_type, size = validate_image_file(file_obj)

    # Generate image ID and R2 storage key
    image_id = f"img_{uuid.uuid4().hex}"
    r2_key = f"originals/{image_id}/{filename}"

    # Extract stream if available to avoid loading the entire file into memory
    upload_body = file_obj
    if hasattr(file_obj, "js_object"):
        js_file = file_obj.js_object
        if hasattr(js_file, "stream") and callable(js_file.stream):
            upload_body = js_file.stream()
        else:
            upload_body = js_file

    # Save to R2 bucket
    await env.IMAGES_BUCKET.put(
        r2_key,
        upload_body,
        httpMetadata={"contentType": content_type},
    )

    # Save metadata in D1 database
    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = await insert_image(
        env.DB,
        id=image_id,
        filename=filename,
        key=r2_key,
        content_type=content_type,
        size=size,
        created_at=created_at,
    )

    return json_response(format_image_response(record), status=201)


async def get_image_handler(request, env, image_id: str) -> Response:
    """GET /v1/images/:imageId - Fetch image metadata."""
    record = await get_image_by_id(env.DB, image_id)
    if not record:
        raise NotFoundError("IMAGE_NOT_FOUND", "Image not found")

    return json_response(format_image_response(record), status=200)


async def delete_image_handler(request, env, image_id: str) -> Response:
    """DELETE /v1/images/:imageId - Delete original from R2 and metadata from D1."""
    record = await get_image_by_id(env.DB, image_id)
    if not record:
        raise NotFoundError("IMAGE_NOT_FOUND", "Image not found")

    # Delete original object from R2 bucket
    await env.IMAGES_BUCKET.delete(record["key"])

    # Delete metadata from D1 database
    await delete_image_by_id(env.DB, image_id)

    # Return HTTP 204 No Content
    return Response(None, status=204)


async def transform_image_handler(request, env, image_id: str) -> Response:
    """
    GET /v1/images/:imageId/transform - Dynamically transform image with Cloudflare Images binding.
    """
    # Validate query parameters
    query_params = parse_query_params(getattr(request, "url", ""))
    params = validate_transform_params(query_params)

    # Ensure image exists in D1
    record = await get_image_by_id(env.DB, image_id)
    if not record:
        raise NotFoundError("IMAGE_NOT_FOUND", "Image not found")

    # Retrieve source image stream from R2
    r2_object = await env.IMAGES_BUCKET.get(record["key"])
    if not r2_object or not hasattr(r2_object, "body"):
        raise NotFoundError("IMAGE_NOT_FOUND", "Original image not found in storage")

    # Pass original image stream to IMAGES binding
    handle = env.IMAGES.input(r2_object.body)

    # Apply transformations: width, height, fit
    transform_opts = {}
    if params["width"] is not None:
        transform_opts["width"] = params["width"]
    if params["height"] is not None:
        transform_opts["height"] = params["height"]
    if params["fit"] is not None:
        transform_opts["fit"] = params["fit"]

    if transform_opts:
        handle = handle.transform(transform_opts)

    # Resolve output format and quality
    accept_header = ""
    if hasattr(request, "headers") and hasattr(request.headers, "get"):
        accept_header = request.headers.get("accept") or ""

    output_format, is_auto = resolve_output_format(
        params["format"],
        accept_header=accept_header,
        original_content_type=record["content_type"],
    )

    output_opts = {"format": output_format}
    if params["quality"] is not None:
        output_opts["quality"] = params["quality"]

    output_handle = await handle.output(output_opts)

    # Prepare response headers
    response_headers = {
        "Cache-Control": CACHE_CONTROL_HEADER,
    }
    if is_auto:
        response_headers["Vary"] = "Accept"

    apply_cors_to_headers(response_headers, request)

    # Generate response directly from Images handle
    transformed_response = output_handle.response({"headers": response_headers})
    return transformed_response


async def variants_handler(request, env, image_id: str) -> Response:
    """
    GET /v1/images/:imageId/variants - List variants for an image.
    TODO: Persistent variant tracking will be added later.
    Currently returns an empty list once image existence is verified.
    """
    record = await get_image_by_id(env.DB, image_id)
    if not record:
        raise NotFoundError("IMAGE_NOT_FOUND", "Image not found")

    # Empty variants list for now with placeholder for persistent variant tracking
    return json_response({
        "imageId": image_id,
        "variants": [],
    }, status=200)
