import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

baseline = [8.90, 8.86, 9.51]
load_aware = [18.9, 18.2, 18.1]

avg_b = sum(baseline) / len(baseline)
avg_l = sum(load_aware) / len(load_aware)

fig, ax = plt.subplots(figsize=(6, 4))
bars = ax.bar(["Baseline\n(shortest path)", "Load-aware\nrouting"],
              [avg_b, avg_l], color=["#999999", "#2a7de1"], width=0.5)

# individual runs as dots
ax.scatter([0] * 3, baseline, color="black", zorder=3, label="Individual runs")
ax.scatter([1] * 3, load_aware, color="black", zorder=3)

for bar, v in zip(bars, [avg_b, avg_l]):
    ax.text(bar.get_x() + bar.get_width() / 2, v + 0.4, f"{v:.1f}",
            ha="center", fontweight="bold")

ax.set_ylabel("Total throughput (Mbits/s)")
ax.set_title("Two flows, two 10 Mbps paths (3 runs each)")
ax.set_ylim(0, 24)
ax.legend()
plt.tight_layout()
plt.savefig("results/throughput.png", dpi=150)
print("saved")
