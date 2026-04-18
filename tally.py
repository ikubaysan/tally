import keyboard
import threading
from datetime import datetime


class GlobalCounter:
    """
    Global counter with configurable hotkeys and timestamp tracking.
    """

    def __init__(self, key_bindings=None, target_count=None):
        # Default key bindings
        self.key_bindings = key_bindings or {
            "increment": ["up"],
            "decrement": ["down"],
            "reset": ["left", "right"],
            "exit": ["esc"],
        }

        self.target_count = target_count

        self.count = 0
        self.last_action_time = None
        self.lock = threading.Lock()

    # =========================
    # Utility Methods
    # =========================

    def _get_time_str(self):
        return datetime.now().strftime("%H:%M:%S")

    def _update_time(self):
        self.last_action_time = self._get_time_str()

    def _print_status(self, action=""):
        if self.last_action_time:
            time_part = f" | Last action: {self.last_action_time}"
        else:
            time_part = ""

        if action:
            print(
                f"\r{action} | Count: {self.count}{time_part}        ",
                end="",
                flush=True,
            )
        else:
            print(
                f"\rCount: {self.count}{time_part}        ",
                end="",
                flush=True,
            )

        if (
            self.target_count is not None
            and self.count == self.target_count
        ):
            print(f"\n🎉 Target reached: {self.target_count}!")

    # =========================
    # Actions
    # =========================

    def increment(self):
        with self.lock:
            self.count += 1
            self._update_time()
            self._print_status("Increment")

    def decrement(self):
        with self.lock:
            self.count -= 1
            self._update_time()
            self._print_status("Decrement")

    def reset(self):
        with self.lock:
            self.count = 0
            self._update_time()
            self._print_status("Reset")

    # =========================
    # Hotkey Handling
    # =========================

    def register_hotkeys(self):
        for key in self.key_bindings["increment"]:
            keyboard.add_hotkey(key, self.increment)

        for key in self.key_bindings["decrement"]:
            keyboard.add_hotkey(key, self.decrement)

        for key in self.key_bindings["reset"]:
            keyboard.add_hotkey(key, self.reset)

    def wait_for_exit(self):
        exit_keys = self.key_bindings["exit"]
        keyboard.wait(exit_keys[0])

    # =========================
    # Run
    # =========================

    def run(self):
        print("Global Counter Started\n")

        print("Key Bindings:")
        for action, keys in self.key_bindings.items():
            print(f"  {action.capitalize():10} -> {', '.join(keys)}")

        print()

        self._print_status()

        self.register_hotkeys()
        self.wait_for_exit()

        print("\nExiting...")


# =========================
# MAIN ENTRY POINT
# =========================

if __name__ == "__main__":

    KEY_BINDINGS = {
        "increment": ["up"],
        "decrement": ["down"],
        "reset": ["left", "right"],
        "exit": ["esc"],
    }

    TARGET_COUNT = None  # Example: 10

    counter = GlobalCounter(
        key_bindings=KEY_BINDINGS,
        target_count=TARGET_COUNT,
    )

    counter.run()