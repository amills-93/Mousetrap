import logging
import os
from collections import Counter

from fastapi import Depends, FastAPI, Header, HTTPException

from . import buffer, enrollment, features, model
from .schemas import EnrollFinishResponse, IngestRequest, IngestResponse, UserStatus

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
    if enrollment.is_enrolling(user_id):
        enroll_windows = enrollment.add(user_id, rows)
        phase = "enroll"
    else:
        phase = "live"  # Stage 6 scores these
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
        f" enroll={enroll_windows}" if enroll_windows is not None else "",
    )
    return IngestResponse(ok=True, buffered=len(buf.events), windows=len(rows), enrollWindows=enroll_windows)


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
    trained = model.train(user_id, rows)
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


# Stage 6+: /risk/{sessionId}, /feedback, all declared with dependencies=internal.
