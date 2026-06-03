from pathlib import Path
import csv
import math
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path("/mnt/e/pilot exp")

BASE = ROOT / "dual_view_test_10min/mvp3d_9_10min/mvp3d_best30_9_00_9_30/manual_direct_edit/final_state_machine_corrected"

CSV_IN = BASE / "trajectory_3d_state_machine_interpolated_smoothed.csv"

OUT_SUMMARY = BASE / "final_manual_v1_qc_summary.txt"
OUT_SPEED = BASE / "final_manual_v1_speed.csv"
OUT_DISTANCE = BASE / "final_manual_v1_inter_fish_distance.csv"

FIG_SPEED = BASE / "final_manual_v1_speed_time.png"
FIG_DISTANCE = BASE / "final_manual_v1_inter_fish_distance_time.png"

FPS = 30
FISH_IDS = ["fish_1", "fish_2", "fish_3"]

data = {fid: [] for fid in FISH_IDS}

with CSV_IN.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        fid = r["fish_id"]
        data[fid].append({
            "sample_idx": int(float(r["sample_idx"])),
            "time_sec": float(r["time_sec"]),
            "X": float(r["X"]),
            "Y": float(r["Y"]),
            "Z": float(r["Z"]),
            "interpolated": int(float(r.get("interpolated", 0))),
        })

summary = []
summary.append("Final manual v1 trajectory QC")
summary.append("=" * 80)
summary.append(f"source: {CSV_IN}")
summary.append("")

all_x, all_y, all_z = [], [], []

for fid in FISH_IDS:
    rows = data[fid]
    X = np.array([r["X"] for r in rows])
    Y = np.array([r["Y"] for r in rows])
    Z = np.array([r["Z"] for r in rows])
    interp_n = sum(r["interpolated"] for r in rows)

    all_x.extend(X)
    all_y.extend(Y)
    all_z.extend(Z)

    summary.append(fid)
    summary.append(f"  points: {len(rows)}")
    summary.append(f"  interpolated points: {interp_n}")
    summary.append(f"  interpolated ratio: {interp_n / len(rows) * 100:.2f}%")
    summary.append(f"  X range: {X.min():.4f} to {X.max():.4f}")
    summary.append(f"  Y range: {Y.min():.4f} to {Y.max():.4f}")
    summary.append(f"  Z range: {Z.min():.4f} to {Z.max():.4f}")
    summary.append("")

summary.append("All fish combined")
summary.append(f"  X range: {min(all_x):.4f} to {max(all_x):.4f}")
summary.append(f"  Y range: {min(all_y):.4f} to {max(all_y):.4f}")
summary.append(f"  Z range: {min(all_z):.4f} to {max(all_z):.4f}")
summary.append("")

# speed
speed_rows = []
for fid in FISH_IDS:
    rows = data[fid]
    for a, b in zip(rows[:-1], rows[1:]):
        dt = b["time_sec"] - a["time_sec"]
        dx = b["X"] - a["X"]
        dy = b["Y"] - a["Y"]
        dz = b["Z"] - a["Z"]
        speed = math.sqrt(dx * dx + dy * dy + dz * dz) / dt
        speed_rows.append({
            "sample_idx": b["sample_idx"],
            "time_sec": b["time_sec"],
            "fish_id": fid,
            "speed_relative_unit_per_sec": speed,
            "from_interpolated": a["interpolated"],
            "to_interpolated": b["interpolated"],
        })

with OUT_SPEED.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(speed_rows[0].keys()))
    writer.writeheader()
    writer.writerows(speed_rows)

for fid in FISH_IDS:
    speeds = np.array([r["speed_relative_unit_per_sec"] for r in speed_rows if r["fish_id"] == fid])
    summary.append(f"{fid} speed")
    summary.append(f"  mean: {speeds.mean():.4f}")
    summary.append(f"  median: {np.median(speeds):.4f}")
    summary.append(f"  p95: {np.percentile(speeds, 95):.4f}")
    summary.append(f"  max: {speeds.max():.4f}")
    summary.append("")

# inter-fish distance
distance_rows = []
n = len(data["fish_1"])

for idx in range(n):
    sample_idx = data["fish_1"][idx]["sample_idx"]
    time_sec = data["fish_1"][idx]["time_sec"]

    coords = {}
    for fid in FISH_IDS:
        r = data[fid][idx]
        coords[fid] = np.array([r["X"], r["Y"], r["Z"]], dtype=float)

    d12 = float(np.linalg.norm(coords["fish_1"] - coords["fish_2"]))
    d13 = float(np.linalg.norm(coords["fish_1"] - coords["fish_3"]))
    d23 = float(np.linalg.norm(coords["fish_2"] - coords["fish_3"]))

    distance_rows.append({
        "sample_idx": sample_idx,
        "time_sec": time_sec,
        "d_fish_1_fish_2": d12,
        "d_fish_1_fish_3": d13,
        "d_fish_2_fish_3": d23,
        "mean_inter_fish_distance": float(np.mean([d12, d13, d23])),
        "min_inter_fish_distance": float(np.min([d12, d13, d23])),
    })

with OUT_DISTANCE.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(distance_rows[0].keys()))
    writer.writeheader()
    writer.writerows(distance_rows)

mean_dist = np.array([r["mean_inter_fish_distance"] for r in distance_rows])
min_dist = np.array([r["min_inter_fish_distance"] for r in distance_rows])

summary.append("Inter-fish distance")
summary.append(f"  mean distance mean: {mean_dist.mean():.4f}")
summary.append(f"  mean distance median: {np.median(mean_dist):.4f}")
summary.append(f"  min distance mean: {min_dist.mean():.4f}")
summary.append(f"  min distance min: {min_dist.min():.4f}")
summary.append("")

OUT_SUMMARY.write_text("\n".join(summary), encoding="utf-8")

# plots
plt.figure(figsize=(9, 5))
for fid in FISH_IDS:
    rows = [r for r in speed_rows if r["fish_id"] == fid]
    plt.plot(
        [r["time_sec"] for r in rows],
        [r["speed_relative_unit_per_sec"] for r in rows],
        label=fid
    )
plt.xlabel("Time (s)")
plt.ylabel("Speed (relative unit/s)")
plt.title("Final manual v1 speed over time")
plt.legend()
plt.tight_layout()
plt.savefig(FIG_SPEED, dpi=300)
plt.close()

plt.figure(figsize=(9, 5))
T = [r["time_sec"] for r in distance_rows]
for col in ["d_fish_1_fish_2", "d_fish_1_fish_3", "d_fish_2_fish_3"]:
    plt.plot(T, [r[col] for r in distance_rows], label=col)
plt.xlabel("Time (s)")
plt.ylabel("Distance (relative unit)")
plt.title("Final manual v1 inter-fish distance over time")
plt.legend()
plt.tight_layout()
plt.savefig(FIG_DISTANCE, dpi=300)
plt.close()

print("\n".join(summary))
print("Saved:")
print(OUT_SUMMARY)
print(OUT_SPEED)
print(OUT_DISTANCE)
print(FIG_SPEED)
print(FIG_DISTANCE)
