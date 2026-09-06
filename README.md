# Whisper Audio Transcriber

A local-first Tkinter desktop application for transcribing and translating audio and video with OpenAI Whisper. Media files and transcript output remain on the local machine.

## Features

- Batch processing for common audio and video formats.
- Whisper model selection from `tiny` through `large`.
- `transcribe` and `translate` task modes.
- Per-file status, progress reporting, cancellation, and application logging.
- Automatic `Whisper_Transcriptions` output folder beside the first queued input file.

## Requirements

- Python 3.9 or newer.
- FFmpeg installed and available in `PATH`.
- A system capable of running Whisper models. CPU is supported; a compatible GPU can improve performance.

The first model load may download the selected Whisper model. Models are cached in the system temporary directory for later local use.

## Installation

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```bash
python app.py
```

## Project structure

```
.
├── app.py             # Application startup and Tkinter event loop
├── config.py          # Constants, logging, FFmpeg, and model-cache setup
├── transcription.py   # Whisper model loading and batch processing
├── ui.py              # Tkinter window, controls, and user interaction
├── utils.py           # Shared path and transcript-formatting helpers
├── tests/             # Lightweight tests for non-GUI logic
├── requirements.txt   # Runtime dependencies
└── README.md          # Project documentation
```

## Input and output

Supported input extensions are `.mp3`, `.mp4`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.avi`, `.mov`, `.mkv`, and `.webm`. Each transcript is written as UTF-8 plain text with one timestamped segment per line:

```text
[start -> end] text
```

Existing transcript names are preserved by adding `_1`, `_2`, and so on. Logs are written to `transcribing_log.txt` in the working directory.

## Tests

```bash
python -m pytest
```

Runtime Whisper model loading requires the dependencies in requirements.txt and has not been exercised in environments without them.

