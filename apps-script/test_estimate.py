#!/usr/bin/env python3
"""Valida el algoritmo de fecha estimada con los pedidos de Tracking."""
import json
import math
import datetime
from collections import defaultdict

TODAY = datetime.date(2026, 8, 24)
WORKDAYS = {1, 2, 3, 4, 5, 6}


def fold(s):
    t = str(s or "").lower()
    for a, b in zip("áéíóúü", "aeiouu"):
        t = t.replace(a, b)
    return t.strip()


def stage_rank(etapa):
    e = fold(etapa)
    if "espera de confeccion" in e:
        return 1
    if "confeccion" in e:
        return 0
    if e in ("terminado", "completado", "entregado"):
        return 3
    return 2


def add_workdays(start, offset):
    d = start
    while d.isoweekday() not in WORKDAYS:
        d += datetime.timedelta(days=1)
    remaining = offset
    while remaining > 0:
        d += datetime.timedelta(days=1)
        if d.isoweekday() in WORKDAYS:
            remaining -= 1
    return d


def estimate(rows, default_cap=130):
    line_caps = defaultdict(lambda: default_cap)
    for j in rows:
        for ln in j["lineas"]:
            line_caps[ln] = max(line_caps[ln], j["cap"] or default_cap)
    line_load = defaultdict(float)
    queued = [j for j in rows if j["faltante"] > 0]
    queued.sort(key=lambda j: (stage_rank(j["etapa"]), j["mo"] or "zzz", j["row"]))
    for j in queued:
        cands = j["lineas"] or ["SIN LINEA"]
        best = min(cands, key=lambda ln: line_load[ln] / (line_caps[ln] or default_cap))
        cap = line_caps[best] or default_cap
        start = line_load[best]
        end = start + j["faltante"]
        end_day = max(0, math.ceil(end / cap) - 1)
        line_load[best] = end
        j["lineaAsignada"] = best
        j["fechaEstimada"] = add_workdays(TODAY, end_day).isoformat()
        j["diaFinCola"] = end_day
    for j in rows:
        if j["faltante"] <= 0:
            j["fechaEstimada"] = None
            j["lineaAsignada"] = j["lineas"][0] if j["lineas"] else ""
    return line_caps, line_load


def main():
    with open("/workspace/apps-script/sample_data.json") as f:
        payload = json.load(f)
    rows = payload["rows"]
    # reset assignment before re-running
    for r in rows:
        r.pop("lineaAsignada", None)
        r.pop("fechaEstimada", None)
    caps, load = estimate(rows)

    falt = sum(r["faltante"] for r in rows)
    sol = sum(r["solicitada"] for r in rows)
    prod = sum(r["producida"] for r in rows)
    dated = [r for r in rows if r.get("fechaEstimada")]
    done = [r for r in rows if r["faltante"] <= 0]

    assert abs(sol - 3482) < 1, sol
    assert abs(prod - 1498) < 1, prod
    assert abs(falt - 2058) < 1, falt
    assert len(rows) == 86
    assert len(dated) == 56
    assert all(r.get("fechaEstimada") is None for r in done)

    assert abs(load["1"] + load["2"] - 646) < 1, dict(load)
    assert abs(load["3"] - 1412) < 1, dict(load)
    assert "Estampado" not in load or load["Estampado"] == 0

    last = max(r["fechaEstimada"] for r in dated)
    assert last == "2026-09-04", last

    # A espera de Confeccion must be scheduled after En Confeccion on same line
    demo = [
        {"row": 1, "mo": "1", "faltante": 130, "cap": 130, "lineas": ["3"], "etapa": "En Confeccion"},
        {"row": 2, "mo": "2", "faltante": 130, "cap": 130, "lineas": ["3"], "etapa": "A espera de Confeccion"},
    ]
    estimate(demo)
    assert demo[0]["fechaEstimada"] == "2026-08-24", demo[0]
    assert demo[1]["fechaEstimada"] == "2026-08-25", demo[1]
    assert demo[0]["diaFinCola"] < demo[1]["diaFinCola"]

    print("OK 86 SKUs | faltante 2058 | lineas", dict(load), "| ultima", last)


if __name__ == "__main__":
    main()
