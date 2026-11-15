"""Portfolio uploads: check a file, then save it in the uploading account's own folder.

Checks run in order (3.AI_RULES §13): not empty, size, type (extension and content sniffing),
safe filename, then save. Files go to `data/uploads/<account>/` in the persona folder layout
(a PDF as `cv.pdf`, text and code under `repos/`), so one account never changes another's
portfolio or the shared persona corpus the evals use.
shortcut: the Portfolio server indexes only data/personas/<persona>/, so uploads are stored but
not searched yet; merging an account's folder into its corpus needs account-scoped Portfolio
sessions (Phase 7).
"""

import re
from pathlib import Path

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "data" / "uploads"
ACCOUNT = re.compile(r"^[a-z0-9_]+$")
UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
PDF_MAGIC = b"%PDF-"
MAX_NAME = 80


class UploadRejected(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def safe_name(filename: str) -> str:
    name = UNSAFE.sub("_", Path(filename.replace("\\", "/")).name).strip("._")
    return name[-MAX_NAME:] or "upload"


def check_upload(filename: str, content: bytes, max_bytes: int, suffixes: list[str]) -> str:
    """The file's suffix, after every check passes; raises UploadRejected otherwise."""
    if not content:
        raise UploadRejected("empty_file", "The file is empty.")
    if len(content) > max_bytes:
        raise UploadRejected("file_too_large", f"Files may be at most {max_bytes} bytes.")
    suffix = Path(filename).suffix.lower()
    if suffix not in suffixes:
        raise UploadRejected("unsupported_type", f"Upload one of: {', '.join(suffixes)}.")
    if suffix == ".pdf":
        if not content.startswith(PDF_MAGIC):
            raise UploadRejected("unsupported_type", "The file is not a PDF.")
    else:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UploadRejected("unsupported_type", "Text files must be UTF-8.") from error
    return suffix


def save_upload(account: str, filename: str, content: bytes, max_bytes: int,
                suffixes: list[str], uploads_dir: Path | None = None) -> str:
    """Save a checked upload into the account's folder; returns the path inside it."""
    if not ACCOUNT.match(account):
        raise UploadRejected("invalid_account", "Unknown account.")
    suffix = check_upload(filename, content, max_bytes, suffixes)
    relative = Path("cv.pdf") if suffix == ".pdf" else Path("repos", safe_name(filename))
    target = (uploads_dir or UPLOADS_DIR) / account / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return relative.as_posix()
