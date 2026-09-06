"""Tkinter user interface for the Whisper transcriber."""

from __future__ import annotations

import logging
import os
import threading
import tkinter as tk
import traceback
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

from config import MODEL_NAMES, TASK_NAMES, OUTPUT_DIRECTORY_NAME
from transcription import TranscriptionService
from utils import ensure_output_directory


class WhisperTranscriberApp:
    """Main window and user interaction for the desktop transcriber."""

    def __init__(
        self,
        root: tk.Tk,
        service: Optional[TranscriptionService] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.cancel_flag = threading.Event()
        self.file_paths = []
        self.model_loaded = False
        self.model = None
        self.input_dir = None
        self.transcription_dir = None
        self.file_widgets: Dict[str, Dict[str, Any]] = {}
        self.process_thread = None
        self.load_thread = None
        self.service = service or TranscriptionService(cache_dir=cache_dir)

        self.setup_ui()
        self.model_var.set("base")
        self.root.after(100, self.load_model)

    def setup_ui(self) -> None:
        self.root.title("Whisper Audio Transcriber")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)
        self.root.configure(bg="#f2f2f2")

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.style.configure("Card.TFrame", background="#ffffff", borderwidth=1, relief="solid")
        self.style.configure("TFrame", background="#f9f9f9")
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        self.style.map("TButton", background=[("active", "#d9d9d9")])
        self.style.configure(
            "Danger.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=6,
            foreground="#a60000",
            background="#ffe0e0",
        )
        self.style.map("Danger.TButton", background=[("active", "#ffcccc")])
        self.style.configure("TCombobox", font=("Segoe UI", 10), padding=5)
        self.style.configure("TScrollbar", troughcolor="#f0f0f0", background="#c0c0c0")
        self.style.configure("TProgressbar", troughcolor="#e0e0e0", background="#0078d4")

        title = tk.Label(
            self.root,
            text="🎧 Whisper Audio Transcriber",
            font=("Segoe UI", 18, "bold"),
            bg="#f2f2f2",
            foreground="#333",
        )
        title.pack(pady=(15, 10))

        paned_window = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            sashrelief=tk.RAISED,
            bg="#d0d0d0",
            sashwidth=6,
        )
        paned_window.pack(fill="both", expand=True, padx=15, pady=10)

        left_frame = ttk.Frame(paned_window, style="Card.TFrame", padding=10)
        paned_window.add(left_frame, stretch="always", minsize=300)

        ttk.Label(left_frame, text="📋 Processing Log", font=("Segoe UI", 12, "bold")).pack(
            pady=(0, 5), anchor="w"
        )
        text_frame = ttk.Frame(left_frame)
        text_frame.pack(fill="both", expand=True)

        self.file_status = tk.Text(
            text_frame,
            height=10,
            width=40,
            bg="#ffffff",
            wrap="word",
            font=("Consolas", 10),
            bd=1,
            relief="solid",
            state="disabled",
            padx=5,
            pady=5,
        )
        self.file_status.pack(side="left", fill="both", expand=True)

        file_scrollbar = ttk.Scrollbar(text_frame, command=self.file_status.yview, style="TScrollbar")
        file_scrollbar.pack(side="right", fill="y")
        self.file_status.config(yscrollcommand=file_scrollbar.set)

        right_frame = ttk.Frame(paned_window, style="Card.TFrame", padding=10)
        paned_window.add(right_frame, stretch="never", minsize=350)

        control_container = ttk.Frame(right_frame)
        control_container.pack(anchor="nw", fill="x")

        ttk.Label(control_container, text="⚙️ Controls", font=("Segoe UI", 12, "bold")).pack(
            pady=(0, 10), anchor="w"
        )

        task_frame = ttk.Frame(control_container)
        task_frame.pack(fill="x", pady=(5, 5))
        ttk.Label(task_frame, text="Task:", font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        self.task_var = tk.StringVar(value=TASK_NAMES[0])
        self.task_dropdown = ttk.Combobox(
            task_frame,
            textvariable=self.task_var,
            values=TASK_NAMES,
            state="readonly",
            width=15,
        )
        self.task_dropdown.pack(side="left", fill="x", expand=True)

        model_frame = ttk.Frame(control_container)
        model_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(model_frame, text="Model:", font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=MODEL_NAMES,
            state="readonly",
            width=15,
            style="TCombobox",
        )
        self.model_dropdown.pack(side="left", fill="x", expand=True)
        self.model_dropdown.bind("<<ComboboxSelected>>", lambda _event: self.load_model())

        self.model_status = ttk.Label(
            control_container,
            text="Model status: Initializing...",
            foreground="gray",
            font=("Segoe UI", 9),
        )
        self.model_status.pack(anchor="w", pady=(0, 10), fill="x")

        button_frame = ttk.Frame(control_container)
        button_frame.pack(fill="x", pady=5)
        self.select_button = ttk.Button(
            button_frame,
            text="📂 Select Files",
            command=self.select_files,
            state=tk.DISABLED,
            width=18,
        )
        self.select_button.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.start_button = ttk.Button(
            button_frame,
            text="▶️ Start",
            command=self.start_processing,
            state=tk.DISABLED,
            width=18,
        )
        self.start_button.pack(side="left", fill="x", expand=True)

        self.cancel_button = ttk.Button(
            control_container,
            text="❌ Close Application",
            command=self.on_closing,
            style="Danger.TButton",
        )
        self.cancel_button.pack(pady=(8, 0), fill="x")

        ttk.Separator(control_container, orient="horizontal").pack(fill="x", pady=15)
        self.progress_label = ttk.Label(control_container, text="", font=("Segoe UI", 9))
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(
            control_container,
            length=200,
            mode="determinate",
            style="TProgressbar",
        )
        self.progress_bar.pack(pady=(2, 10), fill="x")

        ttk.Label(right_frame, text="📄 File Queue", font=("Segoe UI", 12, "bold")).pack(
            pady=(15, 5), anchor="w"
        )

        status_frame_container = ttk.Frame(right_frame, relief="groove", borderwidth=1)
        status_frame_container.pack(fill="both", expand=True)

        self.checkbox_canvas = tk.Canvas(status_frame_container, bg="#ffffff", highlightthickness=0, bd=0)
        self.checkbox_scrollbar = ttk.Scrollbar(
            status_frame_container,
            orient="vertical",
            command=self.checkbox_canvas.yview,
            style="TScrollbar",
        )
        self.checkbox_scrollable_frame = ttk.Frame(self.checkbox_canvas, style="Card.TFrame")
        self.checkbox_scrollable_frame.bind(
            "<Configure>",
            lambda _event: self.checkbox_canvas.configure(
                scrollregion=self.checkbox_canvas.bbox("all")
            ),
        )
        self.canvas_window = self.checkbox_canvas.create_window(
            (0, 0), window=self.checkbox_scrollable_frame, anchor="nw"
        )
        self.checkbox_canvas.configure(yscrollcommand=self.checkbox_scrollbar.set)
        self.checkbox_canvas.pack(side="left", fill="both", expand=True)
        self.checkbox_scrollbar.pack(side="right", fill="y")
        self.checkbox_canvas.bind("<Configure>", self.on_canvas_configure)
        self.checkbox_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.checkbox_canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.checkbox_canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, event: tk.Event) -> None:
        x, y = self.root.winfo_pointerxy()
        widget = self.root.winfo_containing(x, y)
        if widget is None:
            return

        parent = widget
        is_over_target = False
        while parent is not None:
            if parent in (self.checkbox_canvas, self.checkbox_scrollable_frame):
                is_over_target = True
                break
            parent = getattr(parent, "master", None)

        if is_over_target:
            event_delta = getattr(event, "delta", 0)
            if getattr(event, "num", None) == 4 or event_delta > 0:
                self.checkbox_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5 or event_delta < 0:
                self.checkbox_canvas.yview_scroll(1, "units")

    def on_canvas_configure(self, event: tk.Event) -> None:
        self.checkbox_canvas.itemconfig(self.canvas_window, width=event.width)

    def start_spinner(self, message: str = "") -> None:
        self.safe_ui_update(self.progress_bar.config, mode="indeterminate")
        self.safe_ui_update(self.progress_label.config, text=message)
        self.safe_ui_update(self.progress_bar.start, 10)

    def stop_spinner(self, message: str = "") -> None:
        self.safe_ui_update(self.progress_bar.stop)
        self.safe_ui_update(self.progress_bar.config, mode="determinate", value=0)
        self.safe_ui_update(self.progress_label.config, text=message)

    def update_progress(self, value: int, total: int, message: str = "") -> None:
        if total > 0:
            percentage = int((value / total) * 100)
            self.safe_ui_update(self.progress_bar.config, mode="determinate", value=percentage)
            self.safe_ui_update(
                self.progress_label.config,
                text=f"{message} ({value}/{total}) - {percentage}%",
            )
        else:
            self.safe_ui_update(self.progress_bar.config, mode="determinate", value=0)
            self.safe_ui_update(self.progress_label.config, text=message)

    def load_model(self) -> None:
        if self.load_thread and self.load_thread.is_alive():
            messagebox.showwarning("Busy", "Model is already loading.")
            logging.warning("Attempted to load model while previous load was in progress.")
            return

        model_name = self.model_var.get()

        def load() -> None:
            self.safe_ui_update(self.model_dropdown.config, state="disabled")
            self.safe_ui_update(self.select_button.config, state=tk.DISABLED)
            self.safe_ui_update(self.start_button.config, state=tk.DISABLED)
            self.safe_ui_update(self.model_status.config, text="Model status: Unknown", foreground="gray")

            try:
                self.safe_ui_update(
                    self.model_status.config,
                    text=f"Loading '{model_name}' model...",
                    foreground="orange",
                )
                self.start_spinner(f"Downloading/Loading '{model_name}'...")
                logging.info(f"Attempting to load Whisper model: {model_name}")
                self.start_spinner(f"Loading model '{model_name}'... (may take a while)")
                self.model = self.service.load_model(model_name)

                self.model_loaded = True
                logging.info(f"Model '{model_name}' loaded successfully.")
                self.safe_ui_update(
                    self.model_status.config,
                    text=f"Model '{model_name}' loaded ✓",
                    foreground="dark green",
                )
                self.safe_ui_update(self.select_button.config, state=tk.NORMAL)
            except ImportError:
                logging.error("Whisper library not found. Please install it: pip install -U openai-whisper")
                self.safe_ui_update(
                    messagebox.showerror,
                    "Error",
                    "Whisper library not found.\nPlease install it via pip:\npip install -U openai-whisper",
                )
                self.safe_ui_update(
                    self.model_status.config,
                    text="Error: Whisper not installed",
                    foreground="red",
                )
                self.model_loaded = False
            except Exception as exc:
                error_msg = f"Failed to load model '{model_name}':\n{exc}"
                logging.error(f"Failed to load model '{model_name}': {traceback.format_exc()}")
                self.safe_ui_update(self.model_status.config, text="Model load failed!", foreground="red")
                self.safe_ui_update(messagebox.showerror, "Error", error_msg)
                self.model_loaded = False
            finally:
                self.stop_spinner("Ready." if self.model_loaded else "Model load failed.")
                self.safe_ui_update(self.model_dropdown.config, state="readonly")
                if self.model_loaded and self.file_paths:
                    self.safe_ui_update(self.start_button.config, state=tk.NORMAL)
                else:
                    self.safe_ui_update(self.start_button.config, state=tk.DISABLED)

        self.load_thread = threading.Thread(target=load, name="ModelLoader", daemon=True)
        self.load_thread.start()

    def on_closing(self) -> None:
        if self.process_thread and self.process_thread.is_alive():
            if messagebox.askyesno(
                "Confirm Exit",
                "Processing is ongoing. Are you sure you want to stop and exit?",
            ):
                logging.info("User requested exit during processing.")
                self.cancel_flag.set()
                self.root.destroy()
            else:
                logging.info("User cancelled exit request.")
            return

        if self.load_thread and self.load_thread.is_alive():
            if messagebox.askyesno(
                "Confirm Exit",
                "Model is still loading. Are you sure you want to exit?",
            ):
                logging.info("User requested exit during model load.")
                self.root.destroy()
            return

        logging.info("User closed the application.")
        self.root.destroy()

    def select_files(self) -> None:
        self.file_paths.clear()
        for widget in self.file_widgets.values():
            widget["row"].destroy()
        self.file_widgets.clear()

        if not self.model_loaded:
            messagebox.showwarning(
                "Model Required",
                "Please wait for the model to load before selecting files.",
            )
            return

        new_paths = filedialog.askopenfilenames(
            title="Select Media Files",
            filetypes=[
                ("Media Files", "*.mp3 *.mp4 *.m4a *.wav *.ogg *.flac *.avi *.mov *.mkv *.webm"),
                ("Audio Files", "*.mp3 *.wav *.m4a *.ogg *.flac"),
                ("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                ("All Files", "*.*"),
            ],
        )
        if not new_paths:
            return

        added_count = 0
        current_paths_set = set(self.file_paths)
        for path in new_paths:
            if path not in current_paths_set:
                self.file_paths.append(path)
                current_paths_set.add(path)
                added_count += 1

        if added_count <= 0:
            self.append_status("No new files were added (already in queue).\n")
            return

        self.file_paths.sort()
        if not self.input_dir:
            self.input_dir = os.path.dirname(self.file_paths[0])
            self.transcription_dir = os.path.join(self.input_dir, OUTPUT_DIRECTORY_NAME)
            try:
                ensure_output_directory(self.file_paths[0])
                logging.info(f"Transcription output directory set to: {self.transcription_dir}")
            except OSError as exc:
                logging.error(f"Could not create transcription directory: {exc}")
                messagebox.showerror(
                    "Error",
                    f"Could not create output directory:\n{self.transcription_dir}\nError: {exc}",
                )
                self.input_dir = None
                self.transcription_dir = None
                return

        self.update_file_list_ui()
        self.start_button.config(state=tk.NORMAL)
        self.append_status(f"Added {added_count} new file(s). Total in queue: {len(self.file_paths)}\n")

    def update_file_list_ui(self) -> None:
        for path, widget_dict in list(self.file_widgets.items()):
            widget_dict["row"].destroy()
            del self.file_widgets[path]

        for path in self.file_paths:
            row_frame = ttk.Frame(self.checkbox_scrollable_frame, padding=(5, 2))
            row_frame.pack(fill="x")

            status_label = ttk.Label(
                row_frame,
                text="⏳",
                foreground="gray",
                font=("Arial Unicode MS", 10),
                width=2,
            )
            status_label.pack(side="left", padx=(0, 5))

            file_label = ttk.Label(
                row_frame,
                text=os.path.basename(path),
                anchor="w",
                font=("Segoe UI", 9),
            )
            file_label.pack(side="left", fill="x", expand=True)
            self.file_widgets[path] = {"row": row_frame, "status": status_label, "file": file_label}

        self.checkbox_scrollable_frame.update_idletasks()
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))

    def start_processing(self) -> None:
        if not self.model_loaded:
            messagebox.showwarning("Model Required", "Model is not loaded yet.")
            return
        if not self.file_paths:
            messagebox.showwarning("Files Required", "Please select files to transcribe.")
            return
        if self.process_thread and self.process_thread.is_alive():
            messagebox.showwarning("Busy", "Processing is already in progress.")
            return

        self.select_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.model_dropdown.config(state="disabled")
        self.cancel_button.config(text="⏳ Cancel Processing...")
        self.start_spinner("Preparing...")
        self.update_progress(0, len(self.file_paths), "Starting...")
        self.append_status("--- Starting Transcription Process ---\n")

        for path_data in self.file_widgets.values():
            path_data["status"].config(text="⏳", foreground="gray")

        self.cancel_flag.clear()
        self.process_thread = threading.Thread(
            target=self.process_files_thread,
            args=(list(self.file_paths), self.transcription_dir, self.task_var.get()),
            name="ProcessingThread",
            daemon=True,
        )
        self.process_thread.start()

    def process_files_thread(self, file_paths, output_directory, task: str) -> None:
        try:
            summary = self.service.process_files(
                file_paths,
                output_directory,
                task,
                self.cancel_flag,
                status_callback=self.append_status,
                file_status_callback=self.update_file_status,
                progress_callback=self.update_progress,
            )
            self.stop_spinner(summary.final_message)
            self.append_status(
                f"--- {summary.final_message} --- "
                f"({summary.processed_count}/{summary.total_files} processed)\n"
            )
        except Exception as exc:
            logging.error(f"Unhandled processing error: {traceback.format_exc()}")
            self.stop_spinner("Processing failed.")
            self.append_status(f"ERROR: {exc}\n")
        finally:
            self.safe_ui_update(self.restore_processing_controls)

    def update_file_status(self, path: str, status: str, foreground: str) -> None:
        file_info = self.file_widgets.get(path)
        if file_info:
            self.safe_ui_update(file_info["status"].config, text=status, foreground=foreground)

    def restore_processing_controls(self) -> None:
        self.select_button.config(state=tk.NORMAL)
        self.model_dropdown.config(state="readonly")
        self.start_button.config(state=tk.NORMAL if self.file_paths else tk.DISABLED)
        self.cancel_button.config(text="❌ Close Application")

    def safe_ui_update(self, func, *args, **kwargs) -> None:
        try:
            if self.root.winfo_exists():
                self.root.after(0, lambda: func(*args, **kwargs))
        except (RuntimeError, tk.TclError) as exc:
            logging.warning(f"UI update could not be scheduled (window likely closing): {exc}")

    def append_status(self, text: str) -> None:
        def update() -> None:
            if self.file_status.winfo_exists():
                current_state = self.file_status.cget("state")
                self.file_status.config(state="normal")
                self.file_status.insert(tk.END, text)
                self.file_status.see(tk.END)
                self.file_status.config(state=current_state)

        self.safe_ui_update(update)
