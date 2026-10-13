import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

baseline = [8.90, 8.86, 9.51]
load_aware = [18.9, 18.2, 18.1]
avg = [sum(baseline) / 3, sum(load_aware) / 3]

fig, ax = plt.subplots(figsize=(6, 4.2))
x = [0, 1]
ax.bar(x, avg, color=["#9aa0a6", "#2a7de1"], width=0.45)

# individual runs, spread sideways so they don't overlap
for i, runs in enumerate([baseline, load_aware]):
    for j, v in enumerate(runs):
        ax.scatter(i + (j - 1) * 0.08, v, color="white", edgecolor="black", s=40, zorder=3)

# average labels above everything
for i, a in enumerate(avg):
    top = max([baseline, load_aware][i])
    ax.text(i, top + 0.9, f"avg {a:.1f}", ha="center", fontsize=12, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(["Baseline (shortest path)", "Load-aware routing"], fontsize=11)
ax.set_ylabel("Total throughput (Mbits/s)")
ax.set_title("Two flows, two 10 Mbps paths\nbars = average, dots = individual runs", fontsize=11)
ax.set_ylim(0, 23)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
plt.tight_layout()
plt.savefig("results/throughput.png", dpi=150)
print("saved")
