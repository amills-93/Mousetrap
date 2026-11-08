"""Plot key per-window features for every enrolled user so you can check they visibly differ (Stage 5 gate).

In Docker (models live in the ml volume):
    docker compose exec ml python scripts/plot_features.py
    docker compose cp ml:/app/models/features.png .

Options: --phase enroll|live|all (default enroll), --out PATH, --label <userId>=<name> (repeatable).
Also prints per-user medians and a separation score per feature (spread of user medians / mean within-user std;
above ~1 means the feature tells users apart).
"""

import argparse
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

KEY = [
    "dwell_mean", "flight_mean", "digraph_mean", "typing_rate",
    "speed_mean", "accel_mean", "straightness", "angle_mean",
    "click_hold_mean", "pause_mean", "tap_dur_mean", "swipe_speed_mean",
]


def main() -> None:
    models = Path(os.environ.get("MODELS_DIR", Path(__file__).resolve().parent.parent / "models"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--models-dir", type=Path, default=models)
    ap.add_argument("--out", type=Path, default=models / "features.png")
    ap.add_argument("--phase", default="enroll", choices=["enroll", "live", "all"])
    ap.add_argument("--label", action="append", default=[], help="userId=name")
    args = ap.parse_args()
    labels = dict(x.split("=", 1) for x in args.label)

    frames = []
    for path in sorted(args.models_dir.glob("*/features.parquet")):
        df = pd.read_parquet(path)
        if args.phase != "all":
            df = df[df["phase"] == args.phase]
        if len(df):
            uid = path.parent.name
            frames.append(df.assign(user=labels.get(uid, uid[:8])))
    if not frames:
        sys.exit(f"no {args.phase} features under {args.models_dir}")
    df = pd.concat(frames, ignore_index=True)
    feats = [f for f in KEY if f in df and df[f].notna().any()]

    print(df.groupby("user").size().rename("windows").to_string(), "\n")
    print("per-user medians:")
    print(df.groupby("user")[feats].median().T.round(3).to_string(), "\n")
    if df["user"].nunique() > 1:
        sep = df.groupby("user")[feats].median().std() / df.groupby("user")[feats].std().mean()
        print("separation (higher = more distinctive):")
        print(sep.sort_values(ascending=False).round(2).to_string())

    cols = 4
    rows = -(-len(feats) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 3 * rows), squeeze=False)
    for ax, f in zip(axes.flat, feats):
        for user, g in df.groupby("user"):
            vals = g[f].dropna()
            if len(vals):
                ax.hist(vals, bins=20, alpha=0.5, label=f"{user} (n={len(vals)})")
        ax.set_title(f, fontsize=10)
    for ax in list(axes.flat)[len(feats):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle(f"Per-window features by user ({args.phase})")
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=110)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
