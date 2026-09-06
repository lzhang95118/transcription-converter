"""Application constants and runtime configuration."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from typing import Optional


MODEL_NAMES = ("tiny", "base", "small", "medium", "large")
TASK_NAMES = ("transcribe", "translate")
SUPPORTED_EXTENSIONS = frozenset(
    {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".flac", ".avi", ".mov", ".mkv", ".webm"}
)
OUTPUT_DIRECTORY_NAME = "Whisper_Transcriptions"
LOG_FILENAME = "transcribing_log.txt"
MODEL_CACHE_DIRECTORY_NAME = "whisper_models_transcriber"
LOG_FORMAT = "%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s"


def configure_logging(log_path: Optional[str] = None) -> str:
    """Configure application logging and return the log file path."""

    resolved_path = os.fspath(log_path) if log_path is not None else os.path.join(os.getcwd(), LOG_FILENAME)
    try:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.basicConfig(filename=resolved_path, level=logging.INFO, format=LOG_FORMAT)
        logging.info("App Started")
        print(f"Logging to: {resolved_path}")

        if getattr(sys, "frozen", False):
            import io

            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
    except Exception as exc:
        print(f"Logging init failed: {exc}")
        logging.basicConfig(level=logging.CRITICAL)
    return resolved_path


def configure_ffmpeg() -> str:
    """Configure pydub to use bundled or PATH-provided FFmpeg."""

    ffmpeg_path = "ffmpeg"
    try:
        from pydub import AudioSegment
        from pydub.utils import which

        if getattr(sys, "frozen", False):
            bundled_root = os.fspath(getattr(sys, "_MEIPASS"))
            ffmpeg_path = os.path.join(bundled_root, "ffmpeg", "bin", "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                raise FileNotFoundError("Bundled ffmpeg not found.")
        else:
            ffmpeg_path = which("ffmpeg") or "ffmpeg"

        AudioSegment.converter = ffmpeg_path
        ffmpeg_directory = os.path.dirname(ffmpeg_path)
        if ffmpeg_directory:
            os.environ["PATH"] = ffmpeg_directory + os.pathsep + os.environ.get("PATH", "")
        logging.info(f"Using ffmpeg at: {ffmpeg_path}")
    except Exception as exc:
        logging.error(f"FFmpeg path setup failed: {exc}")
        try:
            AudioSegment.converter = "ffmpeg"
        except UnboundLocalError:
            pass
    return ffmpeg_path


def configure_model_cache() -> str:
    """Set the cache location used by Whisper and its model dependencies."""

    cache_dir = os.path.join(tempfile.gettempdir(), MODEL_CACHE_DIRECTORY_NAME)
    try:
        os.makedirs(cache_dir, exist_ok=True)
        logging.info(f"Model cache directory: {cache_dir}")
    except Exception as exc:
        logging.error(f"Cache directory error: {exc}")
    return cache_dir


def configure_runtime() -> tuple[str, str]:
    """Configure logging, media conversion, and model caching for the app."""

    log_path = configure_logging()
    configure_ffmpeg()
    cache_dir = configure_model_cache()
    return log_path, cache_dir
