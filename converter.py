"""Handles conversion of incoming documents (pdf, xlsx, docx, etc.) to markdown."""
import json
import shutil
import time
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

from config import DOCS_DIR, PROCESSED_LOG, SETTLE_SECONDS, SUPPORTED_EXTENSIONS
from logger import get_logger

logger = get_logger("converter")

_md_engine = MarkItDown()


def _load_processed() -> dict:
    if PROCESSED_LOG.exists():
        try:
            return json.loads(PROCESSED_LOG.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read processed log, starting fresh: %s", e)
    return {}


def _save_processed(data: dict) -> None:
    try:
        PROCESSED_LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error("Failed to persist processed log: %s", e)


def _file_signature(path: Path) -> str:
    """A cheap signature (size + mtime) to detect whether a file changed."""
    stat = path.stat()
    return f"{stat.st_size}-{int(stat.st_mtime)}"


def is_already_processed(path: Path) -> bool:
    processed = _load_processed()
    return processed.get(str(path)) == _file_signature(path)


def mark_processed(path: Path) -> None:
    processed = _load_processed()
    processed[str(path)] = _file_signature(path)
    _save_processed(processed)


def wait_until_settled(path: Path, settle_seconds: float = SETTLE_SECONDS) -> bool:
    """
    Waits until a file's size stops changing, to avoid reading a file
    that is still being written/copied. Returns False if the file
    disappears while waiting.
    """
    try:
        last_size = -1
        stable_checks = 0
        required_stable_checks = 2

        while stable_checks < required_stable_checks:
            if not path.exists():
                return False
            current_size = path.stat().st_size
            if current_size == last_size:
                stable_checks += 1
            else:
                stable_checks = 0
                last_size = current_size
            time.sleep(settle_seconds / required_stable_checks)
        return True
    except OSError as e:
        logger.warning("Error while waiting for file to settle (%s): %s", path, e)
        return False


def convert_file(path: Path) -> Optional[Path]:
    """
    Convert a single file to markdown and write it into DOCS_DIR.
    Returns the output path on success, or None on failure.
    """
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.debug("Skipping unsupported file type: %s", path.name)
        return None

    if is_already_processed(path):
        logger.info("Already processed, skipping: %s", path.name)
        return None

    if not wait_until_settled(path):
        logger.warning("File disappeared or never settled, skipping: %s", path.name)
        return None

    out_path = DOCS_DIR / f"{path.stem}.md"

    try:
        logger.info("Converting: %s -> %s", path.name, out_path.name)
        result = _md_engine.convert(str(path))

        out_path.write_text(result.text_content, encoding="utf-8")
        mark_processed(path)
        logger.info("Conversion successful: %s", out_path.name)
        return out_path

    except Exception as e:
        logger.error("Conversion failed for %s: %s", path.name, e, exc_info=True)
        _quarantine(path)
        return None


def _quarantine(path: Path) -> None:
    """Move a file that failed conversion into a 'failed' subfolder so it
    doesn't repeatedly clog the pipeline, while preserving it for inspection."""
    try:
        failed_dir = path.parent / "_failed"
        failed_dir.mkdir(exist_ok=True)
        target = failed_dir / path.name
        shutil.move(str(path), str(target))
        logger.info("Moved failed file to quarantine: %s", target)
    except OSError as e:
        logger.error("Could not quarantine file %s: %s", path, e)
