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

plt.style.use("Solarize_Light2")
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
        #ax.set_ylim(0, 100)

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
        #ax.set_ylim(0, 100)

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

        #ax.set_ylim(0, 100)

        if ax.get_legend_handles_labels()[0]:
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

        #ax.set_ylim(0, 100)

        if ax.get_legend_handles_labels()[0]:
            ax.legend()




class RunSuccessProbabilityTimelinePlot(BasePlot):

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        objective_names = sorted(data.keys())

        # =========================
        # Step 1 — Flatten attempts
        # =========================

        attempts_per_objective = {}

        for name in objective_names:

            sessions = data[name]

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            if all_results:
                attempts_per_objective[name] = all_results

        if not attempts_per_objective:
            return

        # =========================
        # Step 2 — Find minimum length
        # =========================

        min_len = min(
            len(v)
            for v in attempts_per_objective.values()
        )

        if min_len == 0:
            return

        # =========================
        # Step 3 — Trim to aligned length
        # =========================

        aligned = {}

        for name, attempts in attempts_per_objective.items():
            aligned[name] = attempts[-min_len:]

        # =========================
        # Step 4 — Compute rolling rates
        # =========================

        rolling_history = defaultdict(list)

        for name in objective_names:

            attempts = aligned[name]

            window = deque(maxlen=self.window)

            for r in attempts:

                window.append(r)

                rate = sum(window) / len(window)

                rolling_history[name].append(rate)

        # =========================
        # Step 5 — Compute run probability timeline
        # =========================

        x_vals = []
        y_vals = []

        for t in range(min_len):

            prob = 1.0

            for name in objective_names:

                prob *= rolling_history[name][t]

            x_vals.append(t + 1)
            y_vals.append(prob * 100)

        ax.plot(x_vals, y_vals)

        ax.set_title(
            f"Run Success Probability Timeline\n"
            f"(Aligned Length = {min_len}, "
            f"Rolling Window = {self.window})"
        )

        ax.set_xlabel(
            "Aligned Attempt Index "
            "(All Objectives)"
        )

        ax.set_ylabel(
            "Estimated Full Run Success %"
        )

        #ax.set_ylim(0, 100)




class CurrentRunSurvivalByObjectivePlot(BasePlot):

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        objective_names = sorted(data.keys())

        # =========================
        # Step 1 — Flatten attempts
        # =========================

        attempts_per_objective = {}

        for name in objective_names:

            sessions = data[name]

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            if all_results:
                attempts_per_objective[name] = all_results

        if not attempts_per_objective:
            return

        # =========================
        # Step 2 — Find minimum length
        # =========================

        min_len = min(
            len(v)
            for v in attempts_per_objective.values()
        )

        if min_len == 0:
            return

        # =========================
        # Step 3 — Trim to aligned length
        # =========================

        aligned = {}

        for name, attempts in attempts_per_objective.items():
            aligned[name] = attempts[-min_len:]

        # =========================
        # Step 4 — Compute per-objective
        # =========================

        per_objective_prob = []

        for name in objective_names:

            attempts = aligned[name]

            recent = attempts[-self.window:]

            prob = sum(recent) / len(recent)

            per_objective_prob.append(prob)

        # =========================
        # Step 5 — Cumulative survival
        # =========================

        cumulative = []

        prob = 1.0

        for p in per_objective_prob:

            prob *= p
            cumulative.append(prob * 100)

        x_vals = list(range(1, len(cumulative) + 1))

        ax.plot(x_vals, cumulative, marker="o")

        ax.set_xticks(x_vals)

        ax.set_xticklabels(
            objective_names,
            rotation=45,
            ha="right"
        )

        ax.set_title(
            f"Current Run Survival by Objective\n"
            f"(Aligned Length = {min_len}, "
            f"Rolling Window = {self.window})"
        )

        ax.set_xlabel("Objective")

        ax.set_ylabel(
            "Run Survival Probability %"
        )

        #ax.set_ylim(0, 100)


# =========================
# Plot Manager
# =========================

class PlotManager:

    def __init__(self):

        self.plots = [
            RecentSuccessPlot(ROLLING_WINDOW),
            OverallSuccessPlot(),
            RollingSuccessPlot(ROLLING_WINDOW),
            SessionProgressPlot(),
            RunSuccessProbabilityTimelinePlot(ROLLING_WINDOW),
            CurrentRunSurvivalByObjectivePlot(ROLLING_WINDOW),
        ]

        figsize = self._compute_figsize(len(self.plots))

        self.fig = plt.figure(figsize=figsize)
        self.fig.canvas.manager.set_window_title("Tally Visualizations")

    def _compute_figsize(self, n_plots):
        cols = math.ceil(math.sqrt(n_plots))
        rows = math.ceil(n_plots / cols)

        # size per subplot (tweakable)
        width_per_plot = 6
        height_per_plot = 4

        return (
            cols * width_per_plot,
            rows * height_per_plot
        )

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