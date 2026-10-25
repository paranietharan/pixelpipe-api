# PixelPipe API

PixelPipe is a high-performance image processing and transformation API built on Cloudflare Workers in Python. It provides fast image uploads, metadata tracking, and on-the-fly transformations powered by Cloudflare Images and R2 storage.

---

## Architecture & Bindings

PixelPipe relies on the following Cloudflare bindings:

| Binding Name | Resource Type | Purpose |
|--------------|---------------|---------|
| `IMAGES_BUCKET` | R2 Bucket | Stores original uploaded images. |
| `DB` | D1 Database | Stores image metadata (`id`, `filename`, `key`, `content_type`, `size`, `created_at`). |
| `IMAGES` | Cloudflare Images | Executes dynamic transformations (resizing, transcoding, quality adjustment). |

---

## Prerequisites

- [Node.js](https://nodejs.org/) (v18+) & `npm`
- [uv](https://docs.astral.sh/uv/) Python package manager (v0.13+)
- Cloudflare account with Images transformation access

---

## Local Development Setup

1. **Install Node & Python Dependencies**:
   ```bash
   npm install
   uv sync
   uv run pywrangler sync
   ```

2. **Run D1 Database Migrations Locally**:
   Before running the API locally, execute the migration to create the `images` table and indexes in the local SQLite instance:
   ```bash
   npx wrangler d1 migrations apply DB --local
   ```

3. **Start the Local Development Server**:
   ```bash
   npm run dev
   ```
   *(or `uv run pywrangler dev --port 8787`)*

   The API will be available at `http://localhost:8787`.

4. **Run Unit Tests**:
   ```bash
   uv run pytest
   ```

---

## D1 Migrations

Database schema migrations are stored under `./migrations/`.

- **Create a new migration**:
  ```bash
  npx wrangler d1 migrations create DB <migration_name>
  ```

- **Apply migrations locally**:
  ```bash
  npx wrangler d1 migrations apply DB --local
  ```

- **Apply migrations to remote Cloudflare production database**:
  ```bash
  npx wrangler d1 migrations apply DB --remote
  ```

---

## API Reference & Example Requests

All product endpoints use the `/v1` prefix.

### 1. Health Check
`GET /health`

**Example Request:**
```bash
curl http://localhost:8787/health
```

**Example Response:**
```json
{
  "status": "ok",
  "service": "pixelpipe-api"
}
```

---

### 2. Upload Image
`POST /v1/images`

Uploads an image via `multipart/form-data`. Streams directly into R2 and records metadata in D1.

- **Allowed Formats:** JPEG (`image/jpeg`), PNG (`image/png`), WebP (`image/webp`), GIF (`image/gif`), AVIF (`image/avif`).
- **Required Field:** `file`

**Example Request:**
```bash
curl -X POST http://localhost:8787/v1/images \
  -F "file=@photo.jpg;type=image/jpeg"
```

**Example Response (201 Created):**
```json
{
  "id": "img_6188e4924fa745a49fa3c7e6d8e4f276",
  "filename": "photo.jpg",
  "contentType": "image/jpeg",
  "size": 123456,
  "createdAt": "2026-10-25T13:44:03.988999+00:00"
}
```

---

### 3. Get Image Metadata
`GET /v1/images/:imageId`

Fetches metadata from D1. Internal R2 storage keys and Cloudflare credentials are never exposed.

**Example Request:**
```bash
curl http://localhost:8787/v1/images/img_6188e4924fa745a49fa3c7e6d8e4f276
```

**Example Response (200 OK):**
```json
{
  "id": "img_6188e4924fa745a49fa3c7e6d8e4f276",
  "filename": "photo.jpg",
  "contentType": "image/jpeg",
  "size": 123456,
  "createdAt": "2026-10-25T13:44:03.988999+00:00"
}
```

---

### 4. Transform Image
`GET /v1/images/:imageId/transform`

Reads original image from R2, transforms it on the fly using Cloudflare Images binding, and returns the binary image. Caching headers are automatically applied:
`Cache-Control: public, max-age=3600, stale-while-revalidate=86400`

**Query Parameters:**
- `width` *(optional)*: Integer, 1–4000.
- `height` *(optional)*: Integer, 1–4000.
  *(Note: At least one of `width` or `height` must be supplied).*
- `fit` *(optional)*: `cover`, `contain`, `scale-down`, or `crop`.
- `format` *(optional)*: `jpeg`, `png`, `webp`, `avif`, or `auto` (auto negotiates based on browser `Accept` header).
- `quality` *(optional)*: Integer, 1–100.

**Example Request:**
```bash
curl "http://localhost:8787/v1/images/img_6188e4924fa745a49fa3c7e6d8e4f276/transform?width=800&height=600&fit=cover&format=webp&quality=85" \
  --output transformed.webp
```

---

### 5. Get Image Variants
`GET /v1/images/:imageId/variants`

Returns tracked image variants. Currently returns an empty list placeholder for persistent variant tracking.

**Example Request:**
```bash
curl http://localhost:8787/v1/images/img_6188e4924fa745a49fa3c7e6d8e4f276/variants
```

**Example Response (200 OK):**
```json
{
  "imageId": "img_6188e4924fa745a49fa3c7e6d8e4f276",
  "variants": []
}
```

---

### 6. Delete Image
`DELETE /v1/images/:imageId`

Deletes the original image from R2 and removes the metadata record from D1.

**Example Request:**
```bash
curl -X DELETE http://localhost:8787/v1/images/img_6188e4924fa745a49fa3c7e6d8e4f276
```

**Response:**
`204 No Content` (empty body)

---

## Standard Error Format

All errors return consistent JSON payloads with HTTP error status codes (400, 404, 405, 500):

```json
{
  "error": {
    "code": "IMAGE_NOT_FOUND",
    "message": "Image not found"
  }
}
```

Common error codes:
- `IMAGE_NOT_FOUND`: The requested image was not found (404)
- `INVALID_PARAMETER`: Invalid query parameter value or missing dimensions (400)
- `INVALID_CONTENT_TYPE`: Unsupported file MIME type or missing multipart header (400)
- `FILE_MISSING`: Missing required `file` upload field (400)
- `METHOD_NOT_ALLOWED`: HTTP method not permitted on endpoint (405)
- `NOT_FOUND`: Route does not exist (404)
- `INTERNAL_ERROR`: Unexpected internal error (500)

---

## Adding Authentication Middleware

PixelPipe includes a built-in middleware pipeline in `src/router.py`. To protect endpoints when ready, register an authentication middleware:

```python
from errors import error_response
from router import router

async def auth_middleware(request, env):
    # Skip public health endpoint
    if request.url.endswith("/health"):
        return None

    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return error_response("UNAUTHORIZED", "Missing or invalid authorization header", status=401)

    # Optional: validate token against API keys in KV / D1 / env
    token = auth_header.split(" ")[1]
    # if not is_valid_token(token):
    #     return error_response("FORBIDDEN", "Invalid API token", status=403)

    return None

router.use(auth_middleware)
```

---

## Production Deployment to Cloudflare

### 1. Create Cloudflare Resources

Run the following Wrangler commands or create them in the Cloudflare Dashboard:

1. **Create the R2 Bucket**:
   ```bash
   npx wrangler r2 bucket create pixelpipe-images
   ```

2. **Create the D1 Database**:
   ```bash
   npx wrangler d1 create pixelpipe-db
   ```
   *Note the `database_id` output by Wrangler and update `wrangler.jsonc`:*
   ```jsonc
   "d1_databases": [
     {
       "binding": "DB",
       "database_name": "pixelpipe-db",
       "database_id": "<YOUR_ACTUAL_D1_DATABASE_UUID>",
       "migrations_dir": "migrations"
     }
   ]
   ```

3. **Enable Cloudflare Images Transformations**:
   In the Cloudflare Dashboard:
   - Navigate to **Images** > **Transformations**.
   - Enable transformations for your zone / account.

### 2. Apply Migrations to Remote D1

```bash
npx wrangler d1 migrations apply DB --remote
```

### 3. Deploy the Worker

```bash
npm run deploy
```
*(or `uv run pywrangler deploy`)*
