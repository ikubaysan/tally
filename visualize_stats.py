import sqlite3
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from collections import defaultdict, deque
from datetime import datetime
import os
import math



# =========================
# Config
# =========================

DB_FILE = "tally.db"
CHECK_INTERVAL_SECONDS = 10
ROLLING_WINDOW = 20
#plt.style.use("dark_background")

# =========================
# Data Loader
# =========================

class DatabaseLoader:

    def __init__(self, db_file):
        self.db_file = db_file

    def load_rows(self):

        conn = sqlite3.connect(self.db_file)
        cur = conn.cursor()

        cur.execute("""
        SELECT
            o.name,
            s.id,
            a.result
        FROM attempts a
        JOIN sessions s ON a.session_id = s.id
        JOIN objectives o ON a.objective_id = o.id
        ORDER BY o.name, s.id
        """)

        rows = cur.fetchall()
        conn.close()

        return rows

    def process_data(self, rows):

        data = defaultdict(lambda: defaultdict(list))

        for name, sid, result in rows:
            data[name][sid].append(result)

        return data


# =========================
# Base Plot
# =========================

class BasePlot:

    def update(self, ax, data):
        raise NotImplementedError


# =========================
# Overall Success (ALL TIME)
# =========================

class OverallSuccessPlot(BasePlot):

    def update(self, ax, data):

        ax.clear()

        names = []
        rates = []

        for name, sessions in data.items():

            total = 0
            success = 0

            for results in sessions.values():
                success += sum(results)
                total += len(results)

            if total == 0:
                continue

            names.append(name)
            rates.append((success / total) * 100)

        ax.bar(names, rates)

        ax.set_title("Overall Success Rate per Objective")
        ax.set_ylabel("Success %")
        ax.set_ylim(0, 100)

        ax.tick_params(axis='x', rotation=45)


# =========================
# Recent Success (NEW)
# =========================

class RecentSuccessPlot(BasePlot):

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        names = []
        rates = []

        for name, sessions in data.items():

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            if not all_results:
                continue

            recent = all_results[-self.window:]

            if not recent:
                continue

            rate = (sum(recent) / len(recent)) * 100

            names.append(name)
            rates.append(rate)

        ax.bar(names, rates)

        ax.set_title(
            f"Recent Success Rate "
            f"(last {self.window} attempts)"
        )

        ax.set_ylabel("Success %")
        ax.set_ylim(0, 100)

        ax.tick_params(axis='x', rotation=45)


# =========================
# Session Progress
# =========================

class SessionProgressPlot(BasePlot):

    def update(self, ax, data):

        ax.clear()

        for name, sessions in data.items():

            rates = []

            for sid in sorted(sessions.keys()):

                results = sessions[sid]

                if not results:
                    continue

                rates.append(
                    (sum(results) / len(results)) * 100
                )

            if not rates:
                continue

            x = list(range(1, len(rates) + 1))

            ax.plot(x, rates, marker="o", label=name)

        ax.set_title("Success Rate by Session")
        ax.set_xlabel("Session")
        ax.set_ylabel("Success %")

        ax.xaxis.set_major_locator(
            MaxNLocator(integer=True)
        )

        ax.set_ylim(0, 100)

        ax.legend()


# =========================
# Rolling Success
# =========================

class RollingSuccessPlot(BasePlot):

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        for name, sessions in data.items():

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            if len(all_results) < self.window:
                continue

            window = deque(maxlen=self.window)
            rolling = []

            for r in all_results:
                window.append(r)

                if len(window) == self.window:
                    rolling.append(
                        sum(window) / self.window * 100
                    )

            x = range(
                self.window,
                self.window + len(rolling)
            )

            ax.plot(x, rolling, label=name)

        ax.set_title(
            f"Rolling Success Rate (MA {self.window})"
        )

        ax.set_xlabel("Attempt")
        ax.set_ylabel("Success %")

        ax.set_ylim(0, 100)

        ax.legend()



# ============================================================
# CUMULATIVE SUCCESS PROBABILITY ACROSS OBJECTIVES
# ------------------------------------------------------------
#
# Purpose:
# --------
# This visualization estimates the probability of completing
# ALL objectives perfectly in sequence (no failures allowed),
# based on recent performance.
#
# It answers the question:
#
#   "Based on my recent attempts, what is the chance that I
#    would succeed at every objective once, with zero mistakes?"
#
#
# Core Concept:
# -------------
# Each objective has a rolling success rate calculated from
# its most recent N attempts (currently N = 20).
#
# Example:
#
#   Objective A (last 20 attempts):
#       18 successes, 2 failures → 90% success rate
#
#   Objective B (last 20 attempts):
#       15 successes, 5 failures → 75% success rate
#
#   Objective C (last 20 attempts):
#       10 successes, 10 failures → 50% success rate
#
# These per-objective probabilities are multiplied together
# to produce the cumulative probability of a perfect run:
#
#   P(total) = P(A) × P(B) × P(C)
#
# Example:
#
#   P(total) = 0.90 × 0.75 × 0.50
#            = 0.3375
#            = 33.75%
#
#
# Rolling Window Behavior:
# ------------------------
# Only the most recent N attempts (currently 20) are used
# for each objective.
#
# As new attempts occur:
#
#   - New attempts are added
#   - Old attempts fall out of the window
#   - Success rates update dynamically
#   - The cumulative probability updates accordingly
#
# This ensures the visualization reflects CURRENT performance,
# not historical lifetime averages.
#
#
# Objective Ordering:
# -------------------
# Objectives are processed in alphabetical order.
#
# This defines the assumed order of execution when computing
# the cumulative probability.
#
# For example:
#
#   A → B → C → D
#
# The cumulative probability decreases step-by-step as each
# objective is added to the sequence.
#
#
# Important Interpretation:
# -------------------------
# This represents the probability of a PERFECT RUN,
# meaning:
#
#   - Each objective is attempted exactly once
#   - No retries are allowed
#   - Any failure ends the run
#
# It does NOT represent:
#
#   - The probability of eventual success with retries
#   - The probability of finishing after multiple failures
#
#
# Mathematical Assumption:
# ------------------------
# This model assumes independence between objectives,
# meaning the probability of success at one objective
# does not directly affect another.
#
# While not perfectly true in practice, this provides a
# useful and intuitive estimate of full-run reliability.
#
#
# Why This Is Useful:
# -------------------
# The cumulative probability drops as more objectives
# are included, highlighting weak points in the sequence.
#
# If one objective has a low success rate, it will cause
# a sharp drop in the cumulative probability, making it
# easy to identify where improvement is needed.
#
#
# Summary:
# --------
# This visualization shows:
#
#   "Based on my last 20 attempts per objective,
#    what is the chance I would clear ALL objectives
#    perfectly in one uninterrupted run?"
#
# ============================================================
class CumulativeSuccessProbabilityPlot(BasePlot):

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        # alphabetical order (IMPORTANT requirement)
        objective_names = sorted(data.keys())

        print("\n=== Objective Execution Order (Alphabetical) ===")
        for i, name in enumerate(objective_names, 1):
            print(f"{i}. {name}")
        print("================================================\n")

        # build per-objective rolling windows over time
        history = defaultdict(list)

        max_steps = 0

        for name in objective_names:

            sessions = data[name]

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            window = deque(maxlen=self.window)
            rolling = []

            for r in all_results:
                window.append(r)

                if len(window) == self.window:
                    rolling_rate = sum(window) / self.window
                else:
                    rolling_rate = sum(window) / len(window) if window else 0

                rolling.append(rolling_rate)

            history[name] = rolling
            max_steps = max(max_steps, len(rolling))

        # compute compounded probability over time
        x_vals = []
        y_vals = []

        for t in range(max_steps):

            prob = 1.0

            for name in objective_names:

                series = history[name]

                if not series:
                    continue

                # clamp to last known value
                idx = min(t, len(series) - 1)

                prob *= series[idx]

            x_vals.append(t)
            y_vals.append(prob * 100)

        ax.plot(x_vals, y_vals)

        ax.set_title(
            f"Cumulative Success Probability Across Objectives\n"
            f"(Alphabetical Order, Rolling Window = {self.window})"
        )

        ax.set_xlabel("Attempt Step (Global)")
        ax.set_ylabel("Success Probability %")

        ax.set_ylim(0, 100)



# =========================
# Plot Manager
# =========================

class PlotManager:

    def __init__(self):

        self.fig = plt.figure()
        self.fig.canvas.manager.set_window_title("Tally Visualizations")

        self.plots = [
            RecentSuccessPlot(ROLLING_WINDOW),

            OverallSuccessPlot(),

            RollingSuccessPlot(ROLLING_WINDOW),

            SessionProgressPlot(),

            CumulativeSuccessProbabilityPlot(ROLLING_WINDOW),

        ]

    def _build_axes(self):

        count = len(self.plots)

        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)

        axes = []

        for i in range(count):
            axes.append(
                self.fig.add_subplot(rows, cols, i + 1)
            )

        return axes

    def update(self, data):

        self.fig.clear()

        axes = self._build_axes()

        for ax, plot in zip(axes, self.plots):
            plot.update(ax, data)

        self.fig.tight_layout()
        self.fig.canvas.draw_idle()


# =========================
# App
# =========================

class VisualizationApp:

    def __init__(self):

        self.loader = DatabaseLoader(DB_FILE)
        self.plot_manager = PlotManager()
        self.last_mtime = None

    def check_for_updates(self):

        try:

            mtime = os.path.getmtime(DB_FILE)

            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] Checking DB file...")

            if self.last_mtime is None:
                self.last_mtime = mtime
                self.update_plots()
                return

            if mtime != self.last_mtime:

                print(f"[{now}] Change detected.")
                self.last_mtime = mtime
                self.update_plots()

        except FileNotFoundError:
            print("Database file not found.")

    def update_plots(self):

        rows = self.loader.load_rows()

        if not rows:
            print("No data.")
            return

        data = self.loader.process_data(rows)

        self.plot_manager.update(data)

        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Charts updated.")

    def run(self):

        print("Visualization started.")
        print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds.\n")

        self.check_for_updates()

        timer = self.plot_manager.fig.canvas.new_timer(
            interval=CHECK_INTERVAL_SECONDS * 1000
        )

        timer.add_callback(self.check_for_updates)
        timer.start()

        plt.show()


# =========================

if __name__ == "__main__":
    VisualizationApp().run()