import logging
import os
from collections import Counter

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException

from . import buffer, enrollment, features, model, scoring
from .schemas import (
    EnrollFinishResponse, FeedbackRequest, FeedbackResponse, IngestRequest, IngestResponse, RiskResponse, UserStatus,
)

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Mousetrap ML")

INTERNAL_KEY = os.environ.get("ML_INTERNAL_KEY", "")


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """All endpoints except /healthz require the shared internal key (ARCHITECTURE.md 8.1)."""
    if not INTERNAL_KEY or x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")


def valid_user(user_id: str) -> str:
    try:
        model.user_dir(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user id")
    return user_id


internal = [Depends(require_internal_key)]


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/ingest", response_model=IngestResponse, dependencies=internal)
def ingest(req: IngestRequest) -> IngestResponse:
    user_id = valid_user(req.userId)
    buf, windows = buffer.append(user_id, req.sessionId, req.batch)
    rows = [features.extract(w) for w in windows]

    enroll_windows = None
    st = None
    if enrollment.is_enrolling(user_id):
        enroll_windows = enrollment.add(user_id, rows)
        phase = "enroll"
    else:
        phase = "live"
        st = scoring.update(user_id, req.sessionId, windows, rows, req.batch.synthetic)
    enrollment.log_features(user_id, req.sessionId, phase, rows)

    kinds = Counter(e.k for e in req.batch.events)
    log.info(
        "ingest user=%s session=%s… seq=%d events=%d %s synthetic=%d buffered=%d windows=%d%s",
        user_id,
        req.sessionId[:8],
        req.batch.seq,
        len(req.batch.events),
        dict(kinds),
        req.batch.synthetic,
        len(buf.events),
        len(rows),
        f" enroll={enroll_windows}" if enroll_windows is not None else
        (f" risk={st.risk:.2f} scored={st.windows}" if st else ""),
    )
    return IngestResponse(
        ok=True, buffered=len(buf.events), windows=len(rows), enrollWindows=enroll_windows,
        risk=round(st.risk, 4) if st and st.windows else None, scoredWindows=st.windows if st else None,
    )


@app.post("/enroll/{user_id}/start", dependencies=internal)
def enroll_start(user_id: str) -> dict:
    enrollment.start(valid_user(user_id))
    log.info("enroll start user=%s", user_id)
    return {"ok": True}


@app.post("/enroll/{user_id}/finish", response_model=EnrollFinishResponse, dependencies=internal)
def enroll_finish(user_id: str) -> EnrollFinishResponse:
    valid_user(user_id)
    if not enrollment.is_enrolling(user_id):
        return EnrollFinishResponse(ok=False, windowCount=0, error="not enrolling")
    # Close any half-full window so the last few seconds of the exercise count.
    tail = [features.extract(w) for w in buffer.drain_user(user_id)]
    enrollment.add(user_id, tail)
    enrollment.log_features(user_id, "-", "enroll", tail)
    rows = enrollment.take(user_id)
    if len(rows) < model.MIN_WINDOWS:
        return EnrollFinishResponse(
            ok=False, windowCount=len(rows), error=f"need at least {model.MIN_WINDOWS} windows"
        )
    try:
        trained = model.train(user_id, rows)
    except ValueError as e:
        return EnrollFinishResponse(ok=False, windowCount=len(rows), error=str(e))
    enrollment.finish(user_id)
    log.info("enroll finish user=%s windows=%d version=%d", user_id, len(rows), trained["version"])
    return EnrollFinishResponse(ok=True, windowCount=len(rows), modelVersion=trained["version"])


@app.get("/users/{user_id}/status", response_model=UserStatus, dependencies=internal)
def user_status(user_id: str) -> UserStatus:
    meta = model.meta(valid_user(user_id)) or {}
    return UserStatus(
        enrolled=bool(meta),
        enrolling=enrollment.is_enrolling(user_id),
        enrollWindows=enrollment.count(user_id),
        windowCount=meta.get("windowCount", 0),
        modelVersion=meta.get("version", 0),
    )


@app.get("/risk/{session_id}", response_model=RiskResponse, dependencies=internal)
def risk(session_id: str) -> RiskResponse:
    """Current session risk. windows=0 means nothing scored yet (or no model); Nuxt policy treats that as unknown."""
    st = scoring.get(session_id)
    if st is None:
        return RiskResponse(risk=0.0, windows=0, lastUpdated=None, components={})
    return RiskResponse(
        risk=round(st.risk, 4),
        windows=st.windows,
        lastUpdated=st.last_updated,
        components={k: round(v, 4) for k, v in st.components.items()},
        bot=round(st.bot, 2),
    )


def _retrain(user_id: str, rows: list[dict[str, float]]) -> None:
    try:
        info = model.retrain_with(user_id, rows)
        if info:
            log.info("feedback retrain user=%s version=%d windows=%d", user_id, info["version"], info["windowCount"])
    except Exception:  # background task: log, never crash the worker
        log.exception("feedback retrain failed user=%s", user_id)


@app.post("/feedback", response_model=FeedbackResponse, dependencies=internal)
def feedback(req: FeedbackRequest, tasks: BackgroundTasks) -> FeedbackResponse:
    """Called by Nuxt only after a successful step-up: the session's recent windows are the real user."""
    user_id = valid_user(req.userId)
    rows = scoring.take_recent(req.sessionId, user_id)
    if rows:
        enrollment.log_features(user_id, req.sessionId, "feedback", rows)
        tasks.add_task(_retrain, user_id, rows)
    log.info("feedback user=%s session=%s… label=%s windows=%d", user_id, req.sessionId[:8], req.label, len(rows))
    return FeedbackResponse(ok=True, windows=len(rows))
