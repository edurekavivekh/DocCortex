# Doc Assistant

A document knowledge base that watches a folder for new files, automatically converts them to markdown, and exposes them to Claude through an MCP server (for Claude Desktop) or a direct CLI chat (using the Anthropic API).

## What it does

Drop a PDF, Word doc, Excel sheet, PowerPoint, or CSV into the `incoming/` folder. It gets automatically converted to markdown and stored in `docs/`. From there, you can query the knowledge base either:

- **In Claude Desktop**, via an MCP server that exposes search/read tools over your documents, or
- **In a terminal**, via a standalone chat script that talks directly to the Anthropic API

## Project structure

```
.
├── incoming/          # Drop new files here (pdf, docx, xlsx, pptx, csv)
│   └── _failed/       # Files that failed conversion land here
├── docs/              # Auto-converted markdown files live here
├── logs/              # Rotating application logs + processed-file tracking
├── config.py          # Central configuration (paths, model, retry settings)
├── logger.py          # Shared logging setup (stderr-safe for MCP compatibility)
├── converter.py        # Converts a single file to markdown via markitdown
├── watcher.py          # Watches incoming/ and queues files for conversion
├── context_builder.py  # Builds the cached system prompt from docs/*.md
├── claude_client.py    # Anthropic API wrapper with retry logic
├── main.py              # Standalone CLI chat app (watcher + chat loop)
├── mcp_server.py        # MCP server for Claude Desktop (watcher + tools)
└── requirements.txt
```

## Setup

**1. Create a virtual environment and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

**2. Install FFmpeg** (required by some document conversions)

```bash
brew install ffmpeg        # macOS
winget install ffmpeg      # Windows
```

**3. Add your API key**

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=your-key-here
```

Get a key and add credits at [console.anthropic.com](https://console.anthropic.com/settings/billing).

## Usage

### Option A — Standalone CLI chat

Runs the folder watcher and an interactive chat loop in one process.

```bash
python main.py
```

Drop files into `incoming/` at any time — they're auto-converted, and the knowledge base refreshes automatically before your next question (no restart needed).

Commands:
- Type any question to query your documents
- `reload` — manually force a knowledge base refresh
- `exit` — quit

### Option B — Claude Desktop via MCP

Runs the folder watcher inside an MCP server that Claude Desktop connects to, exposing your documents as tools Claude can call on demand.

**1. Add to your Claude Desktop config:**

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "doc-assistant": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

Use `which python` (with your venv activated) to get the exact path for `command`.

**2. Fully quit and reopen Claude Desktop** (Cmd+Q / close from system tray — not just closing the window).

**3. Start a new chat.** The watcher starts automatically in the background as soon as Claude Desktop launches the server. Drop files into `incoming/` and ask Claude about them — no separate process needed.

Available tools:
- `list_documents()` — see what's in the knowledge base
- `read_document(filename)` — read a specific document in full
- `search_documents(query)` — search across all documents for a term
- `knowledge_base_status()` — check document count and most recent update

## How conversion works

1. A new file appears in `incoming/` (via watcher event or manual drop)
2. The watcher waits for the file size to stop changing (avoids reading a partially-copied file)
3. `markitdown` converts it to markdown, saved as `docs/<filename>.md`
4. A signature (size + modified time) is recorded in `logs/processed_files.json` so the same file isn't reprocessed unnecessarily
5. If conversion fails, the original file is moved to `incoming/_failed/` and the error is logged

## Troubleshooting

**"Your credit balance is too low"** — Add credits at [console.anthropic.com/settings/billing](https://console.anthropic.com/settings/billing). This is separate from any claude.ai subscription.

**MCP server fails to start / "ModuleNotFoundError: No module named 'mcp'"** — The `mcp` package isn't installed in the venv that Claude Desktop is pointing to. Activate the venv and reinstall: `source venv/bin/activate && pip install -r requirements.txt`.

**"Unexpected non-whitespace character after JSON"** — Something is writing plain text to stdout, which corrupts the MCP protocol stream. Check that `.env` exists in the project root (a missing `ANTHROPIC_API_KEY` raises an error at import time that can print to stdout) and that no print statements bypass the stderr-only logger.

**New files in `incoming/` aren't converting** — Confirm a watcher is actually running. If using Option A, check that `main.py` is still open in a terminal. If using Option B, confirm Claude Desktop is open (the watcher only runs while the MCP server process is alive) and check `logs/app.log` for `"Queued new file"` / `"Converting"` entries.

**Conversion fails for a specific file** — Check `incoming/_failed/` and `logs/app.log` for the error. Scanned/image-only PDFs without text layers are a common cause, since `markitdown` doesn't perform OCR by default.

## Logs

All activity is logged to `logs/app.log` (rotating, 5MB per file, 5 backups kept) and mirrored to stderr. `logs/processed_files.json` tracks which files have already been converted to avoid redundant work.
