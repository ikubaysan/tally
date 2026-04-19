import sqlite3
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from collections import defaultdict


DB_FILE = "tally.db"


# =========================
# Load Data (SQL)
# =========================

def load_data():

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
    SELECT
        o.name,
        s.id,
        a.result
    FROM attempts a
    JOIN sessions s
        ON a.session_id = s.id
    JOIN objectives o
        ON a.objective_id = o.id
    WHERE LOWER(o.name) != 'default'
    ORDER BY o.name, s.id
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


# =========================
# Structure Data
# =========================

def process_data(rows):

    data = defaultdict(lambda: defaultdict(list))

    for obj_name, session_id, result in rows:
        data[obj_name][session_id].append(result)

    return data


# =========================
# Overall Success Rate
# =========================

def compute_overall_rates(data):

    names = []
    rates = []

    for obj_name, sessions in data.items():

        success = 0
        total = 0

        for results in sessions.values():
            success += results.count("success")
            total += len(results)

        if total == 0:
            continue

        names.append(obj_name)
        rates.append((success / total) * 100)

    return names, rates


# =========================
# Session Progress
# =========================

def compute_session_rates(data):

    output = {}

    for obj_name, sessions in data.items():

        session_ids = sorted(sessions.keys())

        rates = []

        for sid in session_ids:

            results = sessions[sid]

            total = len(results)
            if total == 0:
                continue

            success = results.count("success")

            rates.append((success / total) * 100)

        if rates:
            output[obj_name] = rates

    return output


# =========================
# Plot 1: Overall
# =========================

def plot_overall(names, rates):

    if not names:
        print("No data available.")
        return

    plt.figure()

    plt.bar(names, rates)

    plt.title("Success Rate per Objective")

    plt.ylabel("Success Rate (%)")

    plt.xticks(rotation=45)

    plt.ylim(0, 100)

    plt.tight_layout()

    plt.show()


# =========================
# Plot 2: Session Progress
# =========================

def plot_progress(session_progress):

    if not session_progress:
        print("No session data available.")
        return

    plt.figure()

    ax = plt.gca()

    for obj_name, rates in session_progress.items():

        x = list(range(1, len(rates) + 1))

        plt.plot(x, rates, marker="o", label=obj_name)

    plt.title("Success Rate by Session")

    plt.xlabel("Session Number")

    plt.ylabel("Success Rate (%)")

    plt.ylim(0, 100)

    plt.legend()

    # Force integer ticks (FIX)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()

    plt.show()


# =========================
# Main
# =========================

def main():

    rows = load_data()

    if not rows:
        print("No data found.")
        return

    data = process_data(rows)

    names, rates = compute_overall_rates(data)

    session_progress = compute_session_rates(data)

    plot_overall(names, rates)

    plot_progress(session_progress)


if __name__ == "__main__":
    main()