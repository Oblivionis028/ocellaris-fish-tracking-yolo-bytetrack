from pathlib import Path
import csv
import math
import shutil
import numpy as np

ROOT = Path("/mnt/e/pilot exp")

BASE = ROOT / "dual_view_test_10min/mvp3d_9_10min/mvp3d_best30_9_00_9_30/manual_direct_edit/final_state_machine_corrected"

SRC = BASE / "trajectory_3d_state_machine_interpolated_smoothed.csv"

FINAL_COPY = BASE / "trajectory_3d_final_manual_v1.csv"
OUT_METRICS = BASE / "pilot_behavior_metrics_final_manual_v1.csv"
OUT_PER_FISH = BASE / "pilot_behavior_metrics_per_fish_final_manual_v1.csv"

FPS = 30
FISH_IDS = ["fish_1", "fish_2", "fish_3"]

# 复制封存版轨迹
if SRC.exists():
    shutil.copy2(SRC, FINAL_COPY)
else:
    raise FileNotFoundError(SRC)

data = {fid: [] for fid in FISH_IDS}

with SRC.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for r in reader:
        fid = r["fish_id"]
        if fid not in data:
            continue
        data[fid].append({
            "sample_idx": int(float(r["sample_idx"])),
            "time_sec": float(r["time_sec"]),
            "X": float(r["X"]),
            "Y": float(r["Y"]),
            "Z": float(r["Z"]),
            "interpolated": int(float(r.get("interpolated", 0))),
        })

# 基础检查
for fid in FISH_IDS:
    data[fid] = sorted(data[fid], key=lambda r: r["sample_idx"])
    if len(data[fid]) == 0:
        raise RuntimeError(f"{fid} has no data")

n_frames = len(data["fish_1"])
duration_sec = n_frames / FPS

# 每条鱼速度和空间指标
per_fish_rows = []
all_speeds = []
all_X, all_Y, all_Z = [], [], []

for fid in FISH_IDS:
    rows = data[fid]

    X = np.array([r["X"] for r in rows], dtype=float)
    Y = np.array([r["Y"] for r in rows], dtype=float)
    Z = np.array([r["Z"] for r in rows], dtype=float)
    interpolated = np.array([r["interpolated"] for r in rows], dtype=int)

    all_X.extend(X)
    all_Y.extend(Y)
    all_Z.extend(Z)

    speeds = []
    for a, b in zip(rows[:-1], rows[1:]):
        dt = b["time_sec"] - a["time_sec"]
        dx = b["X"] - a["X"]
        dy = b["Y"] - a["Y"]
        dz = b["Z"] - a["Z"]
        if dt > 0:
            speeds.append(math.sqrt(dx*dx + dy*dy + dz*dz) / dt)

    speeds = np.array(speeds, dtype=float)
    all_speeds.extend(speeds)

    per_fish_rows.append({
        "video_id": "mvp3d_best30_9_00_9_30",
        "trajectory_version": "final_manual_v1",
        "fish_id": fid,
        "n_points": len(rows),
        "interpolated_points": int(interpolated.sum()),
        "interpolated_ratio": float(interpolated.mean()),
        "mean_speed": float(speeds.mean()),
        "median_speed": float(np.median(speeds)),
        "p95_speed": float(np.percentile(speeds, 95)),
        "max_speed": float(speeds.max()),
        "mean_X": float(X.mean()),
        "mean_Y": float(Y.mean()),
        "mean_Z": float(Z.mean()),
        "X_min": float(X.min()),
        "X_max": float(X.max()),
        "Y_min": float(Y.min()),
        "Y_max": float(Y.max()),
        "Z_min": float(Z.min()),
        "Z_max": float(Z.max()),
        "X_range": float(X.max() - X.min()),
        "Y_range": float(Y.max() - Y.min()),
        "Z_range": float(Z.max() - Z.min()),
    })

# 群体距离、最近邻距离、群体离散度
mean_inter_fish_distances = []
min_inter_fish_distances = []
nearest_neighbor_distances = []
group_dispersions = []
centroid_X, centroid_Y, centroid_Z = [], [], []

for idx in range(n_frames):
    coords = []
    for fid in FISH_IDS:
        r = data[fid][idx]
        coords.append(np.array([r["X"], r["Y"], r["Z"]], dtype=float))

    coords = np.array(coords, dtype=float)
    centroid = coords.mean(axis=0)

    centroid_X.append(float(centroid[0]))
    centroid_Y.append(float(centroid[1]))
    centroid_Z.append(float(centroid[2]))

    pair_dists = []
    for i in range(len(FISH_IDS)):
        for j in range(i + 1, len(FISH_IDS)):
            pair_dists.append(float(np.linalg.norm(coords[i] - coords[j])))

    pair_dists = np.array(pair_dists, dtype=float)

    mean_inter_fish_distances.append(float(pair_dists.mean()))
    min_inter_fish_distances.append(float(pair_dists.min()))

    # 每条鱼到最近个体的距离，再取平均
    nn = []
    for i in range(len(FISH_IDS)):
        d_to_others = []
        for j in range(len(FISH_IDS)):
            if i == j:
                continue
            d_to_others.append(float(np.linalg.norm(coords[i] - coords[j])))
        nn.append(min(d_to_others))
    nearest_neighbor_distances.append(float(np.mean(nn)))

    # 群体离散度：三条鱼到群体中心的平均距离
    dist_to_centroid = np.linalg.norm(coords - centroid, axis=1)
    group_dispersions.append(float(dist_to_centroid.mean()))

all_speeds = np.array(all_speeds, dtype=float)
all_X = np.array(all_X, dtype=float)
all_Y = np.array(all_Y, dtype=float)
all_Z = np.array(all_Z, dtype=float)

mean_inter_fish_distances = np.array(mean_inter_fish_distances, dtype=float)
min_inter_fish_distances = np.array(min_inter_fish_distances, dtype=float)
nearest_neighbor_distances = np.array(nearest_neighbor_distances, dtype=float)
group_dispersions = np.array(group_dispersions, dtype=float)
centroid_X = np.array(centroid_X, dtype=float)
centroid_Y = np.array(centroid_Y, dtype=float)
centroid_Z = np.array(centroid_Z, dtype=float)

total_interpolated = sum(r["interpolated_points"] for r in per_fish_rows)
total_points = n_frames * len(FISH_IDS)

# QC 判定：当前是 pilot 规则
interpolated_ratio = total_interpolated / total_points
if interpolated_ratio <= 0.05 and all_speeds.max() < 2.0:
    qc_status = "pass"
else:
    qc_status = "check"

summary_row = {
    "video_id": "mvp3d_best30_9_00_9_30",
    "trajectory_version": "final_manual_v1",
    "source_csv": str(SRC),
    "final_csv": str(FINAL_COPY),
    "fps": FPS,
    "duration_sec": duration_sec,
    "n_frames": n_frames,
    "n_fish": len(FISH_IDS),
    "total_points": total_points,
    "total_interpolated_points": total_interpolated,
    "interpolated_ratio": interpolated_ratio,

    "group_mean_speed": float(all_speeds.mean()),
    "group_median_speed": float(np.median(all_speeds)),
    "group_p95_speed": float(np.percentile(all_speeds, 95)),
    "group_max_speed": float(all_speeds.max()),

    "mean_inter_fish_distance": float(mean_inter_fish_distances.mean()),
    "median_inter_fish_distance": float(np.median(mean_inter_fish_distances)),
    "min_inter_fish_distance_mean": float(min_inter_fish_distances.mean()),
    "min_inter_fish_distance_min": float(min_inter_fish_distances.min()),

    "mean_nearest_neighbor_distance": float(nearest_neighbor_distances.mean()),
    "median_nearest_neighbor_distance": float(np.median(nearest_neighbor_distances)),

    "mean_group_dispersion": float(group_dispersions.mean()),
    "median_group_dispersion": float(np.median(group_dispersions)),
    "max_group_dispersion": float(group_dispersions.max()),

    "centroid_mean_X": float(centroid_X.mean()),
    "centroid_mean_Y": float(centroid_Y.mean()),
    "centroid_mean_Z": float(centroid_Z.mean()),

    "all_X_min": float(all_X.min()),
    "all_X_max": float(all_X.max()),
    "all_Y_min": float(all_Y.min()),
    "all_Y_max": float(all_Y.max()),
    "all_Z_min": float(all_Z.min()),
    "all_Z_max": float(all_Z.max()),

    "all_X_range": float(all_X.max() - all_X.min()),
    "all_Y_range": float(all_Y.max() - all_Y.min()),
    "all_Z_range": float(all_Z.max() - all_Z.min()),

    # 粗略空间利用：相对坐标包围盒体积
    "bbox_space_use_volume": float(
        (all_X.max() - all_X.min()) *
        (all_Y.max() - all_Y.min()) *
        (all_Z.max() - all_Z.min())
    ),

    "qc_status": qc_status,
    "qc_note": "pilot final_manual_v1; relative tank coordinates; metrics for behavior-analysis feasibility and future GCN input preparation",
}

# 写总表
with OUT_METRICS.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_row.keys()))
    writer.writeheader()
    writer.writerow(summary_row)

# 写每条鱼表
with OUT_PER_FISH.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(per_fish_rows[0].keys()))
    writer.writeheader()
    writer.writerows(per_fish_rows)

print("=" * 80)
print("PILOT BEHAVIOR METRICS FINAL MANUAL V1")
print("=" * 80)
print("final trajectory copy:", FINAL_COPY)
print("summary metrics:", OUT_METRICS)
print("per-fish metrics:", OUT_PER_FISH)
print("")
print("QC status:", qc_status)
print("duration_sec:", duration_sec)
print("n_frames:", n_frames)
print("total_interpolated_points:", total_interpolated)
print("interpolated_ratio:", f"{interpolated_ratio*100:.2f}%")
print("group_mean_speed:", f"{summary_row['group_mean_speed']:.4f}")
print("mean_inter_fish_distance:", f"{summary_row['mean_inter_fish_distance']:.4f}")
print("mean_nearest_neighbor_distance:", f"{summary_row['mean_nearest_neighbor_distance']:.4f}")
print("mean_group_dispersion:", f"{summary_row['mean_group_dispersion']:.4f}")
print("centroid_mean_Z:", f"{summary_row['centroid_mean_Z']:.4f}")
print("bbox_space_use_volume:", f"{summary_row['bbox_space_use_volume']:.4f}")
