"""Small, side-effect-free helpers shared by the application."""

from __future__ import annotations

import os
from typing import Iterable, Mapping, Union

from config import OUTPUT_DIRECTORY_NAME, SUPPORTED_EXTENSIONS


PathValue = Union[str, os.PathLike]


def is_supported_media_file(path: PathValue) -> bool:
    """Return whether a path has one of the input media extensions."""

    return os.path.splitext(os.fspath(path))[1].lower() in SUPPORTED_EXTENSIONS


def get_output_directory(input_path: PathValue, directory_name: str = OUTPUT_DIRECTORY_NAME) -> str:
    """Return the output directory next to an input file."""

    input_directory = os.path.dirname(os.fspath(input_path))
    return os.path.join(input_directory, directory_name)


def ensure_output_directory(input_path: PathValue, directory_name: str = OUTPUT_DIRECTORY_NAME) -> str:
    """Create and return the output directory next to an input file."""

    output_directory = get_output_directory(input_path, directory_name)
    os.makedirs(output_directory, exist_ok=True)
    return output_directory


def get_unique_output_path(output_directory: PathValue, source_path: PathValue) -> str:
    """Return a non-overwriting text path for a source media file."""

    source_name = os.path.splitext(os.path.basename(os.fspath(source_path)))[0]
    output_path = os.path.join(os.fspath(output_directory), f"{source_name}.txt")
    counter = 1
    while os.path.exists(output_path):
        output_path = os.path.join(os.fspath(output_directory), f"{source_name}_{counter}.txt")
        counter += 1
    return output_path


def format_timestamp(seconds: float) -> str:
    """Format a transcript timestamp using the application's two-decimal format."""

    return f"{seconds:.2f}"


def format_transcript_segment(start: float, end: float, text: str) -> str:
    """Format one Whisper segment as a timestamped output line."""

    return f"[{format_timestamp(start)} -> {format_timestamp(end)}] {text.strip()}\n"


def format_transcript(segments: Iterable[Mapping[str, object]]) -> str:
    """Format Whisper segments as the application's plain-text transcript."""

    return "".join(
        format_transcript_segment(
            float(segment["start"]),
            float(segment["end"]),
            str(segment["text"]),
        )
        for segment in segments
    )
