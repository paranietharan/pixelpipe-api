import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from db import get_image_by_id, insert_image, reconcile_images
from handlers import delete_image_handler


class Database:
    def __init__(self):
        self.sql = sqlite3.connect(":memory:")
        self.sql.row_factory = sqlite3.Row
        for migration in sorted((Path(__file__).parents[1] / "migrations").glob("*.sql")):
            self.sql.executescript(migration.read_text())

    def prepare(self, query):
        class Statement:
            args = ()

            def bind(stmt, *args):
                stmt.args = args
                return stmt

            async def first(stmt, column=None):
                row = self.sql.execute(query, stmt.args).fetchone()
                if row is None:
                    return None
                return row[column] if column else dict(row)

            async def run(stmt):
                self.sql.execute(query, stmt.args)

            async def raw(stmt):
                return self.sql.execute(query, stmt.args).fetchall()

        return Statement()


@pytest.mark.asyncio
async def test_interrupted_upload_and_delete_are_recoverable():
    db = Database()
    bucket = SimpleNamespace(delete=AsyncMock())
    env = SimpleNamespace(DB=db, IMAGES_BUCKET=bucket)
    for image in ("partial", "published"):
        await insert_image(db, image, "a.png", image, "image/png", 8, "2000-01-01")
    assert await get_image_by_id(db, "partial") is None
    db.sql.execute("UPDATE images SET state='ready' WHERE id='published'")
    bucket.delete.side_effect = OSError("temporary")
    with pytest.raises(OSError):
        await delete_image_handler(None, env, "published")
    assert await get_image_by_id(db, "published") is None
    bucket.delete.side_effect = None
    await reconcile_images(env)
    assert db.sql.execute("SELECT count(*) FROM images").fetchone()[0] == 0
    assert (await delete_image_handler(None, env, "published")).status == 204
