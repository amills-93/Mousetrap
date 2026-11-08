"""Train the scam classifier and report honest numbers (ARCHITECTURE.md 8.7).

    python scripts/train_classifier.py            # at image build; writes $CLASSIFIER_DIR/{model.joblib,metrics.json}

data/classifier_metrics.json in the repo is a copy of the metrics from the image build, for the docs:
    docker compose run --rm --no-deps ml cat /app/classifier/metrics.json > services/ml/data/classifier_metrics.json

Evaluation: fit on the "train" templates only, score the "heldout" templates (wording the model never saw), and
compare with the rules-only baseline on the same rows. A random split is reported too, to show how much easier
seen templates are. The shipped model is then refit on every row.
"""

import json
import random
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import classifier  # noqa: E402


def binary_metrics(y_true, y_pred, p=None) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()
    out = {
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "falsePositiveRate": round(fp / max(1, fp + tn), 4),
        "confusion": {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)},
    }
    if p is not None:
        out["rocAuc"] = round(roc_auc_score(y_true, p), 4)
    return out


def evaluate(train: list[dict], test: list[dict]) -> dict:
    m = classifier.fit([r["text"] for r in train], [r["label"] for r in train], [r["category"] for r in train])
    texts = [r["text"] for r in test]
    y = np.array([r["label"] == "scam" for r in test])
    p = m["binary"].predict_proba(texts)[:, 1]
    pred = p >= classifier.SCAM_AT
    out = {"rows": len(test), "model": binary_metrics(y, pred, p),
           "baseline": binary_metrics(y, np.array([classifier.baseline_is_scam(t) for t in texts]))}

    scams = [r for r in test if r["label"] == "scam"]
    cat_pred = m["category"].predict([r["text"] for r in scams])
    out["categoryAccuracy"] = round(float(np.mean([c == r["category"] for c, r in zip(cat_pred, scams)])), 4)
    per = {}
    for r, ok in zip(test, pred):
        key = r["category"]
        hit = bool(ok) == (r["label"] == "scam")
        a, n = per.get(key, (0, 0))
        per[key] = (a + hit, n + 1)
    out["perCategoryAccuracy"] = {k: round(a / n, 4) for k, (a, n) in sorted(per.items())}
    missed = [r for r, ok in zip(test, pred) if bool(ok) != (r["label"] == "scam")]
    out["examplesWrong"] = [{"text": r["text"], "label": r["label"], "category": r["category"]} for r in missed[:12]]
    return out


def main():
    rows = classifier.load_messages()
    train = [r for r in rows if r["split"] == "train"]
    heldout = [r for r in rows if r["split"] == "heldout"]
    metrics = {"heldoutTemplates": evaluate(train, heldout)}

    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    cut = int(len(shuffled) * 0.75)
    metrics["randomSplit"] = {k: v for k, v in evaluate(shuffled[:cut], shuffled[cut:]).items() if k != "examplesWrong"}
    metrics["thresholds"] = {"scam": classifier.SCAM_AT, "suspicious": classifier.SUSPICIOUS_AT}
    metrics["dataset"] = {"rows": len(rows), "scam": sum(r["label"] == "scam" for r in rows), "heldout": len(heldout)}

    bundle = classifier.fit([r["text"] for r in rows], [r["label"] for r in rows], [r["category"] for r in rows])
    classifier.CLASSIFIER_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, classifier.CLASSIFIER_DIR / "model.joblib")
    (classifier.CLASSIFIER_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    h = metrics["heldoutTemplates"]
    print(f"held-out templates ({h['rows']} rows): model F1 {h['model']['f1']} (P {h['model']['precision']}, "
          f"R {h['model']['recall']}, FPR {h['model']['falsePositiveRate']}, AUC {h['model']['rocAuc']}); "
          f"baseline F1 {h['baseline']['f1']} (FPR {h['baseline']['falsePositiveRate']}); "
          f"category acc {h['categoryAccuracy']}")
    r = metrics["randomSplit"]
    print(f"random split: model F1 {r['model']['f1']}, baseline F1 {r['baseline']['f1']}")


if __name__ == "__main__":
    main()
