# transcription-converter

A lightweight, local Whisper GUI that turns audio/video files into text with optional translation.

## ✨ Features
- Batch transcription for common audio/video formats (mp3, wav, mp4, mkv, etc.).
- Model selection (`tiny` → `large`) for speed/accuracy trade‑offs.
- Optional **translate** task mode for cross‑language output.
- Progress tracking, per‑file status, and detailed logs.
- Automatic output folder: `Whisper_Transcriptions` next to input files.

## 🧰 Requirements
- Python 3.9+
- FFmpeg installed and available in `PATH`
- A machine that can run Whisper models (CPU works; GPU recommended for speed)

## 📦 Install
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## ▶️ Run
```bash
python main_optimized.py
```

## 📁 Project Structure
```
.
├── main_optimized.py      # Main Tkinter GUI application
├── requirements.txt       # Dependencies
├── README.md              # Project overview
```

## 📝 Output
- Output files are written as plain text (`.txt`).
- Each line includes timestamps: `[start -> end] text`.
- Logs are written to `transcribing_log.txt` in the working directory.

## 🛠️ Tips for “making the repo look richer”
If you want your repository to feel more complete (like other open‑source projects), consider:
1. **Add docs:** screenshots, GIFs, usage examples, and troubleshooting.
2. **Add CI:** run lint/tests with GitHub Actions.
3. **Add packaging:** a `pyproject.toml` and versioned releases.
4. **Add tests:** unit tests for file handling and output formatting.
5. **Add license & contribution guide:** makes the repo more professional.

---

If you want, I can help you add CI, tests, or packaging next.
