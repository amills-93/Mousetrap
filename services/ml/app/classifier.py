"""Scam text classifier (ARCHITECTURE.md 8.7).

Two TF-IDF + logistic-regression models: scam vs not (word 1-2-grams plus character 3-5-grams, so lookalike
domains and odd spellings count), and, for scams, which taxonomy category. Red flags are plain rules over the text;
they explain a verdict to the customer and power the rules-only baseline that the model is measured against.
Trained by scripts/train_classifier.py at image build; loaded lazily here.
"""

import json
import os
import re
from pathlib import Path
from threading import Lock

import joblib
import numpy as np
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
CLASSIFIER_DIR = Path(os.environ.get("CLASSIFIER_DIR", APP_DIR / "classifier"))

SCAM_AT = 0.5  # p(scam) at or above: "scam"
SUSPICIOUS_AT = 0.25  # at or above (and below SCAM_AT): "suspicious", shown with a softer warning

_URL = re.compile(r"https?://([a-z0-9.-]+)", re.I)
_PHONE = re.compile(r"\(\d{3}\) ?555-01\d\d")
OFFICIAL_HOSTS = {"nimbus.example", "my.nimbus.example"}

# (id, customer-facing text, pattern). Order is the order shown.
RED_FLAGS = [
    ("asks_code", "Asks you to send or read out a verification code",
     re.compile(r"\b(reply|send|text|read|forward|share)\b[^.]{0,60}\bcode|\bcode\b[^.]{0,40}\b(reply|send me|forward|read)", re.I)),
    ("asks_pin", "Asks for your transfer or account PIN",
     re.compile(r"\b(transfer|port[- ]?out|account)\b[^.]{0,20}\bpin\b", re.I)),
    ("lookalike_link", "Link to a site that is not Nimbus's own", None),  # computed from _URL
    ("call_number", "Asks you to call a number in the message",
     re.compile(r"\bcall\b[^.]{0,40}\(\d{3}\) ?555-01\d\d", re.I)),
    ("threat", "Threatens suspension, lockout, or penalties",
     re.compile(r"\b(suspend|suspension|deactivat|disconnect|locked|lock(ed)? in|legal action|penalty|lose service|restricted)", re.I)),
    ("urgency", "Pushes you to act right away",
     re.compile(r"\b(urgent|immediately|right away|final notice|act now|within \d+ ?(h|hours|min)|before midnight|expir(e|es|ing) (soon|today)|don'?t ignore|do not ignore)", re.I)),
    ("money", "Asks for a fee, payment, or card details",
     re.compile(r"\b(pay|fee|update (your )?card|payment details|bank details|card number|transfer \$|send \$|deposit)", re.I)),
    ("too_good", "Offers a prize, reward, or guaranteed return",
     re.compile(r"\b(won|winner|free (phone|tablet|upgrade)|gift card|guarantee|cashback|reward|double your|10x)", re.I)),
    ("new_number", "Someone claiming to be family on a new number",
     re.compile(r"\b(new (phone|number)|this is my new|(dropped|lost|broke) my phone|my phone (broke|died)|friend'?s phone)", re.I)),
    ("off_platform", "Moves the conversation to another app or group",
     re.compile(r"\b(on (our|the) app|on chat|add our|join (our|the) (private )?group|message us on)", re.I)),
]


def _lookalike(host: str) -> bool:
    if host in OFFICIAL_HOSTS:
        return False
    return "nimbus" in host or "nmbus" in host or host.split(".")[0] in ("go", "lnk", "bit")


def red_flags(text: str) -> list[dict]:
    out = []
    for fid, label, rx in RED_FLAGS:
        if fid == "lookalike_link":
            # A Nimbus-looking host that isn't Nimbus's, or a link shortener hiding where it goes.
            if any(_lookalike(h.lower()) for h in _URL.findall(text)):
                out.append({"id": fid, "label": label})
            continue
        m = rx.search(text)
        if m and not (fid in _NEGATABLE and _negated(text, m)):
            out.append({"id": fid, "label": label})
    return out


_NEGATABLE = {"asks_code", "asks_pin"}
_NEGATION = re.compile(r"\b(never|don'?t share|do not share|not share)\b", re.I)


def _negated(text: str, m: re.Match) -> bool:
    """'We will never ask for your PIN' warns against the request rather than making it."""
    start = max(text.rfind(".", 0, m.start()), text.rfind("!", 0, m.start())) + 1
    end = min((i for i in (text.find(".", m.end()), text.find("!", m.end())) if i != -1), default=len(text))
    return bool(_NEGATION.search(text[start:end]))


def baseline_is_scam(text: str) -> bool:
    """Rules-only baseline: two or more red flags."""
    return len(red_flags(text)) >= 2


class RedFlagFeatures(BaseEstimator, TransformerMixin):
    """One column per red flag. They describe intent (asks for a code, threatens, links to a lookalike), which carries
    over to wording the n-grams never saw."""

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        ids = [f[0] for f in RED_FLAGS]
        rows = [[1.0 if fid in {f["id"] for f in red_flags(t)} else 0.0 for fid in ids] for t in X]
        return sparse.csr_matrix(np.array(rows))


def _features() -> FeatureUnion:
    return FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, lowercase=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=5, sublinear_tf=True, lowercase=True)),
        ("flags", RedFlagFeatures()),
    ])


def fit(texts: list[str], labels: list[str], categories: list[str]) -> dict:
    y = np.array([lab == "scam" for lab in labels])
    binary = Pipeline([("f", _features()), ("lr", LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced"))])
    binary.fit(texts, y)
    scam_idx = np.flatnonzero(y)
    category = Pipeline([("f", _features()), ("lr", LogisticRegression(C=4.0, max_iter=2000))])
    category.fit([texts[i] for i in scam_idx], [categories[i] for i in scam_idx])
    return {"binary": binary, "category": category}


def load_taxonomy() -> dict:
    return json.loads((DATA_DIR / "taxonomy.json").read_text())


def load_messages(path: Path | None = None) -> list[dict]:
    with open(path or DATA_DIR / "messages.jsonl") as f:
        return [json.loads(line) for line in f]


_lock = Lock()
_bundle: dict | None = None


def _model() -> dict:
    global _bundle
    with _lock:
        if _bundle is None:
            path = CLASSIFIER_DIR / "model.joblib"
            if not path.exists():
                raise FileNotFoundError(f"no classifier at {path}; run scripts/train_classifier.py")
            _bundle = {**joblib.load(path), "taxonomy": {c["id"]: c for c in load_taxonomy()["categories"]}}
        return _bundle


def classify(text: str) -> dict:
    b = _model()
    p = float(b["binary"].predict_proba([text])[0][1])
    verdict = "scam" if p >= SCAM_AT else "suspicious" if p >= SUSPICIOUS_AT else "ok"
    out = {"verdict": verdict, "scamProbability": round(p, 4), "redFlags": red_flags(text) if verdict != "ok" else [],
           "category": None, "categoryLabel": None, "categoryProbability": None, "advice": None, "accountRisk": False}
    if verdict != "ok":
        probs = b["category"].predict_proba([text])[0]
        i = int(np.argmax(probs))
        cat = b["taxonomy"].get(b["category"].classes_[i], {})
        out.update(category=cat.get("id"), categoryLabel=cat.get("label"), categoryProbability=round(float(probs[i]), 4),
                   advice=cat.get("advice"), accountRisk=bool(cat.get("accountRisk")) and verdict == "scam")
    return out
