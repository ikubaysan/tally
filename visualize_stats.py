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
# Overall Success Plot
# =========================

class OverallSuccessPlot(BasePlot):

    def update(self, ax, data):

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

        ax.clear()

        ax.bar(names, rates)

        ax.set_title("Success Rate per Objective")
        ax.set_ylabel("Success %")
        ax.set_ylim(0, 100)

        ax.tick_params(axis='x', rotation=45)


# =========================
# Session Progress Plot
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

            ax.plot(
                x,
                rates,
                marker="o",
                label=name
            )

        ax.set_title("Success Rate by Session")
        ax.set_xlabel("Session")
        ax.set_ylabel("Success %")

        ax.xaxis.set_major_locator(
            MaxNLocator(integer=True)
        )

        ax.set_ylim(0, 100)

        ax.legend()


# =========================
# Rolling Success Plot (NEW)
# =========================

class RollingSuccessPlot(BasePlot):

    def __init__(self, window_size):
        self.window_size = window_size

    def update(self, ax, data):

        ax.clear()

        for name, sessions in data.items():

            all_results = []

            for sid in sorted(sessions.keys()):
                all_results.extend(
                    sessions[sid]
                )

            if len(all_results) < self.window_size:
                continue

            rolling_rates = []

            window = deque(
                maxlen=self.window_size
            )

            for r in all_results:

                window.append(r)

                if len(window) == self.window_size:

                    rate = (
                        sum(window)
                        / self.window_size
                    ) * 100

                    rolling_rates.append(rate)

            x = list(
                range(
                    self.window_size,
                    self.window_size
                    + len(rolling_rates)
                )
            )

            ax.plot(
                x,
                rolling_rates,
                label=name
            )

        ax.set_title(
            f"Rolling Success Rate "
            f"(MA of latest {self.window_size} attempts)"
        )

        ax.set_xlabel("Attempt")
        ax.set_ylabel("Success %")

        ax.set_ylim(0, 100)

        ax.legend()


# =========================
# Plot Manager
# =========================

class PlotManager:

    def __init__(self):

        self.fig = plt.figure()

        self.plots = [

            OverallSuccessPlot(),

            SessionProgressPlot(),

            RollingSuccessPlot(
                ROLLING_WINDOW
            )

        ]

    def _build_axes(self):

        count = len(self.plots)

        cols = math.ceil(
            math.sqrt(count)
        )

        rows = math.ceil(
            count / cols
        )

        axes = []

        for i in range(count):

            ax = self.fig.add_subplot(
                rows,
                cols,
                i + 1
            )

            axes.append(ax)

        return axes

    def update(self, data):

        self.fig.clear()

        axes = self._build_axes()

        for ax, plot in zip(
            axes,
            self.plots
        ):

            plot.update(ax, data)

        self.fig.tight_layout()

        self.fig.canvas.draw_idle()


# =========================
# Visualization App
# =========================

class VisualizationApp:

    def __init__(self):

        self.loader = DatabaseLoader(
            DB_FILE
        )

        self.plot_manager = PlotManager()

        self.last_mtime = None

    def check_for_updates(self, event=None):

        try:

            current_mtime = os.path.getmtime(
                DB_FILE
            )

            now = datetime.now().strftime(
                "%H:%M:%S"
            )

            print(
                f"[{now}] Checking DB file..."
            )

            if self.last_mtime is None:

                self.last_mtime = current_mtime
                self.update_plots()
                return

            if current_mtime != self.last_mtime:

                print(
                    f"[{now}] Change detected."
                )

                self.last_mtime = current_mtime

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

        now = datetime.now().strftime(
            "%H:%M:%S"
        )

        print(
            f"[{now}] Charts updated."
        )

    def run(self):

        print("Visualization started.")
        print(
            f"Checking every "
            f"{CHECK_INTERVAL_SECONDS} seconds.\n"
        )

        self.check_for_updates()

        timer = self.plot_manager.fig.canvas.new_timer(
            interval=CHECK_INTERVAL_SECONDS * 1000
        )

        timer.add_callback(
            self.check_for_updates
        )

        timer.start()

        plt.show()


# =========================

if __name__ == "__main__":

    app = VisualizationApp()
    app.run()