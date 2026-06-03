from pathlib import Path
import cv2
import csv
import numpy as np

ROOT = Path("/mnt/e/pilot exp")

BASE = ROOT / "dual_view_test_10min/mvp3d_9_10min"
MVP = BASE / "mvp3d_best30_9_00_9_30"

TOP_VIDEO = ROOT / "dual_view_test_10min/fixed60/TOP_dualview_10min_fixed60.mp4"
LEFT_VIDEO = ROOT / "dual_view_test_10min/fixed60/LEFT_dualview_10min_fixed60.mp4"

P_TOP = BASE / "calibration/P_top.txt"
P_LEFT = BASE / "calibration/P_left.txt"

# 先用清洗后的最终轨迹。如果你后面生成了 manual_direct_corrected，可以把这里换成那一个。
TRAJ_CSV = MVP / "reconstruction_offset460/cleaned/trajectory_3d_cleaned_interpolated_smoothed.csv"

OUT = MVP / "review_videos"
OUT.mkdir(parents=True, exist_ok=True)

OUT_TOP = OUT / "TOP_fish123_reprojected_9_00_9_30.mp4"
OUT_LEFT = OUT / "LEFT_fish123_reprojected_offset460_9_00_9_30.mp4"
OUT_PAIR = OUT / "paired_TOP_LEFT_fish123_reprojected_offset460.mp4"
OUT_QC = OUT / "fish123_reprojection_review_points.csv"

SOURCE_FPS = 60
TARGET_FPS = 30
START_SEC = 9 * 60
N_SAMPLES = 900
LEFT_OFFSET = 460
PAIR_HEIGHT = 720

FISH_IDS = ["fish_1", "fish_2", "fish_3"]

# BGR colors for OpenCV
COLORS = {
    "fish_1": (0, 0, 255),      # red
    "fish_2": (0, 255, 0),      # green
    "fish_3": (255, 0, 0),      # blue
}

def load_P(path):
    return np.loadtxt(path)

def project(P, X, Y, Z):
    Xh = np.array([X, Y, Z, 1.0], dtype=float)
    x = P @ Xh
    if abs(x[2]) < 1e-12:
        return None
    u = x[0] / x[2]
    v = x[1] / x[2]
    return float(u), float(v)

def read_traj(path):
    data = {}

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            i = int(float(r["sample_idx"]))
            fid = r["fish_id"]

            data.setdefault(i, {})[fid] = {
                "X": float(r["X"]),
                "Y": float(r["Y"]),
                "Z": float(r["Z"]),
                "interpolated": int(float(r.get("interpolated", 0))),
            }

    return data

def resize_to_height(img, target_h):
    h, w = img.shape[:2]
    scale = target_h / h
    new_w = int(w * scale)
    return cv2.resize(img, (new_w, target_h))

def draw_fish_labels(frame, points, view_name, sample_idx, video_time_sec):
    img = frame.copy()

    header = f"{view_name} fish_1/2/3 reprojected | sample={sample_idx} | t={video_time_sec:.2f}s"
    cv2.putText(
        img,
        header,
        (30, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.95,
        (0, 255, 255),
        3,
        cv2.LINE_AA,
    )

    h, w = img.shape[:2]

    for fid in FISH_IDS:
        if fid not in points:
            continue

        p = points[fid]
        if p["uv"] is None:
            continue

        u, v = p["uv"]
        x = int(round(u))
        y = int(round(v))

        color = COLORS[fid]
        interp = p["interpolated"]

        # 如果投影点在画面外，也画到边界并标记 OUT
        out_flag = not (0 <= x < w and 0 <= y < h)
        x_draw = min(max(x, 0), w - 1)
        y_draw = min(max(y, 0), h - 1)

        radius = 11 if interp == 0 else 8
        thickness = -1 if interp == 0 else 3

        cv2.circle(img, (x_draw, y_draw), radius, color, thickness)

        label = fid
        if interp == 1:
            label += " interp"
        if out_flag:
            label += " OUT"

        cv2.putText(
            img,
            label,
            (x_draw + 12, max(35, y_draw - 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            color,
            3,
            cv2.LINE_AA,
        )

        # 画十字线，方便定位
        cv2.line(img, (x_draw - 15, y_draw), (x_draw + 15, y_draw), color, 2)
        cv2.line(img, (x_draw, y_draw - 15), (x_draw, y_draw + 15), color, 2)

    return img

P_top = load_P(P_TOP)
P_left = load_P(P_LEFT)
traj = read_traj(TRAJ_CSV)

top_cap = cv2.VideoCapture(str(TOP_VIDEO))
left_cap = cv2.VideoCapture(str(LEFT_VIDEO))

if not top_cap.isOpened():
    raise RuntimeError(f"Cannot open TOP video: {TOP_VIDEO}")
if not left_cap.isOpened():
    raise RuntimeError(f"Cannot open LEFT video: {LEFT_VIDEO}")

top_frame0_id = int(START_SEC * SOURCE_FPS)
left_frame0_id = int(START_SEC * SOURCE_FPS + LEFT_OFFSET * 2)

top_cap.set(cv2.CAP_PROP_POS_FRAMES, top_frame0_id)
left_cap.set(cv2.CAP_PROP_POS_FRAMES, left_frame0_id)

ok_top, top0 = top_cap.read()
ok_left, left0 = left_cap.read()

if not ok_top or not ok_left:
    raise RuntimeError("Cannot read initial frames")

top_h, top_w = top0.shape[:2]
left_h, left_w = left0.shape[:2]

fourcc = cv2.VideoWriter_fourcc(*"mp4v")

top_writer = cv2.VideoWriter(str(OUT_TOP), fourcc, TARGET_FPS, (top_w, top_h))
left_writer = cv2.VideoWriter(str(OUT_LEFT), fourcc, TARGET_FPS, (left_w, left_h))

top_small0 = resize_to_height(top0, PAIR_HEIGHT)
left_small0 = resize_to_height(left0, PAIR_HEIGHT)
pair_w = top_small0.shape[1] + left_small0.shape[1]
pair_writer = cv2.VideoWriter(str(OUT_PAIR), fourcc, TARGET_FPS, (pair_w, PAIR_HEIGHT))

qc_rows = []

print("=" * 80)
print("Making fish_1/2/3 reprojected review video")
print("=" * 80)
print("Trajectory CSV:", TRAJ_CSV)
print("Output:", OUT)
print("LEFT_OFFSET:", LEFT_OFFSET, "frames =", LEFT_OFFSET / TARGET_FPS, "sec")

for i in range(N_SAMPLES):
    top_sample = i
    left_sample = i + LEFT_OFFSET

    top_frame_id = int(START_SEC * SOURCE_FPS + top_sample * 2)
    left_frame_id = int(START_SEC * SOURCE_FPS + left_sample * 2)

    top_cap.set(cv2.CAP_PROP_POS_FRAMES, top_frame_id)
    left_cap.set(cv2.CAP_PROP_POS_FRAMES, left_frame_id)

    ok_top, top_frame = top_cap.read()
    ok_left, left_frame = left_cap.read()

    if not ok_top or not ok_left:
        print(f"Read failed at sample {i}")
        break

    frame_traj = traj.get(i, {})

    top_points = {}
    left_points = {}

    for fid in FISH_IDS:
        if fid not in frame_traj:
            continue

        row = frame_traj[fid]
        X, Y, Z = row["X"], row["Y"], row["Z"]

        top_uv = project(P_top, X, Y, Z)
        left_uv = project(P_left, X, Y, Z)

        top_points[fid] = {
            "uv": top_uv,
            "interpolated": row["interpolated"],
        }

        left_points[fid] = {
            "uv": left_uv,
            "interpolated": row["interpolated"],
        }

        qc_rows.append({
            "sample_idx": i,
            "time_sec": i / TARGET_FPS,
            "left_sample_idx": left_sample,
            "fish_id": fid,
            "X": X,
            "Y": Y,
            "Z": Z,
            "top_x_proj": "" if top_uv is None else top_uv[0],
            "top_y_proj": "" if top_uv is None else top_uv[1],
            "left_x_proj": "" if left_uv is None else left_uv[0],
            "left_y_proj": "" if left_uv is None else left_uv[1],
            "interpolated": row["interpolated"],
        })

    top_time = START_SEC + top_sample / TARGET_FPS
    left_time = START_SEC + left_sample / TARGET_FPS

    top_draw = draw_fish_labels(top_frame, top_points, "TOP", top_sample, top_time)
    left_draw = draw_fish_labels(left_frame, left_points, "LEFT", left_sample, left_time)

    top_writer.write(top_draw)
    left_writer.write(left_draw)

    top_small = resize_to_height(top_draw, PAIR_HEIGHT)
    left_small = resize_to_height(left_draw, PAIR_HEIGHT)

    pair = cv2.hconcat([top_small, left_small])
    pair_writer.write(pair)

    if i % 100 == 0:
        print(f"processed {i}/{N_SAMPLES}")

top_cap.release()
left_cap.release()
top_writer.release()
left_writer.release()
pair_writer.release()

with OUT_QC.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "sample_idx",
        "time_sec",
        "left_sample_idx",
        "fish_id",
        "X", "Y", "Z",
        "top_x_proj",
        "top_y_proj",
        "left_x_proj",
        "left_y_proj",
        "interpolated",
    ])
    writer.writeheader()
    writer.writerows(qc_rows)

print("\nDONE")
print("TOP fish123 video:", OUT_TOP)
print("LEFT fish123 video:", OUT_LEFT)
print("Paired fish123 video:", OUT_PAIR)
print("Projection points csv:", OUT_QC)
