import keyboard
import sqlite3
import threading
from datetime import datetime
from WindowController import WindowController
import time


DB_FILE = "tally.db"
WINDOW_TITLE_KEYWORDS = ["NPUB30769"]


# =========================
# Database
# =========================

class Database:

    def __init__(self):

        self.conn = sqlite3.connect(
            DB_FILE,
            check_same_thread=False
        )

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

        try:
            cur.execute("ALTER TABLE attempts ADD COLUMN end_time TEXT")
        except sqlite3.OperationalError:
            pass

        cur.execute("""
        INSERT OR IGNORE INTO objectives (name)
        VALUES ('default')
        """)

        self.conn.commit()

    def get_objectives(self):

        cur = self.conn.cursor()

        cur.execute("""
        SELECT id, name
        FROM objectives
        ORDER BY name COLLATE NOCASE
        """)

        return cur.fetchall()

    def add_objective(self, name):

        cur = self.conn.cursor()

        try:
            cur.execute("""
            INSERT INTO objectives (name)
            VALUES (?)
            """, (name,))

            self.conn.commit()
            return True

        except sqlite3.IntegrityError:
            return False

    def remove_objective(self, obj_id):

        cur = self.conn.cursor()

        cur.execute("""
        DELETE FROM objectives
        WHERE id = ?
        """, (obj_id,))

        self.conn.commit()

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

    def log_attempt(self, objective_id, session_id, start_time, end_time, result):

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO attempts (
            objective_id,
            session_id,
            start_time,
            end_time,
            result
        )
        VALUES (?, ?, ?, ?, ?)
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

    def _ensure_session(self):

        if self.session_id is None:
            self.session_id = self.db.create_session(self.objective_id)

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

    def elapsed_str(self):

        delta = datetime.now() - self.start_time

        total = int(delta.total_seconds())

        return f"{total//3600:02}:{(total%3600)//60:02}:{total%60:02}"


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

        self.lock = threading.Lock()
        self.locked = False

        self.session = None
        self.last_selected = None

        self.up_hook = None
        self.down_hook = None

    # -------------------------

    def enable_hotkeys(self):

        self.up_hook = keyboard.add_hotkey("up", self.success)
        self.down_hook = keyboard.add_hotkey("down", self.failure)

    def disable_hotkeys(self):

        if self.up_hook:
            keyboard.remove_hotkey(self.up_hook)
            self.up_hook = None

        if self.down_hook:
            keyboard.remove_hotkey(self.down_hook)
            self.down_hook = None

    # -------------------------

    def print_bindings(self):

        print("Key Bindings:")
        print("  Success -> up")
        print("  Failure -> down")

    # -------------------------

    def choose_objective(self):

        self.disable_hotkeys()

        while True:

            objectives = self.db.get_objectives()

            print("\nAvailable Objectives:\n")

            width = len(str(len(objectives)))

            for idx, (_, name) in enumerate(objectives, start=1):
                print(f"  {idx:>{width}}. {name}")

            print("\nOptions:")
            print("  [number] Choose objective")
            print("  A        Add objective")
            print("  R        Remove objective")

            choice = input("\nChoice: ").strip().lower()

            if choice.isdigit():

                num = int(choice)

                if not (1 <= num <= len(objectives)):
                    continue

                obj_id, name = objectives[num - 1]

                target = self._ask_target()

                self.session = Session(obj_id, name, target, self.db)

                self.enable_hotkeys()

                print(f"\nStarted: {name} (target: {target})\n")
                return

            elif choice == "a":
                self._add_objective()

            elif choice == "r":
                self._remove_objective()

    # -------------------------

    def _ask_target(self):

        val = input("Enter target (default 10): ").strip()

        return int(val) if val.isdigit() else 10

    # -------------------------

    def _add_objective(self):

        name = input("Enter new objective name: ").strip()

        if name:
            self.db.add_objective(name)

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

        self.locked = True

        print("\n\n--- COMPLETE ---")
        print(f"Objective: {self.session.name}")
        print(f"Success: {self.session.successes}")
        print(f"Fail: {self.session.failures}")

        self.disable_hotkeys()
        self.choose_objective()

        self.locked = False

    # -------------------------

    def success(self):

        with self.lock:

            if self.locked or self.session is None:
                return

            self.session.success()
            self.show()

            if not self.session.completed:
                self.window_controller.send_hotkey()

            self.handle_completion()

    def failure(self):

        with self.lock:

            if self.locked or self.session is None:
                return

            self.session.failure()
            self.show()

            self.window_controller.send_hotkey()

    # -------------------------

    def run(self):

        print("Started\n")
        self.print_bindings()
        self.choose_objective()

        while True:
            time.sleep(0.1)


# =========================

if __name__ == "__main__":
    Tracker().run()