"""
Production entry point.

Runs a folder watcher in the background (auto-converts any pdf/xlsx/docx/etc.
dropped into the 'incoming' folder to markdown), while the foreground runs an
interactive chat loop against the combined knowledge base.

Usage:
    python main.py
"""
import threading

from claude_client import ask
from context_builder import build_system_blocks, docs_signature
from logger import get_logger
from watcher import run_watcher

logger = get_logger("main")


def main():
    stop_event = threading.Event()
    watcher_thread = threading.Thread(
        target=run_watcher, args=(stop_event,), daemon=True
    )
    watcher_thread.start()

    print("Document watcher running in the background.")
    print("Drop pdf/xlsx/docx/pptx/csv files into the 'incoming' folder — ")
    print("they'll be auto-converted to markdown and picked up automatically")
    print("before your next question. Type 'exit' to quit.\n")

    system_blocks = build_system_blocks()
    last_signature = docs_signature()

    try:
        while True:
            q = input("You: ").strip()

            if not q:
                continue
            if q.lower() == "exit":
                break
            if q.lower() == "reload":
                # still supported manually, but no longer required
                system_blocks = build_system_blocks()
                last_signature = docs_signature()
                print("Knowledge base reloaded.\n")
                continue

            # Auto-refresh: cheap check (filenames + mtimes) before every query.
            # Only rebuilds the (more expensive) system block if something changed.
            current_signature = docs_signature()
            if current_signature != last_signature:
                logger.info("Detected change in docs folder, reloading knowledge base.")
                system_blocks = build_system_blocks()
                last_signature = current_signature
                print("(Knowledge base updated with newly converted document(s).)\n")

            try:
                answer = ask(q, system_blocks)
                print(f"\nClaude: {answer}\n")
            except RuntimeError as e:
                print(f"\n[Error] {e}\n")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        stop_event.set()
        watcher_thread.join(timeout=5)
        logger.info("Application exited cleanly.")


if __name__ == "__main__":
    main()
