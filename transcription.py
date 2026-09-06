"""Whisper model loading and background file processing."""

from __future__ import annotations

import logging
import os
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from utils import format_transcript, get_unique_output_path


StatusCallback = Callable[[str], None]
FileStatusCallback = Callable[[str, str, str], None]
ProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class ProcessingSummary:
    """Result of one batch processing run."""

    final_message: str
    processed_count: int
    total_files: int


class TranscriptionService:
    """Load a Whisper model and process media files without UI dependencies."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        self.model = None
        self.cache_dir = cache_dir

    def load_model(self, model_name: str):
        """Load a named Whisper model and retain it for later processing."""

        import whisper

        model = whisper.load_model(
            model_name,
            download_root=self.cache_dir,
        )
        self.model = model
        return model

    def process_files(
        self,
        file_paths: Sequence[str],
        output_directory: str,
        task: str,
        cancel_event: threading.Event,
        status_callback: Optional[StatusCallback] = None,
        file_status_callback: Optional[FileStatusCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ProcessingSummary:
        """Process a batch, reporting progress through optional callbacks."""

        if self.model is None:
            raise RuntimeError("A Whisper model must be loaded before processing files.")

        files_to_process = list(file_paths)
        total_files = len(files_to_process)
        processed_count = 0

        def report_status(message: str) -> None:
            if status_callback is not None:
                status_callback(message)

        def report_file_status(path: str, status: str, foreground: str) -> None:
            if file_status_callback is not None:
                file_status_callback(path, status, foreground)

        def report_progress(value: int, message: str) -> None:
            if progress_callback is not None:
                progress_callback(value, total_files, message)

        for index, file_path in enumerate(files_to_process):
            if cancel_event.is_set():
                report_status("Processing cancelled by user.\n")
                logging.warning("Processing cancelled by user.")
                break

            filename = os.path.basename(file_path)
            transcript_file = get_unique_output_path(output_directory, file_path)
            output_filename = os.path.basename(transcript_file)

            report_file_status(file_path, "⏱️", "blue")
            report_status(f"Processing [{index + 1}/{total_files}]: {filename}...\n")
            logging.info(f"Processing [{index + 1}/{total_files}]: {file_path}")

            try:
                if not os.path.exists(file_path):
                    logging.warning(f"File not found, skipping: {file_path}")
                    report_file_status(file_path, "❓", "orange")
                    report_status(f"Skipped (Not Found): {filename}\n")
                    continue

                try:
                    from pydub import AudioSegment

                    audio = AudioSegment.from_file(file_path)
                    if audio.duration_seconds < 0.1:
                        logging.warning(
                            f"Audio file seems too short or empty, skipping: {filename} "
                            f"({audio.duration_seconds:.2f}s)"
                        )
                        report_file_status(file_path, "⚠️", "#cc8400")
                        report_status(f"Skipped (Too Short/Empty): {filename}\n")
                        continue
                except Exception as audio_error:
                    logging.warning(
                        f"Could not read audio properties for {filename}, "
                        f"attempting transcription. Error: {audio_error}"
                    )

                logging.info(f"Starting transcription for: {file_path}")
                result = self.model.transcribe(file_path, fp16=False, task=task)

                with open(transcript_file, "w", encoding="utf-8") as transcript:
                    transcript.write(format_transcript(result["segments"]))

                logging.info(f"Transcription saved to: {transcript_file}")
                report_file_status(file_path, "✓", "dark green")
                report_status(f"Success: {filename} -> {output_filename}\n")
            except Exception as exc:
                logging.error(f"Error processing {filename}: {traceback.format_exc()}")
                report_file_status(file_path, "❌", "red")
                report_status(f"ERROR processing {filename}: {exc}\n")
            finally:
                processed_count += 1
                report_progress(processed_count, f"Processed {filename}")

        final_message = "Processing complete." if not cancel_event.is_set() else "Processing cancelled."
        logging.info(final_message)
        return ProcessingSummary(final_message, processed_count, total_files)
