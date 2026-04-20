import keyboard
import sqlite3
import threading
from datetime import datetime
from WindowController import WindowController
import time
import os
import shutil
import re
import atexit

from obsws_python import ReqClient


DB_FILE = "tally.db"
WINDOW_TITLE_KEYWORDS = ["NPUB30769"]

# =========================
# NEW CONSTANT
# =========================

RECORD_SESSIONS = True

OBS_HOST = "localhost"
OBS_PORT = 4455
OBS_PASSWORD = "your_password"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =========================
# Utilities
# =========================

def filesafe(text):
    """Make string safe for filenames."""
    text = text.strip()
    text = re.sub(r'[<>:"/\\|?*]', "_", text)
    text = re.sub(r"\s+", "_", text)
    return text


# =========================
# OBS Recorder
# =========================

class OBSRecorder:

    def __init__(self):

        self.client = None
        self.recording = False

        if RECORD_SESSIONS:
            self.client = ReqClient(
                host=OBS_HOST,
                port=OBS_PORT,
                password=OBS_PASSWORD
            )

    def start(self):

        if not RECORD_SESSIONS:
            return

        if self.recording:
            return

        self.client.start_record()

        self.recording = True

        print("\n[OBS] Recording started")

    def stop(self):

        if not RECORD_SESSIONS:
            return None

        if not self.recording:
            return None

        response = self.client.stop_record()

        self.recording = False

        path = response.output_path

        print(f"\n[OBS] Recording saved: {path}")

        return path


# =========================
# Input Manager
# =========================

class InputManager:

    def __init__(self):

        self.config = {
            "keyboard": {
                "success": "up",
                "failure": "down",
                "early_end": "ctrl+q"
            }
        }

        self.keyboard_hooks = []


    def print_bindings(self):

        kb = self.config["keyboard"]

        print("\nKey Bindings:")
        print(f"  Success   : {kb['success']}")
        print(f"  Failure   : {kb['failure']}")
        print(f"  Early End : {kb['early_end']}")
        print()

    def bind_keyboard(self, tracker):

        self.keyboard_hooks.append(
            keyboard.add_hotkey(
                self.config["keyboard"]["success"],
                tracker.success
            )
        )

        self.keyboard_hooks.append(
            keyboard.add_hotkey(
                self.config["keyboard"]["failure"],
                tracker.failure
            )
        )

        self.keyboard_hooks.append(
            keyboard.add_hotkey(
                self.config["keyboard"]["early_end"],
                tracker.early_end_session
            )
        )

    def unbind_keyboard(self):

        for h in self.keyboard_hooks:
            keyboard.remove_hotkey(h)

        self.keyboard_hooks.clear()


# =========================
# Database (unchanged)
# =========================

class Database:

    def __init__(self):

        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._setup()

    def _setup(self):

        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            video_path TEXT,
            FOREIGN KEY(objective_id)
                REFERENCES objectives(id)
                ON DELETE CASCADE
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            result INTEGER NOT NULL,
            FOREIGN KEY(objective_id)
                REFERENCES objectives(id)
                ON DELETE CASCADE,
            FOREIGN KEY(session_id)
                REFERENCES sessions(id)
                ON DELETE CASCADE
        )
        """)

        # Migration safety (adds column if missing)

        cur.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cur.fetchall()]

        if "video_path" not in columns:
            cur.execute("""
            ALTER TABLE sessions
            ADD COLUMN video_path TEXT
            """)

            print("[DB] Added video_path column")

        self.conn.commit()

    def set_session_video_path(self, session_id, path):

        self.conn.execute("""
        UPDATE sessions
        SET video_path = ?
        WHERE id = ?
        """, (
            path,
            session_id
        ))

        self.conn.commit()

    def get_objectives(self):

        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM objectives ORDER BY name COLLATE NOCASE")
        return cur.fetchall()

    def add_objective(self, name):

        try:
            self.conn.execute(
                "INSERT INTO objectives (name) VALUES (?)",
                (name,)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def create_session(self, objective_id):

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO sessions (objective_id, start_time)
        VALUES (?, ?)
        """, (
            objective_id,
            datetime.now().isoformat()
        ))

        self.conn.commit()
        return cur.lastrowid

    def log_attempt(
        self,
        objective_id,
        session_id,
        start_time,
        end_time,
        result
    ):

        self.conn.execute("""
        INSERT INTO attempts (
            objective_id,
            session_id,
            start_time,
            end_time,
            result
        ) VALUES (?, ?, ?, ?, ?)
        """, (
            objective_id,
            session_id,
            start_time,
            end_time,
            result
        ))

        self.conn.commit()


# =========================
# Session
# =========================

class Session:

    def __init__(self, obj_id, name, target, db):

        self.objective_id = obj_id
        self.name = name
        self.target = target
        self.db = db

        self.successes = 0
        self.failures = 0

        self.start_time = datetime.now()
        self.completed = False

        self.session_id = None
        self.last_attempt_time = datetime.now()

    def elapsed_str(self):

        delta = datetime.now() - self.start_time

        total = int(delta.total_seconds())

        return f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02}"

    def total_attempts(self):
        return self.successes + self.failures

    def success_rate(self):

        total = self.total_attempts()

        if total == 0:
            return 0

        return round((self.successes / total) * 100)

    def _ensure_session(self):

        if self.session_id is None:
            self.session_id = self.db.create_session(
                self.objective_id
            )

    def _log_attempt(self, result):

        now = datetime.now()

        self.db.log_attempt(
            self.objective_id,
            self.session_id,
            self.last_attempt_time.isoformat(),
            now.isoformat(),
            result
        )

        self.last_attempt_time = now

    def success(self):

        if self.completed:
            return

        self._ensure_session()

        self.successes += 1
        self._log_attempt(1)

        if self.successes >= self.target:
            self.completed = True

    def failure(self):

        if self.completed:
            return

        self._ensure_session()

        self.failures += 1
        self._log_attempt(0)


# =========================
# Tracker
# =========================

class Tracker:

    def __init__(self):

        self.window_controller = WindowController(
            title_keywords=WINDOW_TITLE_KEYWORDS,
            hotkey=("ctrl", "r")
        )

        self.db = Database()
        self.input_manager = InputManager()
        self.obs = OBSRecorder()

        self.lock = threading.Lock()

        self.session = None
        self.last_completed_objective = None

        atexit.register(self.cleanup)

    # -------------------------
    def copy_recording(self, original_path):

        if not original_path:
            return

        s = self.session

        obj_safe = filesafe(s.name)

        folder = os.path.join(
            SCRIPT_DIR,
            "recordings",
            obj_safe
        )

        os.makedirs(folder, exist_ok=True)

        timestamp = s.start_time.strftime("%Y-%m-%d_%H-%M-%S")

        filename = (
            f"{timestamp}"
            f"__{obj_safe}"
            f"__target{s.target}"
            f"__attempts{s.total_attempts()}"
            f"__success{s.successes}"
            f"__fail{s.failures}"
            f"__successrate{s.success_rate()}pct"
            ".mp4"
        )

        dest_path = os.path.join(folder, filename)

        shutil.copy2(original_path, dest_path)

        print(f"[OBS] Copied to: {dest_path}")

        # Store RELATIVE path in DB

        relative_path = os.path.relpath(
            dest_path,
            SCRIPT_DIR
        )

        if s.session_id:
            self.db.set_session_video_path(
                s.session_id,
                relative_path
            )

            print(
                f"[DB] Stored video path: "
                f"{relative_path}"
            )
    # -------------------------

    def finalize_session(self):

        video_path = self.obs.stop()

        if video_path:
            self.copy_recording(video_path)

    # -------------------------

    def early_end_session(self):

        with self.lock:

            if self.session is None:
                return

            print("\n\n[EARLY END]")

            self.session.completed = True

            self.handle_completion()

    # -------------------------

    def choose_objective(self):

        self.input_manager.unbind_keyboard()

        while True:

            objs = self.db.get_objectives()

            print("\nAvailable Objectives:\n")

            width = len(str(len(objs)))

            for i, (_, name) in enumerate(objs, 1):
                print(f"  {i:>{width}}. {name}")

            if self.last_completed_objective:
                name, obj_id = self.last_completed_objective
                print(f"\n  ✔ Last Completed: {obj_id - 1}. {name}\n")

            choice = input("\nChoice: ").strip()

            if choice.isdigit():

                idx = int(choice)

                if 1 <= idx <= len(objs):

                    obj_id, name = objs[idx - 1]
                    target = 10

                    self.session = Session(
                        obj_id,
                        name,
                        target,
                        self.db
                    )

                    self.obs.start()

                    self.input_manager.bind_keyboard(self)

                    print("\n" + "=" * 40)

                    print(f"Started Session: {name}")
                    print(f"Target Successes: {target}")

                    self.input_manager.print_bindings()

                    print("=" * 40)

                    print(f"\nStarted: {name}")
                    return

    # -------------------------

    def show(self):

        s = self.session

        print(
            f"\rObjective: {s.name} | "
            f"Success: {s.successes}/{s.target} | "
            f"Fail: {s.failures} | "
            f"Time: {s.elapsed_str()}",
            end=""
        )

    # -------------------------


    def handle_completion(self):

        if not self.session.completed:
            return

        self.last_completed_objective = (self.session.name, self.session.objective_id)

        print("\n\n--- COMPLETE ---")
        print(f"Objective: {self.session.name}")
        print(f"Success: {self.session.successes}")
        print(f"Fail: {self.session.failures}")
        print(self.session.name)

        self.finalize_session()

        self.input_manager.unbind_keyboard()

        self.choose_objective()

    # -------------------------

    def success(self):

        with self.lock:

            if self.session is None:
                return

            self.session.success()
            self.show()

            if not self.session.completed:
                self.window_controller.send_hotkey()

            self.handle_completion()

    def failure(self):

        with self.lock:

            if self.session is None:
                return

            self.session.failure()
            self.show()

            self.window_controller.send_hotkey()
    # -------------------------

    def cleanup(self):

        print("\n[Shutdown] Cleaning up...")

        if self.session:
            self.finalize_session()

    # -------------------------

    def run(self):

        print("Started")

        self.choose_objective()

        while True:
            time.sleep(0.1)


# =========================

if __name__ == "__main__":
    Tracker().run()