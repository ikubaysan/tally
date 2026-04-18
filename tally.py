import keyboard
import threading
from datetime import datetime
import os
import json
import time

# =========================
# Objective
# =========================

class Objective:

    def __init__(self, name, target=10):

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
        self.exported = False

    # =========================
    # Completion
    # =========================

    def _check_completion(self):

        if not self.completed and self.count >= self.target:
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
        self.attempts -= 1  # <-- FIXED: now decreases

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

    def elapsed(self):

        end = self.completed_time or datetime.now()
        return end - self.start_time

    def elapsed_str(self):

        total = int(self.elapsed().total_seconds())

        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        return f"{h:02}:{m:02}:{s:02}"

    # =========================
    # Export
    # =========================

    def export(self):

        if self.exported:
            return

        os.makedirs("results", exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"results/{self.name}_{timestamp}.json"
        filename = filename.replace(" ", "_")

        elapsed = self.elapsed()

        total = int(elapsed.total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60

        data = {
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
            "elapsed_seconds": total,
            "elapsed_hms": f"{h:02}:{m:02}:{s:02}",  # ✅ NEW FIELD
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print(f"\n📁 Saved: {filename}")
        print("✔ Export complete")

        self.exported = True

    # =========================
    # Stats
    # =========================

    def print_stats(self):

        print("\n--- FINAL STATS ---")
        print(f"Objective: {self.name}")
        print(f"Target: {self.target}")
        print(f"Final Count: {self.count}")
        print(f"Attempts: {self.attempts}")
        print(f"Resets: {self.resets}")
        print(f"Total Time: {self.elapsed_str()}")


# =========================
# Tracker
# =========================

class Tracker:

    def __init__(self):

        self.lock = threading.Lock()
        self.locked = False

        self.current = None
        self.running = True

        self.key_bindings = {
            "Increment": ["up"],
            "Decrement": ["down"],
            "Reset": ["left", "right"],
        }

        self._register_hotkeys()

    # =========================
    # Display bindings
    # =========================

    def print_bindings(self):

        print("Key Bindings:")

        for action, keys in self.key_bindings.items():
            print(f"  {action:<15} -> {', '.join(keys)}")

    # =========================
    # Create objective
    # =========================

    def create_objective(self):

        print("\n--- New Objective ---")

        # -------------------------
        # Name input
        # -------------------------
        name = ""
        while not name:
            name = input("Enter objective name: ").strip()

        # -------------------------
        # Target input (NEW)
        # -------------------------
        while True:

            target_input = input("Enter target (default 10): ").strip()

            # default case
            if target_input == "":
                target = 10
                break

            # validation
            if not target_input.isdigit():
                print("❌ Please enter a positive whole number or press Enter for default.")
                continue

            target = int(target_input)

            if target <= 0:
                print("❌ Target must be greater than 0.")
                continue

            break

        # -------------------------
        # Create objective
        # -------------------------
        self.current = Objective(name=name, target=target)

        print(f"Started: {name} (target: {target})\n")

    # =========================
    # Display
    # =========================

    def show(self):

        obj = self.current

        last = "None"

        if obj.last_action_time:
            t = obj.last_action_time.strftime("%H:%M:%S")
            last = f"{obj.last_action_type} @ {t}"

        print(
            f"\rObjective: {obj.name} | "
            f"Count: {obj.count}/{obj.target} | "
            f"Attempts: {obj.attempts} | "
            f"Resets: {obj.resets} | "
            f"Time: {obj.elapsed_str()} | "
            f"Last: {last}      ",
            end=""
        )

    # =========================
    # Completion flow
    # =========================

    def handle_completion(self):

        obj = self.current

        if not obj.completed or obj.exported:
            return

        self.locked = True

        print("\n")
        obj.print_stats()
        obj.export()

        self.create_objective()

        self.locked = False

    # =========================
    # Actions
    # =========================

    def inc(self):

        with self.lock:
            if self.locked:
                return
            self.current.increment()
            self.show()
            self.handle_completion()

    def dec(self):

        with self.lock:
            if self.locked:
                return
            self.current.decrement()
            self.show()

    def reset(self):

        with self.lock:
            if self.locked:
                return
            self.current.reset()
            self.show()

    # =========================
    # Hotkeys
    # =========================

    def _register_hotkeys(self):

        keyboard.add_hotkey("up", self.inc)
        keyboard.add_hotkey("down", self.dec)
        keyboard.add_hotkey("left", self.reset)
        keyboard.add_hotkey("right", self.reset)

    # =========================
    # Run
    # =========================

    def run(self):

        print("Objective Tracker Started\n")

        self.print_bindings()

        self.create_objective()

        while True:
            time.sleep(0.1)
            pass


# =========================
# Entry
# =========================

if __name__ == "__main__":
    Tracker().run()