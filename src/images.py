import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SEARCHCULTURE_RECORD_MARKER = "/aggregator/edm/"
SEARCHCULTURE_THUMBNAIL_MARKER = "/aggregator/thumbnails/edm-record/"
DEFAULT_MAX_IMAGE_BYTES = 7 * 1024 * 1024
DEFAULT_IMAGE_MIME_TYPE = "image/jpeg"

IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def derive_searchculture_thumbnail_url(record_id):
    record_id = (record_id or "").strip()
    if SEARCHCULTURE_RECORD_MARKER not in record_id:
        return None
    return record_id.replace(
        SEARCHCULTURE_RECORD_MARKER,
        SEARCHCULTURE_THUMBNAIL_MARKER,
        1,
    )


def resolve_record_thumbnail_url(record, record_id):
    for field in ("thumbnail_url", "thumbnail", "image_url", "image", "image_source", "image_src"):
        value = record.get(field) if isinstance(record, dict) else None
        if isinstance(value, str) and value.strip():
            return value.strip()

    return derive_searchculture_thumbnail_url(record_id)


def _clean_mime_type(value):
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _extension_for_mime_type(mime_type):
    return IMAGE_EXTENSIONS.get(mime_type) or mimetypes.guess_extension(mime_type or "") or ".img"


def _safe_cache_stem(record_id, thumbnail_url):
    source = record_id or thumbnail_url
    parsed = urlparse(source)
    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2:
        source = "_".join(path_parts[-2:])
    elif path_parts:
        source = path_parts[-1]

    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("._-")
    return stem[:120] or "thumbnail"


def _find_cached_thumbnail(cache_dir, stem):
    for path in sorted(Path(cache_dir).glob(f"{stem}.*")):
        mime_type = mimetypes.guess_type(path.name)[0] or DEFAULT_IMAGE_MIME_TYPE
        if mime_type.startswith("image/"):
            return {
                "path": path,
                "mime_type": mime_type,
                "bytes": path.stat().st_size,
                "cached": True,
            }
    return None


def download_thumbnail(
    thumbnail_url,
    cache_dir,
    record_id=None,
    timeout=30.0,
    max_bytes=DEFAULT_MAX_IMAGE_BYTES,
):
    if not thumbnail_url:
        raise ValueError("Missing thumbnail URL.")

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_cache_stem(record_id, thumbnail_url)
    cached = _find_cached_thumbnail(cache_path, stem)
    if cached:
        cached["url"] = thumbnail_url
        return cached

    request = Request(
        thumbnail_url,
        headers={"User-Agent": "CulturalMT-Generation/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        mime_type = _clean_mime_type(response.headers.get("Content-Type"))
        if mime_type and not mime_type.startswith("image/"):
            raise ValueError(f"Thumbnail URL returned non-image content type: {mime_type}")

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError(f"Thumbnail is too large: {content_length} bytes")

        data = response.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise ValueError(f"Thumbnail is too large: more than {max_bytes} bytes")
    if not data:
        raise ValueError("Thumbnail URL returned an empty response.")

    mime_type = mime_type or mimetypes.guess_type(thumbnail_url)[0] or DEFAULT_IMAGE_MIME_TYPE
    extension = _extension_for_mime_type(mime_type)
    image_path = cache_path / f"{stem}{extension}"
    image_path.write_bytes(data)

    return {
        "url": thumbnail_url,
        "path": image_path,
        "mime_type": mime_type,
        "bytes": len(data),
        "cached": False,
    }
