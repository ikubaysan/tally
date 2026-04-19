import time
import win32gui
import win32con
import pyautogui


import time
import win32gui
import win32con
import pyautogui


class WindowController:
    def __init__(self, title_keywords, hotkey=("ctrl", "r")):
        self.title_keywords = title_keywords
        self.hotkey = hotkey

        self.hwnd = None
        self.title = None

    # -------------------------
    # Window search
    # -------------------------
    def _get_windows(self):
        windows = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append((hwnd, title))

        win32gui.EnumWindows(callback, None)
        return windows

    def find_window(self):
        for hwnd, title in self._get_windows():
            if all(k in title for k in self.title_keywords):
                self.hwnd = hwnd
                self.title = title
                return True
        return False

    # -------------------------
    # Focus
    # -------------------------
    def focus(self):
        if not self.hwnd:
            return False

        win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)

        try:
            win32gui.SetForegroundWindow(self.hwnd)
        except Exception:
            pass

        time.sleep(0.15)
        return True

    # -------------------------
    # Action
    # -------------------------
    def send_hotkey(self):
        if not self.hwnd and not self.find_window():
            print("[WindowController] No matching window found.")
            return False

        if not self.focus():
            print("[WindowController] Failed to focus window.")
            return False

        print(f"[WindowController] Sending hotkey {self.hotkey} to: {self.title}")
        pyautogui.hotkey(*self.hotkey)
        return True

# -------------------------
# Example usage
# -------------------------
if __name__ == "__main__":

    # Example target window (adjust to your app/game)
    controller = WindowController(
        title_keywords=["NPUB30769"],
        hotkey=("ctrl", "r")
    )

    print("Searching for window...")

    if not controller.find_window():
        print("No matching window found.")
        exit()

    print(f"Found: {controller.title}")

    success = controller.send_hotkey()

    if success:
        print("Hotkey successfully sent.")
    else:
        print("Failed to send hotkey.")