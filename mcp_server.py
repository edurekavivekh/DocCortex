"""
MCP server exposing the converted markdown knowledge base (docs/) to
MCP-compatible clients (Claude Desktop, or any MCP client via the API).

This does NOT replace converter.py / watcher.py — run those separately
(e.g. via main.py or a dedicated watcher process) to keep docs/ populated.
This server only reads from docs/ and serves it up as tools + resources.

Run with:
    python mcp_server.py

Then point Claude Desktop's config at this script (see README section below).
"""
import threading
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from config import DOCS_DIR
from logger import get_logger
from watcher import run_watcher

logger = get_logger("mcp_server")

_watcher_stop_event = threading.Event()


def _start_watcher_thread():
    """
    Runs the folder watcher (incoming/ -> docs/ conversion) as a daemon
    thread for the lifetime of this MCP server process. Started once at
    import time so it's active as soon as Claude Desktop launches this
    script, with no separate main.py process required.
    """
    thread = threading.Thread(
        target=run_watcher, args=(_watcher_stop_event,), daemon=True
    )
    thread.start()
    logger.info("Background watcher thread started.")


_start_watcher_thread()

mcp = FastMCP("doc-assistant")


def _list_md_files() -> list[Path]:
    return sorted(DOCS_DIR.glob("*.md"))


def _read_doc(name: str) -> Optional[str]:
    """Reads a doc by filename (with or without .md extension)."""
    if not name.endswith(".md"):
        name = f"{name}.md"
    path = DOCS_DIR / name
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        logger.error("Failed to read %s: %s", path, e)
        return None


# ---------------------------------------------------------------------------
# Tools — things Claude can actively call
# ---------------------------------------------------------------------------

@mcp.tool()
def list_documents() -> str:
    """
    List all documents currently available in the knowledge base, with their
    file size and last-modified time. Use this to see what's available before
    deciding which document(s) to read or search.
    """
    files = _list_md_files()
    if not files:
        return "No documents are currently in the knowledge base."

    lines = []
    for f in files:
        stat = f.stat()
        size_kb = stat.st_size / 1024
        lines.append(f"- {f.name} ({size_kb:.1f} KB)")
    return "Available documents:\n" + "\n".join(lines)


@mcp.tool()
def read_document(filename: str) -> str:
    """
    Read the full content of a specific document by filename.
    Use list_documents() first to see available filenames.

    Args:
        filename: The document filename, e.g. "Stern.md" or "Stern"
    """
    content = _read_doc(filename)
    if content is None:
        available = ", ".join(f.name for f in _list_md_files()) or "(none)"
        return f"Document '{filename}' not found. Available documents: {available}"
    return content


@mcp.tool()
def search_documents(query: str, max_results: int = 5) -> str:
    """
    Search across all documents in the knowledge base for lines containing
    the given query (case-insensitive). Returns matching lines with their
    source document and surrounding context, ranked by number of matches
    per document. Use this instead of read_document() when you don't know
    which document has the relevant content, or the knowledge base is large.

    Args:
        query: The search term or phrase to look for.
        max_results: Maximum number of matching snippets to return (default 5).
    """
    files = _list_md_files()
    if not files:
        return "No documents are currently in the knowledge base."

    query_lower = query.lower()
    matches = []

    for f in files:
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - 1)
                end = min(len(lines), i + 2)
                snippet = "\n".join(lines[start:end])
                matches.append((f.name, i + 1, snippet))

    if not matches:
        return f"No matches found for '{query}' in any document."

    matches = matches[:max_results]
    result_parts = [
        f"[{name}, line {line_no}]\n{snippet}"
        for name, line_no, snippet in matches
    ]
    return f"Found {len(matches)} match(es) for '{query}':\n\n" + "\n\n---\n\n".join(result_parts)


@mcp.tool()
def knowledge_base_status() -> str:
    """
    Report on the current state of the knowledge base: how many documents
    are loaded, total size, and most recently updated document. Useful to
    check whether newly uploaded files have finished converting.
    """
    files = _list_md_files()
    if not files:
        return "Knowledge base is empty. Drop files into the watched 'incoming' folder to add documents."

    total_size = sum(f.stat().st_size for f in files)
    most_recent = max(files, key=lambda f: f.stat().st_mtime)

    return (
        f"{len(files)} document(s) loaded, {total_size / 1024:.1f} KB total.\n"
        f"Most recently updated: {most_recent.name}"
    )


# ---------------------------------------------------------------------------
# Resources — addressable content Claude Desktop can browse directly
# ---------------------------------------------------------------------------

@mcp.resource("docs://{filename}")
def get_document_resource(filename: str) -> str:
    """Expose a single document as a browsable MCP resource."""
    content = _read_doc(filename)
    if content is None:
        return f"Document '{filename}' not found."
    return content


if __name__ == "__main__":
    logger.info("Starting MCP server, serving docs from: %s", DOCS_DIR.resolve())
    mcp.run()
