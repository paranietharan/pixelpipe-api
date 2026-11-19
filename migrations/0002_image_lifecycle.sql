ALTER TABLE images ADD COLUMN state TEXT NOT NULL DEFAULT 'ready'
    CHECK (state IN ('uploading', 'ready', 'deleting'));
CREATE INDEX images_cleanup ON images(state, created_at);
