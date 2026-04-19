import keyboard
import sqlite3
import threading
from datetime import datetime
from WindowController import WindowController
import time
import json
import pygame


DB_FILE = "tally.db"
WINDOW_TITLE_KEYWORDS = ["NPUB30769"]
INPUT_CONFIG_FILE = "input_bindings.json"


# =========================
# Input Manager
# =========================

class InputManager:

    def __init__(self):

        pygame.init()
        pygame.joystick.init()

        self.config = {
            "keyboard": {
                "success": "up",
                "failure": "down"
            },
            "controllers": {}
        }

        self.keyboard_hooks = []
        self.running = True

        self.load()

    # -------------------------

    def load(self):

        try:
            with open(INPUT_CONFIG_FILE, "r") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            pass

    def save(self):

        with open(INPUT_CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    # -------------------------

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

    def unbind_keyboard(self):

        for h in self.keyboard_hooks:
            keyboard.remove_hotkey(h)

        self.keyboard_hooks.clear()

    # -------------------------

    def _refresh_joysticks(self):

        pygame.joystick.quit()
        pygame.joystick.init()

        print("\nDetected controllers:")

        for i in range(pygame.joystick.get_count()):
            js = pygame.joystick.Joystick(i)
            js.init()
            print(f"  [{i}] {js.get_name()} (instance_id={js.get_instance_id()})")

    # -------------------------

    def listen_for_controller_bind(self):

        print("\n--- Controller Binding Mode ---")

        self._refresh_joysticks()

        print("\nPress SUCCESS button (ESC to cancel)...")
        success = self._wait_for_button()
        if success is None:
            return False

        print("Press FAILURE button (ESC to cancel)...")
        failure = self._wait_for_button()
        if failure is None:
            return False

        joy_id = str(success["instance_id"])

        self.config["controllers"][joy_id] = {
            "name": success["name"],
            "success": success["button"],
            "failure": failure["button"]
        }

        self.save()

        print(f"\n✔ Bound controller: {success['name']}")
        return True

    # -------------------------

    def _wait_for_button(self):

        while True:

            pygame.event.pump()

            for event in pygame.event.get():

                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None

                if event.type == pygame.JOYBUTTONDOWN:

                    joy = pygame.joystick.Joystick(event.joy)
                    joy.init()

                    print(f"Detected button {event.button} on {joy.get_name()}")

                    return {
                        "instance_id": joy.get_instance_id(),
                        "joy_index": event.joy,
                        "name": joy.get_name(),
                        "button": event.button
                    }


# =========================
# Database
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

        cur.execute("""
        INSERT OR IGNORE INTO objectives (name)
        VALUES ('default')
        """)

        self.conn.commit()

    def get_objectives(self):

        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM objectives ORDER BY name COLLATE NOCASE")
        return cur.fetchall()

    def add_objective(self, name):

        try:
            self.conn.execute("INSERT INTO objectives (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_objective(self, obj_id):

        self.conn.execute("DELETE FROM objectives WHERE id = ?", (obj_id,))
        self.conn.commit()

    def create_session(self, objective_id):

        cur = self.conn.cursor()

        cur.execute("""
        INSERT INTO sessions (objective_id, start_time)
        VALUES (?, ?)
        """, (objective_id, datetime.now().isoformat()))

        self.conn.commit()
        return cur.lastrowid

    def log_attempt(self, objective_id, session_id, start_time, end_time, result):

        self.conn.execute("""
        INSERT INTO attempts (
            objective_id, session_id, start_time, end_time, result
        ) VALUES (?, ?, ?, ?, ?)
        """, (objective_id, session_id, start_time, end_time, result))

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
        t = int(delta.total_seconds())
        return f"{t//3600:02}:{(t%3600)//60:02}:{t%60:02}"


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

        self.lock = threading.Lock()
        self.locked = False

        self.session = None
        self.keyboard_enabled = False

        self.last_completed_objective = None

    # -------------------------

    def enable_inputs(self):

        self.input_manager.bind_keyboard(self)
        self.keyboard_enabled = True

    def disable_inputs(self):

        self.input_manager.unbind_keyboard()
        self.keyboard_enabled = False

    # -------------------------

    def print_menu(self):

        print("\nOptions:")
        print("  [number] Choose objective")
        print("  A        Add objective")
        print("  R        Remove objective")
        print("  C        Bind controller")

    # -------------------------

    def choose_objective(self):

        self.disable_inputs()

        while True:

            objs = self.db.get_objectives()

            print("\nAvailable Objectives:\n")

            width = len(str(len(objs)))  # auto-align based on list size

            for i, (_, name) in enumerate(objs, 1):
                print(f"  {i:>{width}}. {name}")

            if self.last_completed_objective:
                name, obj_id = self.last_completed_objective
                print(f"\n  ✔ Last Completed: {name} (ID {obj_id})\n")

            self.print_menu()

            choice = input("\nChoice: ").strip().lower()

            if choice.isdigit():

                idx = int(choice)

                if 1 <= idx <= len(objs):

                    obj_id, name = objs[idx - 1]
                    target = 10

                    self.session = Session(obj_id, name, target, self.db)

                    self.enable_inputs()

                    print(f"\nStarted: {name}")
                    return

            elif choice == "c":
                self.input_manager.listen_for_controller_bind()

            elif choice == "a":
                name = input("Name: ")
                self.db.add_objective(name)

    # -------------------------

    def show(self):

        s = self.session

        print(
            f"\r{s.name} | "
            f"{s.successes}/{s.target} | "
            f"fail {s.failures} | "
            f"{s.elapsed_str()}",
            end=""
        )

    # -------------------------

    def handle_completion(self):

        if not self.session.completed:
            return

        self.last_completed_objective = (self.session.name, self.session.objective_id)

        print("\n\n--- COMPLETE ---")
        print(self.session.name)

        self.disable_inputs()
        self.choose_objective()

    # -------------------------

    def success(self):

        with self.lock:

            if self.session is None or self.locked:
                return

            self.session.success()
            self.show()

            if not self.session.completed:
                self.window_controller.send_hotkey()

            self.handle_completion()

    def failure(self):

        with self.lock:

            if self.session is None or self.locked:
                return

            self.session.failure()
            self.show()

            self.window_controller.send_hotkey()

    # -------------------------

    def _poll_controllers(self):

        while True:

            if self.session is None:
                time.sleep(0.1)
                continue

            pygame.event.pump()

            for i in range(pygame.joystick.get_count()):

                js = pygame.joystick.Joystick(i)
                js.init()

                cid = str(js.get_instance_id())

                if cid not in self.input_manager.config["controllers"]:
                    continue

                cfg = self.input_manager.config["controllers"][cid]

                for b in range(js.get_numbuttons()):

                    if js.get_button(b):

                        if b == cfg["success"]:
                            self.success()

                        elif b == cfg["failure"]:
                            self.failure()

            time.sleep(0.01)

    # -------------------------

    def run(self):

        print("Started")

        threading.Thread(
            target=self._poll_controllers,
            daemon=True
        ).start()

        self.choose_objective()

        while True:
            time.sleep(0.1)


# =========================

if __name__ == "__main__":
    Tracker().run()