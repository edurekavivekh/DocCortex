"""Builds the system prompt (with prompt caching) from all converted markdown docs."""
from pathlib import Path

from config import DOCS_DIR
from logger import get_logger

logger = get_logger("context_builder")


def docs_signature() -> tuple:
    """
    A cheap, fast-to-compute fingerprint of the docs folder's current state
    (which files exist + their mtimes). Used to detect whether a reload is
    needed without re-reading file contents every time.
    """
    md_files = sorted(DOCS_DIR.glob("*.md"))
    return tuple((f.name, f.stat().st_mtime) for f in md_files)


def build_system_blocks() -> list:
    """
    Reads every .md file currently in DOCS_DIR and combines them into a single
    cached system block. Re-call this whenever new docs may have been added.
    """
    md_files = sorted(DOCS_DIR.glob("*.md"))

    if not md_files:
        logger.warning("No markdown documents found in %s yet.", DOCS_DIR)
        combined = "(No reference documents have been loaded yet.)"
    else:
        parts = []
        for f in md_files:
            try:
                content = f.read_text(encoding="utf-8")
                parts.append(f"# Source: {f.name}\n\n{content}")
            except OSError as e:
                logger.error("Could not read %s: %s", f, e)
        combined = "\n\n---\n\n".join(parts)
        logger.info("Loaded %d document(s) into system context.", len(md_files))

    return [
        {
            "type": "text",
            "text": combined,
            "cache_control": {"type": "ephemeral"},
        }
    ]
