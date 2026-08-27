"""
PHASE SECURITY — Wave S3.1 — Upload validation (server-authoritative).

The client-supplied Content-Type is NEVER trusted. Every upload is validated by:
  • filename sanitisation (path-traversal, control chars, length)
  • extension allowlist + dangerous-extension / double-extension denylist
  • magic-byte sniffing (filetype) — the REAL type, not the declared one
  • content signature scan to reject HTML / SVG / scripts / executables / archives
  • per-category size limits

`validate_upload()` returns a `SafeUpload` carrying the SERVER-DETERMINED mime,
a sanitised filename, the category, and whether the file may be served `inline`.
Storage + download layers must use THESE values, not the client's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import filetype

# ── size limits (bytes) ──────────────────────────────────────────────────
# PHASE SECURITY S3.1 — limits mandated for BIBI Cars CRM:
#   • photos  → 10 MB
#   • PDF     → 25 MB
#   • other documents (office/text) → 25 MB
MB = 1024 * 1024
SIZE_LIMITS = {
    "image": 10 * MB,
    "pdf": 25 * MB,
    "document": 25 * MB,
}
MAX_ANY = 25 * MB  # hard ceiling regardless of category

# ── extension policy ─────────────────────────────────────────────────────
ALLOWED_EXT = {
    # documents
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "rtf", "odt", "ods", "odp",
    # raster images only (NO svg)
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif",
}

# Anything in here anywhere in the filename (double-extension too) is rejected.
DANGEROUS_EXT = {
    # executables / installers
    "exe", "dll", "com", "bat", "cmd", "msi", "msp", "scr", "cpl", "gadget",
    "app", "dmg", "pkg", "deb", "rpm", "apk", "ipa", "jar", "run", "bin",
    # scripts
    "sh", "bash", "zsh", "ps1", "psm1", "vbs", "vbe", "js", "mjs", "cjs",
    "jse", "wsf", "wsh", "py", "pyc", "rb", "pl", "php", "phtml", "php3",
    "php4", "php5", "asp", "aspx", "jsp", "jspx", "cgi", "lua", "ts",
    # markup / web (XSS vectors)
    "html", "htm", "xhtml", "shtml", "svg", "svgz", "xml", "xsl", "xslt",
    "mht", "mhtml", "hta", "swf",
    # archives (forbidden — zip-bomb / container smuggling)
    "zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz", "lz", "lzma", "cab",
    "iso", "z", "arj", "ace",
    # misc dangerous
    "lnk", "reg", "url", "sql", "jnlp", "scf", "inf", "chm",
}

# ── content signatures that must never pass (regardless of ext / declared) ─
_HTML_SNIFF = re.compile(
    rb"<!doctype\s+html|<html[\s>]|<head[\s>]|<script[\s>]|<svg[\s>]|<\?php|<%@|javascript:",
    re.I,
)
_EXEC_MAGIC = (
    b"MZ",          # PE / DOS executable
    b"\x7fELF",     # ELF
    b"\xca\xfe\xba\xbe",  # Mach-O / Java class
    b"\xfe\xed\xfa",      # Mach-O
    b"#!",          # shebang script
    b"PK\x03\x04",  # raw zip (OOXML handled separately by extension+kind)
    b"Rar!",        # rar
    b"7z\xbc\xaf",  # 7z
    b"\x1f\x8b",    # gzip
)

# server-trusted mime per allowed extension/kind
_INLINE_SAFE_MIME = {
    "application/pdf",
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp",
}

# legacy OLE (doc/xls/ppt) magic
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


@dataclass
class SafeUpload:
    filename: str        # sanitised
    mime: str            # SERVER-determined
    ext: str             # final extension (lower, no dot)
    category: str        # image | pdf | document
    size: int
    inline_safe: bool    # may be served Content-Disposition: inline


class UploadRejected(ValueError):
    """Raised when an upload fails a security check (maps to HTTP 400)."""


def sanitize_filename(name: str) -> str:
    name = (name or "").strip()
    # strip any directory components (path traversal)
    name = name.replace("\\", "/").split("/")[-1]
    # url-decoded traversal markers
    if "%2e" in name.lower() or ".." in name:
        name = name.replace("..", "_")
    # drop control chars + characters unsafe in headers/paths
    name = re.sub(r"[\x00-\x1f\x7f\"'`\r\n\t<>|:*?]", "_", name)
    name = name.strip(". ")
    if not name:
        name = "file"
    return name[:200]


def _all_extensions(filename: str) -> list[str]:
    parts = filename.lower().split(".")
    return [p for p in parts[1:] if p] if len(parts) > 1 else []


def _category_for_ext(ext: str) -> str:
    if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif"}:
        return "image"
    if ext == "pdf":
        return "pdf"
    return "document"


def validate_upload(filename: str, declared_content_type: str, data: bytes) -> SafeUpload:
    if not data:
        raise UploadRejected("empty file")

    size = len(data)
    if size > MAX_ANY:
        raise UploadRejected(f"file exceeds {MAX_ANY // MB} MB limit")

    safe_name = sanitize_filename(filename)

    exts = _all_extensions(safe_name)
    if not exts:
        raise UploadRejected("file must have an extension")

    # double-extension / dangerous extension anywhere in the name
    bad = set(exts) & DANGEROUS_EXT
    if bad:
        raise UploadRejected(f"file type not allowed: .{'/.'.join(sorted(bad))}")

    final_ext = exts[-1]
    if final_ext not in ALLOWED_EXT:
        raise UploadRejected(f"file type not allowed: .{final_ext}")

    # content signature scan — block masqueraded HTML/SVG/script/executable
    head = data[:2048]
    if _HTML_SNIFF.search(head):
        raise UploadRejected("file content looks like HTML/script and is not allowed")
    for sig in _EXEC_MAGIC:
        if head.startswith(sig):
            # PK = zip is the only one legitimately used by OOXML (docx/xlsx/pptx)
            if sig == b"PK\x03\x04" and final_ext in {"docx", "xlsx", "pptx", "odt", "ods", "odp"}:
                break
            raise UploadRejected("file content type is not allowed (binary/executable/archive)")

    category = _category_for_ext(final_ext)
    if size > SIZE_LIMITS.get(category, MAX_ANY):
        raise UploadRejected(
            f"{category} exceeds {SIZE_LIMITS[category] // MB} MB limit"
        )

    # magic-byte detection → server-authoritative mime
    kind = filetype.guess(data)
    detected_mime = kind.mime if kind else None
    detected_ext = kind.extension if kind else None

    if category == "image":
        # detected type MUST be a real raster image consistent with policy
        if not detected_mime or not detected_mime.startswith("image/"):
            raise UploadRejected("file is not a valid image")
        if detected_mime in ("image/svg+xml",) or detected_ext == "svg":
            raise UploadRejected("SVG images are not allowed")
        mime = detected_mime
    elif category == "pdf":
        if detected_mime != "application/pdf":
            raise UploadRejected("file is not a valid PDF")
        mime = "application/pdf"
    else:  # document
        # OOXML (zip-based) or legacy OLE or plain text/csv/rtf
        if final_ext in {"docx", "xlsx", "pptx", "odt", "ods", "odp"}:
            if not (data.startswith(b"PK\x03\x04")):
                raise UploadRejected("invalid office document")
            mime = {
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "odt": "application/vnd.oasis.opendocument.text",
                "ods": "application/vnd.oasis.opendocument.spreadsheet",
                "odp": "application/vnd.oasis.opendocument.presentation",
            }[final_ext]
        elif final_ext in {"doc", "xls", "ppt"}:
            if not data.startswith(_OLE_MAGIC):
                raise UploadRejected("invalid legacy office document")
            mime = "application/msword" if final_ext == "doc" else "application/vnd.ms-office"
        else:  # txt, csv, rtf — text-ish; already passed HTML sniff
            mime = {"txt": "text/plain", "csv": "text/csv", "rtf": "application/rtf"}.get(
                final_ext, "application/octet-stream"
            )

    return SafeUpload(
        filename=safe_name,
        mime=mime,
        ext=final_ext,
        category=category,
        size=size,
        inline_safe=mime in _INLINE_SAFE_MIME,
    )


# ── image-only fast path (admin site-info / blog cover uploads) ───────────
# These endpoints store server-named files, so we don't depend on the
# client filename having a usable extension. The REAL type is decided by
# magic bytes; the declared Content-Type is ignored entirely.
_IMAGE_EXT_BY_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}
_DEFAULT_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def validate_image_upload(
    data: bytes,
    filename: str = "",
    declared_content_type: str = "",
    max_mb: int = 10,
    allowed_mimes: Optional[set] = None,
) -> SafeUpload:
    """Server-authoritative validation for admin IMAGE uploads.

    Ignores the client Content-Type. Enforces (in order):
      • non-empty + size ceiling
      • dangerous / double-extension denylist on the supplied name
      • HTML/script/SVG/executable content-signature scan
      • magic-byte sniffing → must be a real raster image in the allowlist
    Returns a :class:`SafeUpload` whose ``ext``/``mime`` are SERVER-decided.
    """
    if not data:
        raise UploadRejected("empty file")

    size = len(data)
    max_bytes = max_mb * MB
    if size > max_bytes:
        raise UploadRejected(f"image too large (max {max_mb} MB)")

    safe_name = sanitize_filename(filename or "image")

    # reject masqueraded double / dangerous extensions in the supplied name
    bad = set(_all_extensions(safe_name)) & DANGEROUS_EXT
    if bad:
        raise UploadRejected(f"file type not allowed: .{'/.'.join(sorted(bad))}")

    # content-signature scan — block HTML/SVG/script/executable disguises
    head = data[:2048]
    if _HTML_SNIFF.search(head):
        raise UploadRejected("file content looks like HTML/script and is not allowed")
    for sig in _EXEC_MAGIC:
        if head.startswith(sig):
            raise UploadRejected(
                "file content is not a valid image (binary/executable/archive)"
            )

    # magic-byte authoritative detection
    kind = filetype.guess(data)
    detected_mime = kind.mime if kind else None
    if not detected_mime or not detected_mime.startswith("image/"):
        raise UploadRejected("file is not a valid image")
    if detected_mime == "image/svg+xml":
        raise UploadRejected("SVG images are not allowed")

    allowed = allowed_mimes or _DEFAULT_IMAGE_MIMES
    if detected_mime not in allowed:
        raise UploadRejected(f"unsupported image type: {detected_mime}")

    ext = _IMAGE_EXT_BY_MIME.get(detected_mime) or (kind.extension if kind else "img")
    return SafeUpload(
        filename=safe_name,
        mime=detected_mime,
        ext=ext,
        category="image",
        size=size,
        inline_safe=True,
    )


def safe_content_disposition(filename: str, inline_safe: bool) -> str:
    """Build a header-injection-safe Content-Disposition value."""
    fn = sanitize_filename(filename)
    disp = "inline" if inline_safe else "attachment"
    return f'{disp}; filename="{fn}"'
