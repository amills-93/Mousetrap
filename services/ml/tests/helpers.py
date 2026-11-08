"""Synthetic event generators (schema v1 dicts)."""

import math
import random


def typing(t, n=30, dwell=90.0, gap=150.0, backspace_every=0):
    ev = []
    for i in range(n):
        c = random.randrange(40)
        kc = "backspace" if backspace_every and i % backspace_every == 0 else "letter"
        ev += [{"k": "kd", "t": round(t, 1), "kc": kc, "code_hash": c},
               {"k": "ku", "t": round(t + dwell + random.random() * 10, 1), "kc": kc, "code_hash": c}]
        t += gap + random.random() * 30
    return ev, t


def mouse(t, n=40, step=8.0, curve=4.0):
    ev, x, y = [], 100.0, 100.0
    for i in range(n):
        x += step + random.random() * 2
        y += curve * math.sin(i / 5)
        t += 20
        ev.append({"k": "mm", "t": round(t, 1), "x": int(x), "y": int(y)})
    ev += [{"k": "md", "t": round(t + 5, 1), "x": int(x), "y": int(y), "b": 0},
           {"k": "mu", "t": round(t + 105, 1), "x": int(x), "y": int(y), "b": 0}]
    return ev, t + 200


def wheel(t, n=10, flip_every=3):
    ev = []
    for i in range(n):
        dy = -100 if (i // flip_every) % 2 else 100
        ev.append({"k": "wh", "t": round(t, 1), "dy": dy})
        t += 50
    return ev, t


def tap(t, i, x=200, y=300, dur=80.0, r=12.0, f=0.0):
    return [{"k": "ts", "t": round(t, 1), "id": i, "x": x, "y": y, "r": r, "f": f},
            {"k": "te", "t": round(t + dur, 1), "id": i, "x": x + 2, "y": y + 1, "r": r, "f": f}], t + dur


def swipe(t, i, dx=0, dy=-300, steps=8, dur=240.0, r=14.0, f=0.0):
    ev = [{"k": "ts", "t": round(t, 1), "id": i, "x": 200, "y": 600, "r": r, "f": f}]
    for s in range(1, steps + 1):
        ev.append({"k": "tm", "t": round(t + dur * s / (steps + 1), 1), "id": i,
                   "x": int(200 + dx * s / steps), "y": int(600 + dy * s / steps), "r": r, "f": f})
    ev.append({"k": "te", "t": round(t + dur, 1), "id": i, "x": 200 + dx, "y": 600 + dy, "r": r, "f": f})
    return ev, t + dur


def batch(page, seq, events, vw=1280, vh=800, synthetic=0):
    return {"v": 1, "pageId": page, "seq": seq, "vw": vw, "vh": vh, "synthetic": synthetic, "events": events}
