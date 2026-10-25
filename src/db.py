"""D1 database operations and record formatters for image metadata."""


def format_image_response(record: dict) -> dict:
    """
    Format internal database record into public API response shape.
    R2 object key is intentionally omitted to maintain internal security.
    """
    return {
        "id": record["id"],
        "filename": record["filename"],
        "contentType": record["content_type"],
        "size": record["size"],
        "createdAt": record["created_at"],
    }


def row_to_dict(row) -> dict | None:
    """Safely convert D1 query row (dict, JsDict, or JsProxy) into standard Python dict."""
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)

    # In case the row is a JsProxy or object with attribute/item access
    keys = ["id", "filename", "key", "content_type", "size", "created_at"]
    d = {}
    for k in keys:
        if hasattr(row, k):
            d[k] = getattr(row, k)
        elif hasattr(row, "get") and callable(row.get):
            d[k] = row.get(k)
        elif hasattr(row, "__getitem__"):
            try:
                d[k] = row[k]
            except (KeyError, IndexError, TypeError):
                pass
    return d


async def insert_image(db, id: str, filename: str, key: str, content_type: str, size: int, created_at: str) -> dict:
    """Insert a new image metadata record into D1."""
    query = """
    INSERT INTO images (id, filename, key, content_type, size, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """
    await db.prepare(query).bind(id, filename, key, content_type, size, created_at).run()
    return {
        "id": id,
        "filename": filename,
        "key": key,
        "content_type": content_type,
        "size": size,
        "created_at": created_at,
    }


async def get_image_by_id(db, id: str) -> dict | None:
    """Fetch an image metadata record by ID."""
    query = "SELECT id, filename, key, content_type, size, created_at FROM images WHERE id = ?"
    row = await db.prepare(query).bind(id).first()
    return row_to_dict(row)


async def delete_image_by_id(db, id: str) -> bool:
    """Delete an image metadata record by ID."""
    query = "DELETE FROM images WHERE id = ?"
    await db.prepare(query).bind(id).run()
    return True
