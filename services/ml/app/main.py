import logging
import os
from collections import Counter

from fastapi import Depends, FastAPI, Header, HTTPException

from . import buffer
from .schemas import IngestRequest, IngestResponse

log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Mousetrap ML")

INTERNAL_KEY = os.environ.get("ML_INTERNAL_KEY", "")


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """All endpoints except /healthz require the shared internal key (ARCHITECTURE.md 8.1)."""
    if not INTERNAL_KEY or x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_internal_key)])
def ingest(req: IngestRequest) -> IngestResponse:
    buf = buffer.append(req.userId, req.sessionId, req.batch)
    kinds = Counter(e.k for e in req.batch.events)
    log.info(
        "ingest user=%s session=%s… seq=%d events=%d %s synthetic=%d buffered=%d",
        req.userId,
        req.sessionId[:8],
        req.batch.seq,
        len(req.batch.events),
        dict(kinds),
        req.batch.synthetic,
        len(buf.events),
    )
    return IngestResponse(ok=True, buffered=len(buf.events))


# Stage 5+: /risk/{sessionId}, /enroll/*, /feedback, /users/{userId}/status
# all declared with dependencies=[Depends(require_internal_key)].
