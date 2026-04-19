import keyboard
import sqlite3
import threading
from datetime import datetime
import time


DB_FILE = "tally.db"


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

    # -------------------------

    def _setup(self):

        cur = self.conn.cursor()

        # OBJECTIVES
        cur.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        """)

        # SESSIONS  🆕
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

        # ATTEMPTS (updated)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            result TEXT NOT NULL,
            FOREIGN KEY(objective_id)
                REFERENCES objectives(id)
                ON DELETE CASCADE,
            FOREIGN KEY(session_id)
                REFERENCES sessions(id)
                ON DELETE CASCADE
        )
        """)

        # Ensure default exists
        cur.execute("""
        INSERT OR IGNORE INTO objectives (name)
        VALUES ('default')
        """)

        self.conn.commit()

    # -------------------------

    def get_objectives(self):

        cur = self.conn.cursor()

        cur.execute("""
        SELECT id, name
        FROM objectives
        ORDER BY name COLLATE NOCASE
        """)

        return cur.fetchall()

    # -------------------------

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

    # -------------------------

    def remove_objective(self, obj_id):

        cur = self.conn.cursor()

        cur.execute("""
        DELETE FROM objectives
        WHERE id = ?
        """, (obj_id,))

        self.conn.commit()

    # -------------------------
    # SESSION creation (lazy)
    # -------------------------

    def create_session(self, objective_id):

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO sessions (
            objective_id,
            start_time
        )
        VALUES (?, ?)
        """, (
            objective_id,
            datetime.now().isoformat()
        ))

        self.conn.commit()

        return cur.lastrowid

    # -------------------------

    def log_attempt(
        self,
        objective_id,
        session_id,
        result
    ):

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO attempts (
            objective_id,
            session_id,
            timestamp,
            result
        )
        VALUES (?, ?, ?, ?)
        """, (
            objective_id,
            session_id,
            datetime.now().isoformat(),
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

        # Created only on first attempt
        self.session_id = None

    # -------------------------

    def _ensure_session(self):

        if self.session_id is None:

            self.session_id = self.db.create_session(
                self.objective_id
            )

    # -------------------------

    def success(self):

        if self.completed:
            return

        self._ensure_session()

        self.successes += 1

        self.db.log_attempt(
            self.objective_id,
            self.session_id,
            "success"
        )

        if self.successes >= self.target:
            self.completed = True

    # -------------------------

    def failure(self):

        if self.completed:
            return

        self._ensure_session()

        self.failures += 1

        self.db.log_attempt(
            self.objective_id,
            self.session_id,
            "failure"
        )

    # -------------------------

    def elapsed_str(self):

        delta = datetime.now() - self.start_time

        total = int(delta.total_seconds())

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        return f"{h:02}:{m:02}:{s:02}"


# =========================
# Tracker
# =========================

class Tracker:

    def __init__(self):

        self.db = Database()

        self.lock = threading.Lock()
        self.locked = False

        self.session = None

        self.key_bindings = {
            "Success": ["up"],
            "Failure": ["down"]
        }

        self._register_hotkeys()

    # -------------------------

    def print_bindings(self):

        print("Key Bindings:")

        for action, keys in self.key_bindings.items():
            print(f"  {action:<15} -> {', '.join(keys)}")

    # =========================

    def choose_objective(self):

        while True:

            objectives = self.db.get_objectives()

            print("\nAvailable Objectives:\n")

            for idx, (_, name) in enumerate(objectives, start=1):
                print(f"  {idx}. {name}")

            print("\nOptions:")
            print("  [number] Choose objective")
            print("  A        Add objective")
            print("  R        Remove objective")

            choice = input("\nChoice: ").strip().lower()

            if choice.isdigit():

                num = int(choice)

                if not (1 <= num <= len(objectives)):
                    print("Invalid number.")
                    continue

                obj_id, name = objectives[num - 1]

                target = self._ask_target()

                self.session = Session(
                    obj_id,
                    name,
                    target,
                    self.db
                )

                print(
                    f"\nStarted: {name} "
                    f"(target: {target})\n"
                )

                return

            elif choice == "a":

                self._add_objective()

            elif choice == "r":

                self._remove_objective()

            else:

                print("Invalid choice.")

    # -------------------------

    def _ask_target(self):

        while True:

            val = input(
                "Enter target (default 10): "
            ).strip()

            if val == "":
                return 10

            if not val.isdigit():
                print("Must be positive integer.")
                continue

            target = int(val)

            if target <= 0:
                print("Must be > 0.")
                continue

            return target

    # -------------------------

    def _add_objective(self):

        while True:

            name = input(
                "Enter new objective name: "
            ).strip()

            if not name:
                print("Name cannot be empty.")
                continue

            if self.db.add_objective(name):
                print("✔ Objective added.")
                return

            print("❌ Objective already exists.")

    # -------------------------

    def _remove_objective(self):

        objectives = self.db.get_objectives()

        if len(objectives) <= 1:
            print("Cannot remove last objective.")
            return

        while True:

            num = input(
                "Enter number to remove: "
            ).strip()

            if not num.isdigit():
                print("Invalid number.")
                continue

            num = int(num)

            if not (1 <= num <= len(objectives)):
                print("Out of range.")
                continue

            obj_id, name = objectives[num - 1]

            confirm = input(
                f"Delete '{name}'? (y/n): "
            ).lower()

            if confirm == "y":

                self.db.remove_objective(obj_id)

                print("✔ Objective removed.")

            return

    # =========================

    def show(self):

        s = self.session

        print(
            f"\rObjective: {s.name} | "
            f"Successes: {s.successes}/{s.target} | "
            f"Failures: {s.failures} | "
            f"Time: {s.elapsed_str()}      ",
            end=""
        )

    # =========================

    def handle_completion(self):

        s = self.session

        if not s.completed:
            return

        self.locked = True

        print("\n\n--- SESSION COMPLETE ---")

        print(f"Objective: {s.name}")
        print(f"Target: {s.target}")
        print(f"Successes: {s.successes}")
        print(f"Failures: {s.failures}")
        print(f"Time: {s.elapsed_str()}")

        self.choose_objective()

        self.locked = False

    # =========================

    def success(self):

        with self.lock:

            if self.locked:
                return

            self.session.success()

            self.show()

            self.handle_completion()

    def failure(self):

        with self.lock:

            if self.locked:
                return

            self.session.failure()

            self.show()

    # =========================

    def _register_hotkeys(self):

        keyboard.add_hotkey("up", self.success)
        keyboard.add_hotkey("down", self.failure)

    # =========================

    def run(self):

        print("Objective Tracker Started\n")

        self.print_bindings()

        self.choose_objective()

        while True:
            time.sleep(0.1)


# =========================

if __name__ == "__main__":
    Tracker().run()