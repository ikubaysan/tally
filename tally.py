import keyboard
import threading
from datetime import datetime
import os
import json


# =========================
# Objective Class
# =========================

class Objective:

    def __init__(self, name="Default Objective", target=None):

        self.name = name
        self.target = target

        self.count = 0
        self.attempts = 0
        self.resets = 0

        self.start_time = datetime.now()
        self.last_action_time = None
        self.last_action_type = None

        self.completed = False
        self.completed_time = None

    # =========================
    # Completion check
    # =========================

    def _check_completion(self):

        if (
            self.target is not None
            and not self.completed
            and self.count == self.target
        ):
            self.completed = True
            self.completed_time = datetime.now()

    # =========================
    # Actions
    # =========================

    def increment(self):

        if self.completed:
            return

        self.count += 1
        self.attempts += 1

        self.last_action_time = datetime.now()
        self.last_action_type = "Inc"

        self._check_completion()

    def decrement(self):

        if self.completed:
            return

        self.count -= 1
        self.attempts -= 1   # ✅ FIXED: now decreases

        self.last_action_time = datetime.now()
        self.last_action_type = "Dec"

    def reset(self):

        if self.completed:
            return

        self.count = 0
        self.resets += 1

        self.last_action_time = datetime.now()
        self.last_action_type = "Reset"

    # =========================
    # Time
    # =========================

    def get_elapsed_time(self):

        end = self.completed_time or datetime.now()
        return end - self.start_time

    def get_elapsed_str(self):

        total = int(self.get_elapsed_time().total_seconds())

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        return f"{h:02}:{m:02}:{s:02}"

    # =========================
    # Stats
    # =========================

    def get_final_stats(self):

        return (
            f"\n--- FINAL STATS ---\n"
            f"Objective: {self.name}\n"
            f"Target: {self.target}\n"
            f"Final Count: {self.count}\n"
            f"Attempts: {self.attempts}\n"
            f"Resets: {self.resets}\n"
            f"Total Time: {self.get_elapsed_str()}\n"
        )

    def to_dict(self):

        return {
            "name": self.name,
            "target": self.target,
            "final_count": self.count,
            "attempts": self.attempts,
            "resets": self.resets,
            "completed": self.completed,
            "start_time": self.start_time.isoformat(),
            "completed_time": (
                self.completed_time.isoformat()
                if self.completed_time else None
            ),
            "elapsed_seconds": int(
                self.get_elapsed_time().total_seconds()
            ),
        }


# =========================
# Manager
# =========================

class ObjectiveManager:

    DEFAULT_KEYS = {
        "increment": ["up"],
        "decrement": ["down"],
        "reset": ["left", "right"],
        "new_objective": ["n"],
        "exit": ["esc"],
    }

    ACTION_DISPLAY_NAMES = {
        "increment": "Increment",
        "decrement": "Decrement",
        "reset": "Reset",
        "new_objective": "New Objective",
        "exit": "Exit",
    }

    def __init__(self, key_bindings=None):

        self.key_bindings = key_bindings or self.DEFAULT_KEYS

        self.objectives = []
        self.current_objective = None

        self.lock = threading.Lock()

        self._create_default_objective()

    # =========================
    # Default objective
    # =========================

    def _create_default_objective(self):

        obj = Objective()

        self.objectives.append(obj)
        self.current_objective = obj

    # =========================
    # Export
    # =========================

    def _export_objective(self, obj):

        os.makedirs("results", exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        filename = f"results/{obj.name}_{timestamp}.json"
        filename = filename.replace(" ", "_")

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(obj.to_dict(), f, indent=4)

        print(f"\n📁 Results saved to: {filename}")
        print("✔ Objective results exported successfully.")

    # =========================
    # Completion
    # =========================

    def _handle_completion(self, obj):

        print(obj.get_final_stats())
        self._export_objective(obj)

    # =========================
    # Create objective
    # =========================

    def create_new_objective(self):

        print("\n--- Create New Objective ---")

        while True:
            name = input("Enter objective name: ").strip()
            if name:
                break
            print("Name cannot be empty.")

        while True:
            target_input = input(
                "Enter target goal (blank for none): "
            ).strip()

            if target_input == "":
                target = None
                break

            if not target_input.isdigit():
                print("Must be a positive integer.")
                continue

            target = int(target_input)

            if target <= 0:
                print("Must be > 0.")
                continue

            break

        obj = Objective(name, target)

        self.objectives.append(obj)
        self.current_objective = obj

        print(f"Objective '{name}' created.")

    # =========================
    # Display
    # =========================

    def _print_status(self, action=""):

        obj = self.current_objective

        last = "None"

        if obj.last_action_time and obj.last_action_type:
            t = obj.last_action_time.strftime("%H:%M:%S")
            last = f"{obj.last_action_type} @ {t}"

        target = f"/{obj.target}" if obj.target else ""

        line = (
            f"Objective: {obj.name} | "
            f"Count: {obj.count}{target} | "
            f"Attempts: {obj.attempts} | "
            f"Resets: {obj.resets} | "
            f"Elapsed Time: {obj.get_elapsed_str()} | "
            f"Last Action: {last}"
        )

        print("\r" + line + " " * 10, end="", flush=True)

    # =========================
    # Actions
    # =========================

    def increment(self):

        with self.lock:

            obj = self.current_objective
            obj.increment()

            self._print_status()

            if obj.completed:
                self._handle_completion(obj)

    def decrement(self):

        with self.lock:

            obj = self.current_objective
            obj.decrement()

            self._print_status()

    def reset(self):

        with self.lock:

            obj = self.current_objective
            obj.reset()

            self._print_status()

    # =========================
    # Hotkeys
    # =========================

    def register_hotkeys(self):

        for action, keys in self.key_bindings.items():

            for key in keys:

                if action == "increment":
                    keyboard.add_hotkey(key, self.increment)

                elif action == "decrement":
                    keyboard.add_hotkey(key, self.decrement)

                elif action == "reset":
                    keyboard.add_hotkey(key, self.reset)

                elif action == "new_objective":
                    keyboard.add_hotkey(key, self.create_new_objective)

    def wait_for_exit(self):

        keyboard.wait(self.key_bindings["exit"][0])

    # =========================
    # Run
    # =========================

    def run(self):

        print("Objective Tracker Started\n")

        print("Key Bindings:")

        for k, v in self.key_bindings.items():
            name = self.ACTION_DISPLAY_NAMES.get(
                k, k.replace("_", " ").title()
            )
            print(f"  {name:15} -> {', '.join(v)}")

        print("\nCommands: N = New Objective\n")

        self.register_hotkeys()

        self._print_status()

        self.wait_for_exit()

        print("\nExiting...")


# =========================
# Entry point
# =========================

if __name__ == "__main__":

    KEY_BINDINGS = {
        "increment": ["up"],
        "decrement": ["down"],
        "reset": ["left", "right"],
        "new_objective": ["n"],
        "exit": ["esc"],
    }

    manager = ObjectiveManager(KEY_BINDINGS)
    manager.run()