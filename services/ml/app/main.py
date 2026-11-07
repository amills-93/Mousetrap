import os

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Mousetrap ML")

INTERNAL_KEY = os.environ.get("ML_INTERNAL_KEY", "")


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """All endpoints except /healthz require the shared internal key (ARCHITECTURE.md 8.1)."""
    if not INTERNAL_KEY or x_internal_key != INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="invalid internal key")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


# Stage 4+: /ingest, /risk/{sessionId}, /enroll/*, /feedback, /users/{userId}/status
# all declared with dependencies=[Depends(require_internal_key)].
