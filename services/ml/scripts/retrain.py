"""Retrain every user's model from their logged enrollment windows (models/{userId}/features.parquet).

Use after changing model.py (e.g. the Stage 6 per-modality format). Run inside the ml container:
    docker compose exec ml python scripts/retrain.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import model  # noqa: E402
from app.features import FEATURES  # noqa: E402

for path in sorted(model.MODELS_DIR.glob("*/features.parquet")):
    user_id = path.parent.name
    df = pd.read_parquet(path)
    rows = df[df.phase == "enroll"][FEATURES].to_dict("records")
    if len(rows) < model.MIN_WINDOWS:
        print(f"{user_id}: skipped, {len(rows)} enrollment windows")
        continue
    try:
        info = model.train(user_id, rows)
        print(f"{user_id}: v{info['version']} windows={info['windowCount']} modalities={info['modalities']}")
    except ValueError as e:
        print(f"{user_id}: {e}")
