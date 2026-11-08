"""Pydantic models mirroring collector event schema v1 (ARCHITECTURE.md 6.1).

extra="forbid": a payload carrying anything beyond timing and motion (e.g. a key value) is rejected.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

KeyClass = Literal["letter", "digit", "space", "backspace", "enter", "modifier", "nav", "other"]
T = Annotated[float, Field(ge=0)]


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    t: T


class KeyEvent(_Event):
    k: Literal["kd", "ku"]
    kc: KeyClass
    code_hash: Annotated[int, Field(ge=0, le=0xFFFF)]


class MoveEvent(_Event):
    k: Literal["mm"]
    x: int
    y: int


class ButtonEvent(_Event):
    k: Literal["md", "mu"]
    x: int
    y: int
    b: Annotated[int, Field(ge=0, le=4)]


class WheelEvent(_Event):
    k: Literal["wh"]
    dy: float


class FocusEvent(_Event):
    k: Literal["fc"]
    role: Annotated[str, Field(max_length=40)]


class NavEvent(_Event):
    k: Literal["nv"]
    route: Annotated[str, Field(max_length=200)]


CollectorEvent = Annotated[
    Union[KeyEvent, MoveEvent, ButtonEvent, WheelEvent, FocusEvent, NavEvent],
    Field(discriminator="k"),
]


class TelemetryBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    v: Literal[1]
    pageId: str
    seq: Annotated[int, Field(gt=0)]
    vw: Annotated[int, Field(gt=0)]
    vh: Annotated[int, Field(gt=0)]
    synthetic: Annotated[int, Field(ge=0)] = 0
    events: Annotated[list[CollectorEvent], Field(max_length=1000)]


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    userId: Annotated[str, Field(min_length=1)]
    sessionId: Annotated[str, Field(min_length=1)]
    batch: TelemetryBatch


class IngestResponse(BaseModel):
    ok: bool
    buffered: int
