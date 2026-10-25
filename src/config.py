"""Configuration settings for PixelPipe API."""

# Service information
SERVICE_NAME = "pixelpipe-api"
API_PREFIX = "/v1"

# CORS configuration
# Allowed origins for frontend clients. Lock this down to specific domains in production.
ALLOWED_ORIGINS = ["*"]

# Allowed image MIME types for upload
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
}

# Content-type normalization aliases
CONTENT_TYPE_ALIASES = {
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
}

# Transformation constraints
ALLOWED_FITS = {"cover", "contain", "scale-down", "crop"}
ALLOWED_FORMATS = {"jpeg", "png", "webp", "avif", "auto"}

FORMAT_TO_MIME = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "avif": "image/avif",
}

MIN_DIMENSION = 1
MAX_DIMENSION = 4000
MIN_QUALITY = 1
MAX_QUALITY = 100

# Cache-Control headers for transformed images
CACHE_CONTROL_HEADER = "public, max-age=3600, stale-while-revalidate=86400"
