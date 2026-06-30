"""Watches WATCH_DIR for new/modified files and converts them to markdown."""
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import POLL_INTERVAL, SUPPORTED_EXTENSIONS, WATCH_DIR
from converter import convert_file
from logger import get_logger

logger = get_logger("watcher")


class _ConversionHandler(FileSystemEventHandler):
    """Reacts to filesystem events and queues files for conversion."""

    def __init__(self, work_queue: "list[Path]", lock: threading.Lock):
        self._queue = work_queue
        self._lock = lock

    def _maybe_queue(self, path_str: str):
        path = Path(path_str)
        if path.is_dir():
            return
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        with self._lock:
            if path not in self._queue:
                self._queue.append(path)
                logger.info("Queued new file: %s", path.name)

    def on_created(self, event):
        if not event.is_directory:
            self._maybe_queue(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._maybe_queue(event.dest_path)


def _scan_existing_files() -> list[Path]:
    """Picks up any files already sitting in WATCH_DIR at startup."""
    found = [
        p for p in WATCH_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if found:
        logger.info("Found %d existing file(s) in watch folder at startup.", len(found))
    return found


def run_watcher(stop_event: threading.Event):
    """
    Main watcher loop. Runs until stop_event is set.
    Designed to run in a background thread alongside the chat loop.
    """
    queue: list[Path] = _scan_existing_files()
    lock = threading.Lock()

    handler = _ConversionHandler(queue, lock)
    observer = Observer()
    observer.schedule(handler, str(WATCH_DIR), recursive=False)
    observer.start()
    logger.info("Watching folder: %s", WATCH_DIR.resolve())

    try:
        while not stop_event.is_set():
            with lock:
                batch = list(queue)
                queue.clear()

            for path in batch:
                convert_file(path)

            time.sleep(POLL_INTERVAL)
    finally:
        observer.stop()
        observer.join()
        logger.info("Watcher stopped.")
