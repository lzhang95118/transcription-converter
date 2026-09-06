"""Application entry point for the Whisper Audio Transcriber."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

from config import configure_runtime
from ui import WhisperTranscriberApp


def main() -> None:
    """Configure the runtime and start the Tkinter event loop."""

    log_path, cache_dir = configure_runtime()
    root = None
    application = None
    try:
        root = tk.Tk()
        application = WhisperTranscriberApp(root, cache_dir=cache_dir)
        root.mainloop()
    except Exception as exc:
        logging.critical("Unhandled exception", exc_info=True)
        try:
            messagebox.showerror("Fatal Error", f"Critical error:\n{exc}\nCheck log: {log_path}")
        except Exception as messagebox_error:
            print(f"FATAL ERROR: {exc}\nCould not show error message: {messagebox_error}")
    finally:
        logging.info("App Closed")
        logging.shutdown()
        if application is not None:
            application.cancel_flag.set()


if __name__ == "__main__":
    main()
