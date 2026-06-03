from pathlib import Path
import csv
import copy
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path("/mnt/e/pilot exp")

MVP = ROOT / "dual_view_test_10min/mvp3d_9_10min/mvp3d_best30_9_00_9_30"

SRC = MVP / "reconstruction_offset460/cleaned/trajectory_3d_cleaned_interpolated_smoothed.csv"

OUT = MVP / "manual_direct_edit/final_state_machine_corrected"
OUT.mkdir(parents=True, exist_ok=True)

OUT_DIRECT = OUT / "trajectory_3d_state_machine_rules_applied.csv"
OUT_INTERP = OUT / "trajectory_3d_state_machine_interpolated.csv"
OUT_SMOOTH = OUT / "trajectory_3d_state_machine_interpolated_smoothed.csv"
OUT_REPORT = OUT / "state_machine_correction_report.txt"

FIG_3D = OUT / "trajectory_3d_state_machine_smoothed.png"
FIG_XY = OUT / "trajectory_xy_state_machine_smoothed.png"
FIG_Z = OUT / "trajectory_z_time_state_machine_smoothed.png"

FPS = 30
N_SAMPLES = 900
FISH_IDS = ["fish_1", "fish_2", "fish_3"]

# -----------------------------
# Final confirmed rules
# -----------------------------

# R1: 交换过程，三条鱼全部无效
SWAP_PROCESS_START = 186
SWAP_PROCESS_END = 193

# R2: 194 之后标签整体错位，需要重映射到真实 fish_id
REMAP_START = 194
REMAP_END = 899

# 当前错误标签 -> 正确最终标签
# 你的解释：真实 fish_1 被错贴成 fish_2；真实 fish_2 被错贴成 fish_3；真实 fish_3 被错贴成 fish_1
# 所以修正：当前 fish_2 -> fish_1；当前 fish_3 -> fish_2；当前 fish_1 -> fish_3
REMAP = {
    "fish_1": "fish_3",
    "fish_2": "fish_1",
    "fish_3": "fish_2",
}

# R3: 当前标签 fish_1 / fish_3 在 195–202 定位错误
BAD_LOC_START = 195
BAD_LOC_END = 202
BAD_LOC_CURRENT_LABELS = {"fish_1", "fish_3"}

def read_src(path):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "sample_idx": int(float(r["sample_idx"])),
                "time_sec": float(r["time_sec"]),
                "fish_id": r["fish_id"],
                "X": float(r["X"]),
                "Y": float(r["Y"]),
                "Z": float(r["Z"]),
                "original_interpolated": int(float(r.get("interpolated", 0))),
                "valid": 1,
                "note": "",
            })
    return rows

def apply_state_machine_rules(rows):
    out = []

    for r in rows:
        rr = copy.deepcopy(r)
        i = rr["sample_idx"]
        current_fid = rr["fish_id"]

        # R1: 186–193 三鱼交换过程，全设无效
        if SWAP_PROCESS_START <= i <= SWAP_PROCESS_END:
            rr["valid"] = 0
            rr["note"] += "R1_swap_process_all_fish_valid0;"

        # R3: 195–202 当前 fish_1 / fish_3 定位错误
        # 注意：这是在重映射之前按“当前标签”判断
        if BAD_LOC_START <= i <= BAD_LOC_END and current_fid in BAD_LOC_CURRENT_LABELS:
            rr["valid"] = 0
            rr["note"] += f"R3_bad_localization_current_{current_fid}_valid0;"

        # R2: 194–899 整体重映射
        if REMAP_START <= i <= REMAP_END:
            new_fid = REMAP[current_fid]
            rr["fish_id"] = new_fid
            rr["note"] += f"R2_remap_{current_fid}_to_{new_fid};"

        out.append(rr)

    return sorted(out, key=lambda x: (x["sample_idx"], x["fish_id"]))

def save_direct(rows, path):
    fieldnames = [
        "sample_idx", "time_sec", "fish_id",
        "X", "Y", "Z",
        "valid", "original_interpolated", "note"
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def interpolate(rows, smooth=False, win=5):
    by_fish = {fid: {} for fid in FISH_IDS}
    duplicates = []

    for r in rows:
        if int(r["valid"]) != 1:
            continue

        fid = r["fish_id"]
        i = int(r["sample_idx"])

        if fid not in by_fish:
            continue

        if i in by_fish[fid]:
            duplicates.append((i, fid))

        by_fish[fid][i] = r

    samples = np.arange(N_SAMPLES)
    out = []

    for fid in FISH_IDS:
        available = sorted(by_fish[fid].keys())

        if len(available) < 2:
            raise RuntimeError(f"{fid} has fewer than 2 valid points. Cannot interpolate.")

        xs = np.array(available, dtype=float)
        coords = {}

        for coord in ["X", "Y", "Z"]:
            ys = np.array([by_fish[fid][i][coord] for i in available], dtype=float)
            interp = np.interp(samples.astype(float), xs, ys)

            if smooth:
                kernel = np.ones(win) / win
                padded = np.pad(interp, (win // 2, win // 2), mode="edge")
                interp = np.convolve(padded, kernel, mode="valid")

            coords[coord] = interp

        for i in samples:
            out.append({
                "sample_idx": int(i),
                "time_sec": i / FPS,
                "fish_id": fid,
                "X": coords["X"][i],
                "Y": coords["Y"][i],
                "Z": coords["Z"][i],
                "interpolated": 0 if int(i) in by_fish[fid] else 1,
            })

    return sorted(out, key=lambda x: (x["sample_idx"], x["fish_id"])), duplicates

def save_traj(rows, path):
    fieldnames = ["sample_idx", "time_sec", "fish_id", "X", "Y", "Z", "interpolated"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def plot(rows):
    data = {fid: [] for fid in FISH_IDS}
    for r in rows:
        data[r["fish_id"]].append(r)

    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")
    for fid in FISH_IDS:
        rs = data[fid]
        ax.plot(
            [float(r["X"]) for r in rs],
            [float(r["Y"]) for r in rs],
            [float(r["Z"]) for r in rs],
            label=fid
        )
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("Final state-machine corrected 3D trajectories")
    ax.legend()
    plt.tight_layout()
    plt.savefig(FIG_3D, dpi=300)
    plt.close()

    plt.figure(figsize=(7, 6))
    for fid in FISH_IDS:
        rs = data[fid]
        plt.plot(
            [float(r["X"]) for r in rs],
            [float(r["Y"]) for r in rs],
            label=fid
        )
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Final state-machine corrected XY trajectories")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_XY, dpi=300)
    plt.close()

    plt.figure(figsize=(9, 5))
    for fid in FISH_IDS:
        rs = data[fid]
        plt.plot(
            [float(r["time_sec"]) for r in rs],
            [float(r["Z"]) for r in rs],
            label=fid
        )
    plt.xlabel("Time (s)")
    plt.ylabel("Z")
    plt.title("Final state-machine corrected Z over time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_Z, dpi=300)
    plt.close()

def write_report(direct_rows, interp_rows, smooth_rows, duplicates):
    valid0 = sum(1 for r in direct_rows if int(r["valid"]) == 0)
    r1_n = sum(1 for r in direct_rows if "R1_swap_process" in r["note"])
    r2_n = sum(1 for r in direct_rows if "R2_remap" in r["note"])
    r3_n = sum(1 for r in direct_rows if "R3_bad_localization" in r["note"])
    interpolated_n = sum(1 for r in smooth_rows if int(r["interpolated"]) == 1)

    lines = []
    lines.append("Final state-machine manual correction report")
    lines.append("=" * 80)
    lines.append(f"SRC: {SRC}")
    lines.append(f"OUT: {OUT}")
    lines.append("")
    lines.append("Confirmed correction rules:")
    lines.append("R1: global sample 186–193, all fish valid=0; swap process / unstable identity.")
    lines.append("R2: global sample 194–899, remap current fish_2→fish_1, fish_3→fish_2, fish_1→fish_3.")
    lines.append("R3: global sample 195–202, current fish_1 and current fish_3 valid=0; keep 194 and 203 as anchors.")
    lines.append("")
    lines.append("Counts:")
    lines.append(f"total direct rows: {len(direct_rows)}")
    lines.append(f"R1 valid=0 rows: {r1_n}")
    lines.append(f"R2 remapped rows: {r2_n}")
    lines.append(f"R3 bad-localization valid=0 rows: {r3_n}")
    lines.append(f"total valid=0 rows: {valid0}")
    lines.append(f"total interpolated rows after smoothing: {interpolated_n}")
    lines.append(f"duplicate sample/fish keys: {len(duplicates)}")
    lines.append("")
    lines.append("Output files:")
    lines.append(str(OUT_DIRECT))
    lines.append(str(OUT_INTERP))
    lines.append(str(OUT_SMOOTH))
    lines.append(str(FIG_3D))
    lines.append(str(FIG_XY))
    lines.append(str(FIG_Z))

    OUT_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))

src_rows = read_src(SRC)
direct_rows = apply_state_machine_rules(src_rows)

save_direct(direct_rows, OUT_DIRECT)

interp_rows, dup1 = interpolate(direct_rows, smooth=False)
smooth_rows, dup2 = interpolate(direct_rows, smooth=True, win=5)

save_traj(interp_rows, OUT_INTERP)
save_traj(smooth_rows, OUT_SMOOTH)

plot(smooth_rows)

duplicates = dup1 + dup2
write_report(direct_rows, interp_rows, smooth_rows, duplicates)

print("\nDONE")
