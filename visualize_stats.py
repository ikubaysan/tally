import sqlite3
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from collections import defaultdict


DB_FILE = "tally.db"


# =========================
# Load Data
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
    JOIN sessions s ON a.session_id = s.id
    JOIN objectives o ON a.objective_id = o.id
    ORDER BY o.name, s.id
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


# =========================
# Structure
# =========================

def process_data(rows):

    data = defaultdict(lambda: defaultdict(list))

    for name, sid, result in rows:
        data[name][sid].append(result)

    return data


# =========================
# Overall
# =========================

def compute_overall_rates(data):

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

    return names, rates


# =========================
# Session trend
# =========================

def compute_session_rates(data):

    out = {}

    for name, sessions in data.items():

        rates = []

        for sid in sorted(sessions.keys()):

            results = sessions[sid]

            if not results:
                continue

            rates.append((sum(results) / len(results)) * 100)

        if rates:
            out[name] = rates

    return out


# =========================
# Plot
# =========================

def plot_overall(names, rates):

    plt.figure()

    plt.bar(names, rates)

    plt.title("Success Rate per Objective")
    plt.ylabel("Success %")

    plt.xticks(rotation=45)
    plt.ylim(0, 100)

    plt.tight_layout()
    plt.show()


def plot_progress(data):

    plt.figure()
    ax = plt.gca()

    for name, rates in data.items():

        x = list(range(1, len(rates) + 1))

        plt.plot(x, rates, marker="o", label=name)

    plt.title("Success Rate by Session")
    plt.xlabel("Session")
    plt.ylabel("Success %")

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.ylim(0, 100)
    plt.legend()

    plt.tight_layout()
    plt.show()


# =========================
# Main
# =========================

def main():

    rows = load_data()

    if not rows:
        print("No data")
        return

    data = process_data(rows)

    names, rates = compute_overall_rates(data)
    sessions = compute_session_rates(data)

    plot_overall(names, rates)
    plot_progress(sessions)


if __name__ == "__main__":
    main()