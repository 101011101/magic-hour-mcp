"""Copies of the files this server uploads to Magic Hour, so the server can read them again.

Magic Hour's uploads are write-only: a `file_path` (api-assets/...) feeds a generation job, but no API hands the
bytes back. Joining, trimming or taking a frame from a user's clip happens on this server with ffmpeg, so the
server keeps its own copy of every file that passes through it, keyed by the file_path Magic Hour gave it.

With BLOB_READ_WRITE_TOKEN set (Vercel Blob), the copy goes to Blob under kept/; else to a local folder
(MAGIC_HOUR_KEPT_DIR, default <tmp>/magic-hour-kept). A file uploaded straight to Magic Hour, around this
server, has no copy: `read` then raises NotKept and the caller tells the host how to pass the file instead.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

import httpx

BLOB_API = "https://blob.vercel-storage.com"


class NotKept(Exception):
    """This server never saw the file's bytes."""


def is_file_path(value: str) -> bool:
    """A Magic Hour upload path, as get_upload_urls returns it (api-assets/<account>/<name>.<ext>)."""
    return value.startswith("api-assets/")


def _key(file_path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", file_path)


def _dir() -> Path:
    return Path(os.getenv("MAGIC_HOUR_KEPT_DIR", Path(tempfile.gettempdir()) / "magic-hour-kept"))


def keep(file_path: str, data: bytes) -> None:
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if token:
        httpx.put(f"{BLOB_API}/kept/{_key(file_path)}", content=data, timeout=120,
                  headers={"authorization": f"Bearer {token}", "x-api-version": "7", "x-add-random-suffix": "0"}
                  ).raise_for_status()
        return
    folder = _dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / _key(file_path)).write_bytes(data)


def read(file_path: str, out: Path) -> Path:
    """Write the kept copy of file_path to out. NotKept when this server has no copy."""
    token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if token:
        headers = {"authorization": f"Bearer {token}", "x-api-version": "7"}
        listed = httpx.get(BLOB_API, params={"prefix": f"kept/{_key(file_path)}", "limit": 1}, headers=headers, timeout=30)
        listed.raise_for_status()
        blobs = listed.json().get("blobs") or []
        if not blobs:
            raise NotKept(file_path)
        response = httpx.get(blobs[0]["url"], timeout=120, follow_redirects=True)
        response.raise_for_status()
        out.write_bytes(response.content)
        return out
    copy = _dir() / _key(file_path)
    if not copy.exists():
        raise NotKept(file_path)
    out.write_bytes(copy.read_bytes())
    return out


def not_kept_message(file_path: str) -> str:
    return (f"This server cannot read {file_path}: it was uploaded straight to Magic Hour, which never hands a file "
            "back. Upload the file with upload_media (its URL, or its bytes as data_base64) and pass the file_path "
            "that returns, or pass a URL of the file. Nothing was charged.")
