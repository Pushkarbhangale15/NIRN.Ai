"""
ocr_ingest/storage.py — raw uploaded file bytes live on disk, keyed by
SHA-256 hash, not in Postgres (large binary blobs don't belong in a
relational row here any more than the FAISS index does -- see
backend/data/'s existing role for corpus artifacts). GrUpload's DB row
stores everything queryable (hash, OCR text, metadata); this module is
purely the hash -> bytes lookup the background pipeline needs to actually
read the file.
"""
import os

_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "gr_uploads")


def _path_for(file_hash: str, file_type: str) -> str:
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    return os.path.join(_UPLOAD_DIR, f"{file_hash}.{file_type}")


def save_upload_bytes(file_hash: str, file_type: str, content: bytes) -> None:
    path = _path_for(file_hash, file_type)
    if os.path.exists(path):
        return  # dedup: byte-identical file already stored under this hash
    with open(path, "wb") as f:
        f.write(content)


def load_upload_bytes(file_hash: str) -> bytes:
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    matches = [f for f in os.listdir(_UPLOAD_DIR) if f.startswith(f"{file_hash}.")]
    if not matches:
        raise FileNotFoundError(f"No stored upload found for hash {file_hash}")
    with open(os.path.join(_UPLOAD_DIR, matches[0]), "rb") as f:
        return f.read()
