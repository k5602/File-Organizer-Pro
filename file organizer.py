"""
File Organizer Pro - Ultimate Edition
"""
import os
import hashlib
import shutil
import time
import threading
import json
import webbrowser
from pathlib import Path
from tkinter import Menu
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import customtkinter as ctk
import pystray
import schedule
import pdfplumber
from PIL import Image, ImageTk, ImageDraw
import keyring

CATEGORIES = {
    "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx"],
    "Images": [".jpg", ".png", ".webp", ".gif", ".svg"],
    "Media": [".mp4", ".mov", ".avi", ".mkv", ".mp3"],
    "Archives": [".zip", ".rar", ".7z", ".tar"],
    "Code": [".py", ".js", ".html", ".css", ".json"],
}

SCHEDULE_CONFIG = Path.home() / ".file_organizer_schedule.json"
PREVIEW_TEMP = Path.home() / ".file_organizer_previews"

# ---------------------------- Core Engine ----------------------------
class FileOrganizerEngine:
    """Advanced file organization core with scheduling and previews"""
    
    def __init__(self, root_path):
        self.root_path = Path(root_path)
        self.custom_rules = self._load_custom_rules()
        self.observer = None
        self.running = False
        self.scheduler_running = False
        self._setup_workspace()
        self._setup_preview_temp()

    def _setup_workspace(self):
        """Initialize required directories"""
        self.root_path.mkdir(exist_ok=True)
        (self.root_path / "Duplicates").mkdir(exist_ok=True)

    def _setup_preview_temp(self):
        """Create directory for preview thumbnails"""
        PREVIEW_TEMP.mkdir(exist_ok=True)

    def _load_custom_rules(self):
        """Load user-defined organization rules"""
        config_path = Path.home() / ".file_organizer_config.json"
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def organize_existing_files(self, progress_callback=None):
        """Organize existing files with progress reporting"""
        files = list(self.root_path.glob("*.*"))
        for idx, file_path in enumerate(files):
            if file_path.is_file():
                self._process_file(file_path)
                if progress_callback:
                    progress_callback((idx + 1) / len(files))

    def start_real_time_monitoring(self):
        """Begin watching directory for real-time organization"""
        event_handler = FileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.root_path, recursive=False)
        self.observer.start()
        self.running = True

    def stop_real_time_monitoring(self):
        """Stop directory watcher"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.running = False

    def _process_file(self, file_path):
        """Main file processing logic"""
        if self._is_duplicate(file_path):
            self._handle_duplicate(file_path)
            return

        category = self._determine_category(file_path)
        target_dir = self.root_path / category
        target_dir.mkdir(exist_ok=True)
        
        try:
            shutil.move(str(file_path), str(target_dir))
        except PermissionError:
            pass  # Handle locked files gracefully

    def generate_preview(self, file_path):
        """Generate preview for supported file types"""
        preview_path = PREVIEW_TEMP / f"preview_{file_path.name}"
        try:
            if file_path.suffix.lower() in [".jpg", ".png", ".webp"]:
                self._generate_image_preview(file_path, preview_path)
            elif file_path.suffix == ".pdf":
                self._generate_pdf_preview(file_path, preview_path)
            elif file_path.suffix == ".txt":
                self._generate_text_preview(file_path, preview_path)
            return preview_path
        except Exception as e:
            return None

    def _generate_image_preview(self, src, dest):
        with Image.open(src) as img:
            img.thumbnail((200, 200))
            img.save(dest, "PNG")

    def _generate_pdf_preview(self, src, dest):
        with pdfplumber.open(src) as pdf:
            first_page = pdf.pages[0]
            im = first_page.to_image()
            im.save(dest, "PNG")

    def _generate_text_preview(self, src, dest):
        with open(src, "r") as f:
            content = f.read(500) 
        with open(dest, "w") as f:
            f.write(content)

    def _determine_category(self, file_path):
        """Determine file category using multiple strategies"""
        for pattern, category in self.custom_rules.items():
            if pattern in file_path.name.lower():
                return category
        
        ext = file_path.suffix.lower()
        for category, extensions in CATEGORIES.items():
            if ext in extensions:
                return category
        
        return "Miscellaneous"

    def _is_duplicate(self, file_path):
        """Check for duplicate files using content hashing"""
        file_hash = self._generate_file_hash(file_path)
        for existing_file in self.root_path.rglob("*.*"):
            if existing_file != file_path and file_hash == self._generate_file_hash(existing_file):
                return True
        return False

    def _generate_file_hash(self, file_path, block_size=65536):
        """Generate MD5 hash of file contents"""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                hasher.update(block)
        return hasher.hexdigest()

    def _handle_duplicate(self, file_path):
        """Move duplicate to dedicated folder with timestamp"""
        timestamp = int(time.time())
        new_name = f"{timestamp}_{file_path.name}"
        dest = self.root_path / "Duplicates" / new_name
        shutil.move(str(file_path), str(dest))

class TrayManager:
    """Handles system tray integration and notifications"""
    
    def __init__(self, app):
        self.app = app
        self.icon = pystray.Icon(
            "file_organizer",
            icon=self._create_icon(),
            menu=pystray.Menu(
                pystray.MenuItem("Open", self.restore_app),
                pystray.MenuItem("Exit", self.exit_app)
            )
        )
        
    def _create_icon(self):
        """Create system tray icon"""
        image = Image.new("RGB", (64, 64), "white")
        dc = ImageDraw.Draw(image)
        dc.rectangle([0, 0, 63, 63], fill="blue")
        return image

    def run(self):
        """Start tray icon in background thread"""
        threading.Thread(target=self.icon.run, daemon=True).start()

    def restore_app(self):
        """Restore main application window"""
        self.app.after(0, self.app.deiconify)

    def exit_app(self):
        """Clean shutdown procedure"""
        self.app.organizer.stop_real_time_monitoring()
        self.app.destroy()
        self.icon.stop()

# ---------------------------- GUI Interface ----------------------------
class FileOrganizerApp(ctk.CTk):
    """Modern GUI with all enhanced features"""
    
    def __init__(self):
        super().__init__()
        self.organizer = None
        self._setup_ui()
        self._load_settings()
        self.tray = TrayManager(self)
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.tray.run()

    def _setup_ui(self):
        """Configure window and widgets"""
        self.title("File Organizer Pro  🗂️")
        self.geometry("1000x800")
        ctk.set_appearance_mode("System")
        
        # Folder selection
        self.folder_frame = ctk.CTkFrame(self)
        self.folder_frame.pack(pady=20, padx=20, fill="x")
        
        self.folder_label = ctk.CTkLabel(self.folder_frame, text="Selected Folder:")
        self.folder_label.pack(side="left", padx=10)
        
        self.folder_entry = ctk.CTkEntry(self.folder_frame, width=400)
        self.folder_entry.pack(side="left", fill="x", expand=True)
        
        self.browse_btn = ctk.CTkButton(
            self.folder_frame, 
            text="📁 Browse",
            command=self._select_folder
        )
        self.browse_btn.pack(side="right", padx=10)

        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(pady=10, fill="x", padx=20)
        
        self.schedule_frame = ctk.CTkFrame(self)
        self.schedule_frame.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkButton(
            self.schedule_frame,
            text="⏰ Schedule Cleanup",
            command=self._show_schedule_dialog
        ).pack(side="left", padx=5)
        
        self.schedule_status = ctk.CTkLabel(self.schedule_frame, text="No active schedules")
        self.schedule_status.pack(side="right", padx=10)

        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.preview_label = ctk.CTkLabel(self.preview_frame, text="Preview Pane")
        self.preview_label.pack()
        
        self.preview_content = ctk.CTkLabel(self.preview_frame, text="")
        self.preview_content.pack(fill="both", expand=True)

        self.log = ctk.CTkTextbox(self, wrap="word")
        self.log.pack(pady=20, padx=20, fill="both", expand=True)
        self.log.insert("end", "File Organizer Pro Ready\n")
        self.log.bind("<Button-3>", self._show_preview_menu)

        self.btn_frame = ctk.CTkFrame(self)
        self.btn_frame.pack(pady=10)
        
        self.organize_btn = ctk.CTkButton(
            self.btn_frame,
            text="🚀 Organize Existing Files",
            command=self._organize_existing
        )
        self.organize_btn.pack(side="left", padx=5)
        
        self.monitor_btn = ctk.CTkButton(
            self.btn_frame,
            text="👁️ Toggle Real-Time Monitoring",
            command=self._toggle_monitoring
        )
        self.monitor_btn.pack(side="left", padx=5)

    def minimize_to_tray(self):
        """Minimize window to system tray"""
        self.withdraw()

    def _select_folder(self):
        """Handle folder selection dialog"""
        path = ctk.filedialog.askdirectory()
        if path:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, path)
            self.organizer = FileOrganizerEngine(path)
            self._log_action(f"Monitoring folder: {path}")

    def _organize_existing(self):
        """Handle organize existing files action"""
        if not self.organizer:
            return
            
        def organize_thread():
            self.organizer.organize_existing_files(
                lambda p: self.progress.set(p)
            )
            self._log_action("Finished organizing existing files!")
            
        threading.Thread(target=organize_thread, daemon=True).start()

    def _toggle_monitoring(self):
        """Toggle real-time file monitoring"""
        if self.organizer.running:
            self.organizer.stop_real_time_monitoring()
            self._log_action("Stopped real-time monitoring")
        else:
            self.organizer.start_real_time_monitoring()
            self._log_action("Started real-time monitoring")

    def _show_preview_menu(self, event):
        """Right-click menu for file preview"""
        index = self.log.index(f"@{event.x},{event.y}")
        line = self.log.get(index + " linestart", index + " lineend")
        
        if "Moved:" in line:
            file_path = line.split("Moved: ")[-1].strip()
            menu = Menu(self, tearoff=0)
            menu.add_command(label="Preview", command=lambda: self.show_preview(file_path))
            menu.add_command(label="Open File", command=lambda: webbrowser.open(file_path))
            menu.tk_popup(event.x_root, event.y_root)

    def show_preview(self, file_path):
        """Display file preview"""
        preview_path = self.organizer.generate_preview(Path(file_path))
        if preview_path:
            if Path(file_path).suffix.lower() in [".jpg", ".png", ".pdf"]:
                img = ctk.CTkImage(Image.open(preview_path), size=(200, 200))
                self.preview_content.configure(image=img, text="")
            else:
                with open(preview_path, "r") as f:
                    self.preview_content.configure(image=None, text=f.read())
        else:
            self.preview_content.configure(text="Preview not available")

    def _show_schedule_dialog(self):
        """Schedule configuration dialog"""
        dialog = ctk.CTkInputDialog(
            text="Enter schedule (e.g., 'daily at 22:00'):",
            title="Schedule Cleanup"
        )
        schedule_str = dialog.get_input()
        if schedule_str:
            self._save_schedule(schedule_str)
            self._start_scheduler()

    def _save_schedule(self, schedule_str):
        """Store schedule configuration"""
        with open(SCHEDULE_CONFIG, "w") as f:
            json.dump({"schedule": schedule_str}, f)
        self.schedule_status.configure(text=f"Next: {schedule_str}")

    def _start_scheduler(self):
        """Initialize scheduled tasks"""
        schedule.clear()
        with open(SCHEDULE_CONFIG, "r") as f:
            config = json.load(f)
        
        if "daily at" in config["schedule"]:
            time_str = config["schedule"].split("at ")[-1]
            schedule.every().day.at(time_str).do(self._run_scheduled_cleanup)
        
        def scheduler_thread():
            while True:
                schedule.run_pending()
                time.sleep(60)
        
        threading.Thread(target=scheduler_thread, daemon=True).start()

    def _run_scheduled_cleanup(self):
        """Execute scheduled organization"""
        self._log_action("Starting scheduled cleanup...")
        self.organizer.organize_existing_files()
        self._log_action("Scheduled cleanup completed")
        self.tray.icon.notify("Scheduled cleanup completed", "File Organizer Pro")

    def _load_settings(self):
        """Load user preferences from system storage"""
        saved_path = keyring.get_password("file_organizer", "last_path")
        if saved_path:
            self.folder_entry.insert(0, saved_path)
            self.organizer = FileOrganizerEngine(saved_path)

    def _log_action(self, message):
        """Add timestamped message to activity log"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {message}\n")
        self.log.see("end")

if __name__ == "__main__":
    app = FileOrganizerApp()
    app.mainloop()