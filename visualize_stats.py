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




class RunSuccessProbabilityTimelinePlot(BasePlot):
    """
    RUN SUCCESS PROBABILITY OVER TIME (DYNAMIC VIEW)

    PURPOSE
    -------
    This plot shows how the estimated probability of completing
    a full run changes over time based on recent performance.

    It is NOT a single static value — it is a time series.

    HOW IT WORKS
    -------------
    - Each objective has a rolling success rate computed from
      the last N attempts (ROLLING_WINDOW).

    - At each time step t:
        P(run success at time t) =
            P(obj1 at t) *
            P(obj2 at t) *
            P(obj3 at t) * ...

    - This produces a continuously changing estimate of how
      "viable" a full run is over time.

    INTERPRETATION
    --------------
    This plot answers:

        "If my current consistency per objective stayed the same,
         how likely would I be to complete a full run?"

    SPEEDRUN USE CASE
    -----------------
    Useful for tracking:
    - Improvement over time
    - Degradation of consistency
    - Overall run viability trend

    LIMITATIONS
    -----------
    - Assumes independence between objectives
    - Uses aligned rolling windows (not true session coupling)
    - Does not represent actual full-run outcomes
    """

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        objective_names = sorted(data.keys())

        history = defaultdict(list)
        max_steps = 0

        # Build rolling success history per objective
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
                    rate = sum(window) / self.window
                else:
                    rate = sum(window) / len(window) if window else 0

                rolling.append(rate)

            history[name] = rolling
            max_steps = max(max_steps, len(rolling))

        # Compute cumulative probability over time
        x_vals = []
        y_vals = []

        for t in range(max_steps):

            prob = 1.0

            for name in objective_names:

                series = history[name]
                if not series:
                    continue

                idx = min(t, len(series) - 1)
                prob *= series[idx]

            x_vals.append(t)
            y_vals.append(prob * 100)

        ax.plot(x_vals, y_vals)

        ax.set_title(
            f"Run Success Probability Timeline\n"
            f"(Rolling Window = {self.window})"
        )

        ax.set_xlabel("Time Step (Aligned Rolling Index)")
        ax.set_ylabel("Estimated Full Run Success %")
        ax.set_ylim(0, 100)


class CurrentRunSurvivalByObjectivePlot(BasePlot):
    """
    CURRENT RUN SURVIVAL BY OBJECTIVE (SNAPSHOT VIEW)

    PURPOSE
    -------
    This plot shows how a full run survives as it progresses
    through each objective, using ONLY the most recent
    performance snapshot per objective.

    It produces exactly one value per objective.

    HOW IT WORKS
    -------------
    - Each objective's success rate is computed using the
      last N attempts (ROLLING_WINDOW).

    - These are treated as the "current skill level" per objective.

    - The run probability is then computed sequentially:

        P1 = Obj1
        P2 = P1 * Obj2
        P3 = P2 * Obj3
        ...

    - This produces a downward curve representing how a run
      survives step-by-step.

    INTERPRETATION
    --------------
    This plot answers:

        "If I attempted a run right now, where would it fail?"

    It shows:
    - Which objectives reduce run viability the most
    - How quickly a run collapses under current conditions

    SPEEDRUN USE CASE
    -----------------
    Useful for:
    - Identifying run-killing objectives
    - Prioritizing practice targets
    - Understanding current bottlenecks

    IMPORTANT CHARACTERISTIC
    -----------------------
    Unlike the timeline plot, this is:
    - NOT time-based
    - NOT historical
    - A single snapshot of current run performance

    LIMITATIONS
    -----------
    - Assumes objective independence
    - Uses rolling averages as proxy for skill
    - Does not simulate real run sessions
    """

    def __init__(self, window):
        self.window = window

    def update(self, ax, data):

        ax.clear()

        objective_names = sorted(data.keys())

        per_objective_prob = []

        # Compute latest performance per objective
        for name in objective_names:

            sessions = data[name]

            all_results = []
            for sid in sorted(sessions.keys()):
                all_results.extend(sessions[sid])

            if not all_results:
                continue

            recent = all_results[-self.window:]

            if not recent:
                continue

            per_objective_prob.append(sum(recent) / len(recent))

        # Compute cumulative survival chain
        cumulative = []
        prob = 1.0

        for p in per_objective_prob:
            prob *= p
            cumulative.append(prob * 100)

        x_vals = list(range(1, len(cumulative) + 1))

        ax.plot(x_vals, cumulative, marker="o")

        ax.set_xticks(x_vals)
        ax.set_xticklabels(objective_names, rotation=45, ha="right")

        ax.set_title(
            f"Current Run Survival by Objective\n"
            f"(Rolling Window = {self.window})"
        )

        ax.set_xlabel("Objective Order")
        ax.set_ylabel("Run Survival Probability %")
        ax.set_ylim(0, 100)



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