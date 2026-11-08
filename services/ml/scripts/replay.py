"""Replay logged windows through a user's model and the session EWMA to see where the score settles.

    docker compose exec ml python scripts/replay.py <modelUserId> <dataUserId> [enroll|live]

e.g. the owner's model against the owner's own browsing, then against a second person's windows.
Bot heuristics need raw events and are not replayed.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import model, scoring  # noqa: E402
from app.features import FEATURES  # noqa: E402

model_user, data_user = sys.argv[1], sys.argv[2]
phases = sys.argv[3:] or ["live"]
df = pd.read_parquet(model.user_dir(data_user) / "features.parquet")
df = df[df.phase.isin(phases)].sort_values("ts")

risk, trace, windows = 0.0, [], 0
for feats in df[FEATURES].to_dict("records"):
    mods = model.window_risk(model_user, feats)
    if mods is None:
        sys.exit(f"{model_user} has no current model; run scripts/retrain.py")
    r = scoring.combine(mods)
    if r is None:
        continue
    risk = r if windows == 0 else scoring.ALPHA * r + (1 - scoring.ALPHA) * risk
    windows += 1
    trace.append(risk)

if not trace:
    sys.exit("no scorable windows")
t = np.array(trace)
print(f"model={model_user} data={data_user} phases={phases} windows={len(t)}")
print(f"  EWMA mean={t.mean():.2f} p90={np.percentile(t, 90):.2f} max={t.max():.2f} final={t[-1]:.2f}")
print("  trace:", " ".join(f"{x:.2f}" for x in t[:: max(1, len(t) // 25)]))
