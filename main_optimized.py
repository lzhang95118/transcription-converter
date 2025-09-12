# whisper_gui_cleaned.py - 清理优化版 Whisper GUI 主程序

import os
import sys
import logging
import tempfile
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pydub import AudioSegment
from pydub.utils import which
import requests
import time
from huggingface_hub import model_info

# -------------------------
# ✅ 初始化配置和日志
# -------------------------
try:
    log_path = os.path.join(os.getcwd(), "transcribing_log.txt")
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s"
    )
    logging.info("App Started")
    print(f"Logging to: {log_path}")

# ✅ tqdm workaround for PyInstaller: prevent stdout/stderr=None error
    if getattr(sys, 'frozen', False):
        import io
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
except Exception as e:
    print(f"Logging init failed: {e}")
    logging.basicConfig(level=logging.CRITICAL)

# -------------------------
# ✅ 设置 ffmpeg 路径
# -------------------------
try:
    if getattr(sys, 'frozen', False):
        ffmpeg_path = os.path.join(sys._MEIPASS, "ffmpeg", "bin", "ffmpeg.exe")
        if not os.path.exists(ffmpeg_path):
            raise FileNotFoundError("Bundled ffmpeg not found.")
    else:
        ffmpeg_path = which("ffmpeg") or "ffmpeg"
    AudioSegment.converter = ffmpeg_path
    os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]
    logging.info(f"Using ffmpeg at: {ffmpeg_path}")
except Exception as e:
    logging.error(f"FFmpeg path setup failed: {e}")
    AudioSegment.converter = "ffmpeg"

# -------------------------
# ✅ Whisper 模型缓存目录
# -------------------------
try:
    cache_dir = os.path.join(tempfile.gettempdir(), "whisper_models_transcriber")
    os.makedirs(cache_dir, exist_ok=True)
    os.environ["TRANSFORMERS_CACHE"] = cache_dir
    os.environ["HF_HOME"] = cache_dir
    logging.info(f"Model cache directory: {cache_dir}")
except Exception as e:
    logging.error(f"Cache directory error: {e}")

class WhisperModelDownloader:
    def __init__(self, model_name, cache_dir=None, progress_callback=None):
        self.model_name = model_name
        self.progress_callback = progress_callback

def download(self):
    # No-op: whisper.load_model() handles model downloading internally
    if self.progress_callback:
        self.progress_callback(0, 0.0)
    return None

class TranscribingProcessor:
    def __init__(self, root):
        self.root = root
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing) # Handle window close button
        self.cancel_flag = threading.Event() # Use threading.Event for safer flag checking
        self.file_paths = []
        self.model_loaded = False
        self.model = None
        self.input_dir = None
        self.transcription_dir = None
        self.file_widgets = {} # Renamed from file_checkboxes for clarity
        self.process_thread = None # Keep track of the processing thread
        self.load_thread = None # Keep track of the model loading thread

        self.setup_ui()
        self.model_var.set("base") # Default model
        # Delay model load slightly to ensure UI is fully drawn
        self.root.after(100, self.load_model)


    def setup_ui(self):
        self.root.title("Whisper Audio Transcriber")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400) # Set minimum window size
        self.root.configure(bg="#f2f2f2")
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam', 'alt', 'default', 'vista' (windows) are good options

        # Custom styles (adjust colors and fonts as needed)
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        self.style.map("TButton", background=[("active", "#d9d9d9")])
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=6, foreground="#a60000", background="#ffe0e0")
        self.style.map("Danger.TButton", background=[("active", "#ffcccc")])
        self.style.configure("TCombobox", font=("Segoe UI", 10), padding=5)
        self.style.configure("TScrollbar", troughcolor="#f0f0f0", background="#c0c0c0")
        self.style.configure("TProgressbar", troughcolor='#e0e0e0', background='#0078d4') # Blue progress bar

        title = tk.Label(self.root, text="🎧 Whisper Audio Transcriber", font=("Segoe UI", 18, "bold"), bg="#f2f2f2", foreground="#333")
        title.pack(pady=(15, 10))

        # Use PanedWindow for resizable sections
        paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bg="#d0d0d0", sashwidth=6)
        paned_window.pack(fill="both", expand=True, padx=15, pady=10)

        # Left Frame (Status Log)
        left_frame = ttk.Frame(paned_window, style="Card.TFrame", padding=10) # Use ttk.Frame
        paned_window.add(left_frame, stretch="always", minsize=300) # Adjust minsize

        ttk.Label(left_frame, text="📋 Processing Log", font=("Segoe UI", 12, "bold")).pack(pady=(0, 5), anchor="w")
        text_frame = ttk.Frame(left_frame) # Use ttk.Frame for consistency
        text_frame.pack(fill="both", expand=True)

        self.file_status = tk.Text(text_frame, height=10, width=40, bg="#ffffff", wrap="word", font=("Consolas", 10), bd=1, relief="solid", state="disabled", padx=5, pady=5) # Add padding
        self.file_status.pack(side="left", fill="both", expand=True)

        file_scrollbar = ttk.Scrollbar(text_frame, command=self.file_status.yview, style="TScrollbar")
        file_scrollbar.pack(side="right", fill="y")
        self.file_status.config(yscrollcommand=file_scrollbar.set)

        # Right Frame (Controls & File List)
        right_frame = ttk.Frame(paned_window, style="Card.TFrame", padding=10) # Use ttk.Frame
        paned_window.add(right_frame, stretch="never", minsize=350) # Adjust minsize

        control_container = ttk.Frame(right_frame)
        control_container.pack(anchor="nw", fill="x") # Pack controls at the top

        # --- Controls ---
        ttk.Label(control_container, text="⚙️ Controls", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10), anchor="w")

        # 新增任务模式选择
        task_frame = ttk.Frame(control_container)
        task_frame.pack(fill="x", pady=(5, 5))
        ttk.Label(task_frame, text="Model:", font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        self.task_var = tk.StringVar(value="transcribe")  # 默认使用原文模式
        self.task_dropdown = ttk.Combobox(task_frame, textvariable=self.task_var,
                                        values=["transcribe", "translate"],
                                        state="readonly", width=15)
        self.task_dropdown.pack(side="left", fill="x", expand=True)



        model_frame = ttk.Frame(control_container)
        model_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(model_frame, text="Model:", font=("Segoe UI", 10)).pack(side="left", padx=(0, 5))
        self.model_var = tk.StringVar()
        self.model_dropdown = ttk.Combobox(model_frame, textvariable=self.model_var,
                                           values=["tiny", "base", "small", "medium", "large"],
                                           state="readonly", width=15, style="TCombobox")
        self.model_dropdown.pack(side="left", fill="x", expand=True)
        self.model_dropdown.bind("<<ComboboxSelected>>", lambda e: self.load_model())

        self.model_status = ttk.Label(control_container, text="Model status: Initializing...", foreground="gray", font=("Segoe UI", 9))
        self.model_status.pack(anchor="w", pady=(0, 10), fill="x")

        button_frame = ttk.Frame(control_container)
        button_frame.pack(fill="x", pady=5)
        self.select_button = ttk.Button(button_frame, text="📂 Select Files", command=self.select_files, state=tk.DISABLED, width=18)
        self.select_button.pack(side="left", padx=(0,5), fill="x", expand=True)
        self.start_button = ttk.Button(button_frame, text="▶️ Start", command=self.start_processing, state=tk.DISABLED, width=18)
        self.start_button.pack(side="left", fill="x", expand=True)


        self.cancel_button = ttk.Button(control_container, text="❌ Close Application", command=self.on_closing, style="Danger.TButton")
        self.cancel_button.pack(pady=(8,0), fill="x")


        # --- Progress Bar ---
        ttk.Separator(control_container, orient='horizontal').pack(fill='x', pady=15)
        self.progress_label = ttk.Label(control_container, text="", font=("Segoe UI", 9))
        self.progress_label.pack(anchor="w")
        self.progress_bar = ttk.Progressbar(control_container, length=200, mode="determinate", style="TProgressbar") # Use determinate for file progress
        self.progress_bar.pack(pady=(2, 10), fill="x")

        # --- File Status List ---
        ttk.Label(right_frame, text="📄 File Queue", font=("Segoe UI", 12, "bold")).pack(pady=(15, 5), anchor="w") # Label moved to right_frame

        # Frame to hold the canvas and scrollbar for the file list
        status_frame_container = ttk.Frame(right_frame, relief="groove", borderwidth=1) # Added border/relief
        # **MODIFIED PACK**: Fill remaining space in right_frame, allow expansion
        status_frame_container.pack(fill="both", expand=True, pady=(0, 0))

        self.checkbox_canvas = tk.Canvas(status_frame_container, bg="#ffffff", highlightthickness=0, bd=0) # White background
        self.checkbox_scrollbar = ttk.Scrollbar(status_frame_container, orient="vertical", command=self.checkbox_canvas.yview, style="TScrollbar")
        self.checkbox_scrollable_frame = ttk.Frame(self.checkbox_canvas) # Frame inside canvas, use ttk for consistency?
        self.checkbox_scrollable_frame.configure(style='Card.TFrame') # Match background if needed

        # Configure scrolling
        self.checkbox_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))
        )
        # Place scrollable frame inside canvas
        self.canvas_window = self.checkbox_canvas.create_window((0, 0), window=self.checkbox_scrollable_frame, anchor="nw")
        # Link scrollbar and canvas
        self.checkbox_canvas.configure(yscrollcommand=self.checkbox_scrollbar.set)

        # Pack canvas and scrollbar
        self.checkbox_canvas.pack(side="left", fill="both", expand=True)
        self.checkbox_scrollbar.pack(side="right", fill="y")

        # Update canvas width when window resizes
        self.checkbox_canvas.bind("<Configure>", self.on_canvas_configure)

        # Add mouse wheel scrolling for the canvas
        self.checkbox_canvas.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/macOS
        self.checkbox_canvas.bind_all("<Button-4>", self._on_mousewheel) # Linux scroll up
        self.checkbox_canvas.bind_all("<Button-5>", self._on_mousewheel) # Linux scroll down

    def _on_mousewheel(self, event):
        # Determine which widget the mouse is over
        x, y = self.root.winfo_pointerxy()
        widget = self.root.winfo_containing(x, y)

        # Check if the mouse is over the file list canvas or its children
        target_canvas = self.checkbox_canvas
        is_over_target = False
        if widget == target_canvas:
            is_over_target = True
        else:
            # Check if the widget is a child of the scrollable frame within the canvas
            parent = widget
            while parent is not None:
                if parent == self.checkbox_scrollable_frame:
                    is_over_target = True
                    break
                parent = parent.master # type: ignore

        if is_over_target:
            # Determine scroll direction and amount
            if event.num == 4 or event.delta > 0: # Linux scroll up or Windows/macOS scroll up
                target_canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0: # Linux scroll down or Windows/macOS scroll down
                target_canvas.yview_scroll(1, "units")


    def on_canvas_configure(self, event):
        # Update the width of the inner frame to match the canvas width minus scrollbar space if visible
        canvas_width = event.width
        self.checkbox_canvas.itemconfig(self.canvas_window, width=canvas_width)


    def start_spinner(self, message=""):
        # Use indeterminate mode for model loading/unknown duration tasks
        self.safe_ui_update(self.progress_bar.config, mode="indeterminate")
        self.safe_ui_update(self.progress_label.config, text=message)
        self.safe_ui_update(self.progress_bar.start, 10) # Speed of indeterminate animation


    def stop_spinner(self, message=""):
        self.safe_ui_update(self.progress_bar.stop)
        self.safe_ui_update(self.progress_bar.config, mode="determinate", value=0) # Reset determinate bar
        self.safe_ui_update(self.progress_label.config, text=message)


    def update_progress(self, value, total, message=""):
         # Calculate percentage and update determinate progress bar safely
        if total > 0:
            percentage = int((value / total) * 100)
            self.safe_ui_update(self.progress_bar.config, mode="determinate", value=percentage)
            self.safe_ui_update(self.progress_label.config, text=f"{message} ({value}/{total}) - {percentage}%")
        else:
            self.safe_ui_update(self.progress_bar.config, mode="determinate", value=0)
            self.safe_ui_update(self.progress_label.config, text=message)


    def load_model(self):
        if self.load_thread and self.load_thread.is_alive():
            messagebox.showwarning("Busy", "Model is already loading.")
            logging.warning("Attempted to load model while previous load was in progress.")
            return

        def load():
            # Disable controls during load
            self.safe_ui_update(self.model_dropdown.config, state="disabled")
            self.safe_ui_update(self.select_button.config, state=tk.DISABLED)
            self.safe_ui_update(self.start_button.config, state=tk.DISABLED)
            self.safe_ui_update(self.model_status.config, text="Model status: Unknown", foreground="gray")

            try:
                import whisper
                model_name = self.model_var.get()
                self.safe_ui_update(self.model_status.config, text=f"Loading '{model_name}' model...", foreground="orange")
                self.start_spinner(f"Downloading/Loading '{model_name}'...") # Use safe_ui_update indirectly
                logging.info(f"Attempting to load Whisper model: {model_name}")

                # --- Load model (this is the blocking part) ---
                # 👇 新增：用自定义下载器显示下载速度
                downloader = WhisperModelDownloader(
                    model_name=model_name,
                    cache_dir=cache_dir,
                    progress_callback=lambda pct, spd: self.safe_ui_update(
                        self.update_progress_bar_with_speed, pct, spd
                    )
                )
                self.start_spinner(f"Loading model '{model_name}'... (may take a while)")
                self.model = whisper.load_model(model_name)

                # --- Model Loaded ---

                self.model_loaded = True
                logging.info(f"Model '{model_name}' loaded successfully.")
                self.safe_ui_update(self.model_status.config, text=f"Model '{model_name}' loaded ✓", foreground="dark green")
                self.safe_ui_update(self.select_button.config, state=tk.NORMAL) # Enable file selection

            except ImportError:
                 logging.error("Whisper library not found. Please install it: pip install -U openai-whisper")
                 self.safe_ui_update(messagebox.showerror, "Error", "Whisper library not found.\nPlease install it via pip:\npip install -U openai-whisper")
                 self.safe_ui_update(self.model_status.config, text="Error: Whisper not installed", foreground="red")
                 self.model_loaded = False
            except Exception as e:
                error_msg = f"Failed to load model '{self.model_var.get()}':\n{e}"
                logging.error(f"Failed to load model '{self.model_var.get()}': {traceback.format_exc()}")
                self.safe_ui_update(self.model_status.config, text="Model load failed!", foreground="red")
                self.safe_ui_update(messagebox.showerror, "Error", error_msg)
                self.model_loaded = False # Ensure flag is false on error
            finally:
                # Re-enable dropdown, stop spinner regardless of success/failure
                self.stop_spinner("Ready." if self.model_loaded else "Model load failed.") # Uses safe_ui_update indirectly
                self.safe_ui_update(self.model_dropdown.config, state="readonly")
                # Enable start button only if files are also selected
                if self.model_loaded and self.file_paths:
                    self.safe_ui_update(self.start_button.config, state=tk.NORMAL)
                else:
                    self.safe_ui_update(self.start_button.config, state=tk.DISABLED)

        # Start the thread
        self.load_thread = threading.Thread(target=load, name="ModelLoader", daemon=True)
        self.load_thread.start()


    def on_closing(self):
        """ Handles the window close event. """
        if self.process_thread and self.process_thread.is_alive():
             if messagebox.askyesno("Confirm Exit", "Processing is ongoing. Are you sure you want to stop and exit?"):
                 logging.info("User requested exit during processing.")
                 self.cancel_flag.set() # Signal the processing thread to stop
                 # Optionally wait a short time for the thread to finish gracefully
                 # self.process_thread.join(timeout=1.0)
                 self.root.destroy()
                 sys.exit(0)
             else:
                 logging.info("User cancelled exit request.")
                 return # Don't close
        else:
             # Ask even if not processing, for consistency or if loading
             if self.load_thread and self.load_thread.is_alive():
                  if messagebox.askyesno("Confirm Exit", "Model is still loading. Are you sure you want to exit?"):
                     logging.info("User requested exit during model load.")
                     # Cannot easily stop model load, just exit
                     self.root.destroy()
                     sys.exit(0)
                  else:
                     return
             else:
                  # No critical task running, just close
                  logging.info("User closed the application.")
                  self.root.destroy()
                  sys.exit(0)


    def select_files(self):
        # 清空旧任务列表
        self.file_paths.clear()
        for widget in self.file_widgets.values():
            widget['row'].destroy()
        self.file_widgets.clear()
        if not self.model_loaded:
             messagebox.showwarning("Model Required", "Please wait for the model to load before selecting files.")
             return

        new_paths = filedialog.askopenfilenames(
            title="Select Media Files",
            filetypes=[("Media Files", "*.mp3 *.mp4 *.m4a *.wav *.ogg *.flac *.avi *.mov *.mkv *.webm"),
                       ("Audio Files", "*.mp3 *.wav *.m4a *.ogg *.flac"),
                       ("Video Files", "*.mp4 *.avi *.mov *.mkv *.webm"),
                       ("All Files", "*.*")]
        )
        if new_paths:
            # Add only new, unique paths
            added_count = 0
            current_paths_set = set(self.file_paths)
            for p in new_paths:
                if p not in current_paths_set:
                    self.file_paths.append(p)
                    current_paths_set.add(p)
                    added_count += 1

            if added_count > 0:
                self.file_paths.sort() # Keep the list sorted

                if not self.input_dir: # Set directories based on the first file selected in the first batch
                     try:
                         self.input_dir = os.path.dirname(self.file_paths[0])
                         self.transcription_dir = os.path.join(self.input_dir, "Whisper_Transcriptions") # Changed folder name
                         os.makedirs(self.transcription_dir, exist_ok=True)
                         logging.info(f"Transcription output directory set to: {self.transcription_dir}")
                     except OSError as e:
                         logging.error(f"Could not create transcription directory: {e}")
                         messagebox.showerror("Error", f"Could not create output directory:\n{self.transcription_dir}\nError: {e}")
                         self.input_dir = None # Reset if failed
                         self.transcription_dir = None
                         return # Don't proceed

                # Update the file list UI
                self.update_file_list_ui()

                # Enable start button
                self.start_button.config(state=tk.NORMAL)

                self.append_status(f"Added {added_count} new file(s). Total in queue: {len(self.file_paths)}\n")
            else:
                 self.append_status("No new files were added (already in queue).\n")


    def update_file_list_ui(self):
         # Clear existing widgets in the scrollable frame first
        for path, widget_dict in list(self.file_widgets.items()): # Iterate over a copy
            widget_dict["row"].destroy()
            del self.file_widgets[path]

        # Add entries for all current file_paths
        for path in self.file_paths:
            filename = os.path.basename(path)
            # Use a Frame for each row
            row_frame = ttk.Frame(self.checkbox_scrollable_frame, padding=(5, 2))
            row_frame.pack(fill="x")

            # Status indicator (Label)
            status_label = ttk.Label(row_frame, text="⏳", foreground="gray", font=("Arial Unicode MS", 10), width=2) # Use a font that supports symbols
            status_label.pack(side="left", padx=(0, 5))

            # Filename Label (allow it to shrink/expand)
            # Use elide=tk.END if filename gets too long? Requires fixed width or clever geometry.
            file_label = ttk.Label(row_frame, text=filename, anchor="w", font=("Segoe UI", 9))
            file_label.pack(side="left", fill="x", expand=True)

            # Store references to update later
            self.file_widgets[path] = {"row": row_frame, "status": status_label, "file": file_label}

        # Update scrollregion after adding/removing widgets
        self.checkbox_scrollable_frame.update_idletasks() # Ensure geometry is calculated
        self.checkbox_canvas.configure(scrollregion=self.checkbox_canvas.bbox("all"))


    def start_processing(self):
        if not self.model_loaded:
            messagebox.showwarning("Model Required", "Model is not loaded yet.")
            return
        if not self.file_paths:
            messagebox.showwarning("Files Required", "Please select files to transcribe.")
            return
        if self.process_thread and self.process_thread.is_alive():
             messagebox.showwarning("Busy", "Processing is already in progress.")
             return

        # Disable buttons/controls during processing
        self.select_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.model_dropdown.config(state="disabled")
        self.cancel_button.config(text="⏳ Cancel Processing...") # Change cancel button text

        # Reset progress bar and status for a new run
        self.start_spinner("Preparing...")
        self.update_progress(0, len(self.file_paths), "Starting...")
        self.append_status("--- Starting Transcription Process ---\n")

        # Reset visual status of files in the list
        for path_data in self.file_widgets.values():
            path_data["status"].config(text="⏳", foreground="gray") # Reset to pending

        # Start the processing thread
        self.cancel_flag.clear() # Reset cancel flag/event before starting
        self.process_thread = threading.Thread(target=self.process_files_thread, name="ProcessingThread", daemon=True)
        self.process_thread.start()


    def process_files_thread(self):
        """ The actual file processing logic running in the background thread. """
        import whisper # Import here if not needed globally
        total_files = len(self.file_paths)
        processed_count = 0
        files_to_process = list(self.file_paths) # Process a copy in case list changes

        for i, file_path in enumerate(files_to_process):
            if self.cancel_flag.is_set(): # Check if cancellation requested
                self.append_status(f"Processing cancelled by user.\n")
                logging.warning("Processing cancelled by user.")
                break # Exit the loop

            filename = os.path.basename(file_path)
            base_name = os.path.splitext(filename)[0]

            # --- Prepare output path ---
            output_filename = base_name + ".txt" # Simple .txt output
            transcript_file = os.path.join(self.transcription_dir, output_filename)
            counter = 1
            while os.path.exists(transcript_file): # Avoid overwriting silently
                output_filename = f"{base_name}_{counter}.txt"
                transcript_file = os.path.join(self.transcription_dir, output_filename)
                counter += 1
            # --- ---

            file_info = self.file_widgets.get(file_path)
            if file_info:
                 # Update UI: Mark as Processing
                 self.safe_ui_update(file_info["status"].config, text="⏱️", foreground="blue")
            self.append_status(f"Processing [{i+1}/{total_files}]: {filename}...\n")
            logging.info(f"Processing [{i+1}/{total_files}]: {file_path}")

            try:
                # --- Basic File Checks ---
                if not os.path.exists(file_path):
                    logging.warning(f"File not found, skipping: {file_path}")
                    if file_info:
                        self.safe_ui_update(file_info["status"].config, text="❓", foreground="orange") # Not found icon
                    self.append_status(f"Skipped (Not Found): {filename}\n")
                    # Note: count as processed for progress bar? Yes.
                    processed_count += 1
                    self.update_progress(processed_count, total_files, f"Skipped {filename}")
                    continue # Skip to next file

                # --- Audio Check (Optional but recommended) ---
                try:
                    audio = AudioSegment.from_file(file_path)
                    if audio.duration_seconds < 0.1: # Check for very short/empty files
                         logging.warning(f"Audio file seems too short or empty, skipping: {filename} ({audio.duration_seconds:.2f}s)")
                         if file_info:
                              self.safe_ui_update(file_info["status"].config, text="⚠️", foreground="#cc8400") # Warning icon orange/brown
                         self.append_status(f"Skipped (Too Short/Empty): {filename}\n")
                         processed_count += 1
                         self.update_progress(processed_count, total_files, f"Skipped {filename}")
                         continue
                except Exception as audio_err:
                     # Log warning but attempt transcription anyway, Whisper might handle it
                     logging.warning(f"Could not read audio properties for {filename}, attempting transcription. Error: {audio_err}")


                # --- Transcribe (The Core Task) ---
                logging.info(f"Starting transcription for: {file_path}")
                # Add whisper options here if needed: language='en', task='transcribe', etc.
                # 假设你新增一个变量 self.task_var 用于存储任务模式
                task_mode = self.task_var.get()  # "translate" 或 "transcribe"
                result = self.model.transcribe(file_path, fp16=False, task=task_mode)


                # --- Save Transcript ---
                with open(transcript_file, "w", encoding="utf-8") as f:
                    #f.write(result["text"].strip()) # Write the full text directly
                    # Or segmented output:
                    for seg in result["segments"]:
                        start = seg['start']
                        end = seg['end']
                        text = seg['text'].strip()
                        f.write(f"[{start:.2f} -> {end:.2f}] {text}\n")

                logging.info(f"Transcription saved to: {transcript_file}")

                # --- Update UI: Success ---
                if file_info:
                    self.safe_ui_update(file_info["status"].config, text="✓", foreground="dark green") # Success icon
                self.append_status(f"Success: {filename} -> {output_filename}\n")

            except Exception as e:
                # --- Update UI: Error ---
                logging.error(f"Error processing {filename}: {traceback.format_exc()}")
                if file_info:
                    self.safe_ui_update(file_info["status"].config, text="❌", foreground="red") # Error icon
                self.append_status(f"ERROR processing {filename}: {e}\n")
            finally:
                 # --- Update Progress ---
                 processed_count += 1
                 self.update_progress(processed_count, total_files, f"Processed {filename}")


        # --- Processing Finished (Loop Ends or Cancelled) ---
        final_message = "Processing complete." if not self.cancel_flag.is_set() else "Processing cancelled."
        logging.info(final_message)
        self.stop_spinner(final_message) # Updates UI safely
        self.append_status(f"--- {final_message} --- ({processed_count}/{total_files} processed)\n")

        # --- Clear processed files from the list? (Optional UX decision) ---
        # If you want to clear successful files:
        # self.file_paths = [p for p in self.file_paths if self.file_widgets[p]["status"].cget("text") not in ["✓"]]
        # self.safe_ui_update(self.update_file_list_ui)
        # For now, leave all files listed with their status.

        # --- Re-enable Controls (Safely) ---
        self.safe_ui_update(self.select_button.config, state=tk.NORMAL)
        self.safe_ui_update(self.model_dropdown.config, state="readonly")
        # Only enable Start if files are still in the list
        if self.file_paths:
             self.safe_ui_update(self.start_button.config, state=tk.NORMAL)
        else:
             self.safe_ui_update(self.start_button.config, state=tk.DISABLED)
        self.safe_ui_update(self.cancel_button.config, text="❌ Close Application") # Reset cancel button

    def update_progress_bar_with_speed(self, percent, speed):
        self.progress_bar.config(mode="determinate", value=percent)
        self.progress_label.config(text=f"Downloading '{self.model_var.get()}' - {percent:.1f}% @ {speed:.2f} MB/s")


    def safe_ui_update(self, func, *args, **kwargs):
        """ Schedules a function to run in the main Tkinter thread. """
        try:
            if self.root.winfo_exists(): # Check if window still exists
                self.root.after(0, lambda: func(*args, **kwargs))
        except tk.TclError as e:
            # This can happen if the window is destroyed while updates are pending
             logging.warning(f"TclError during safe_ui_update (window likely closing): {e}")


    def append_status(self, text):
        """ Appends text to the status log text widget safely. """
        def _update():
            if self.file_status.winfo_exists(): # Check widget existence too
                 current_state = self.file_status.cget("state")
                 self.file_status.config(state="normal")
                 self.file_status.insert(tk.END, text)
                 self.file_status.see(tk.END) # Scroll to the end
                 self.file_status.config(state=current_state) # Restore original state (usually disabled)
        # Schedule the UI update
        self.safe_ui_update(_update)


# -------------------------
# ✅ 主程序入口
# -------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = None
    try:
        style = ttk.Style()
        style.configure("Card.TFrame", background="#ffffff", borderwidth=1, relief="solid")
        style.configure("TFrame", background="#f9f9f9")

        app = TranscribingProcessor(root)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Unhandled exception: {traceback.format_exc()}")
        try:
            messagebox.showerror("Fatal Error", f"Critical error:\n{e}\nCheck log: {log_path}")
        except Exception as e_msg:
            print(f"FATAL ERROR: {e}\nCould not show error message: {e_msg}")
    finally:
        logging.info("App Closed")
        logging.shutdown()
        if app:
            app.cancel_flag.set()
