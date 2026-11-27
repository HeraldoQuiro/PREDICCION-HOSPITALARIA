# -*- coding: utf-8 -*-
"""
=============================================================================
01_descargar_clima.py
Descarga el clima diario real de NASA POWER (MERRA-2) para Puno (2023-2026)
Coordenadas oficiales del proyecto: lat = -15.8396, lon = -70.0282
Variables (Sección 4.1 del PDF):
  T2M, T2M_MAX, T2M_MIN, RH2M, WD2M, GWETROOT, PRECTOTCORR
Calcula: rango_termico = T2M_MAX - T2M_MIN y temp_min_lag3 (media móvil t-1..t-3)
Salida: datos/clima_puno_nasa_power_2023_2026.csv
=============================================================================
"""

import csv
import json
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "datos"
OUTPUT_CSV = DATOS_DIR / "clima_puno_nasa_power_2023_2026.csv"

LAT = -15.8396
LON = -70.0282
START_DATE = "20230101"
END_DATE = "20261126"
PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "WD2M", "GWETROOT", "PRECTOTCORR"]


def download_nasa_power():
    url = (
        "https://power.larc.nasa.gov/api/temporal/daily/point"
        f"?parameters={','.join(PARAMS)}"
        "&community=RE"
        f"&longitude={LON}&latitude={LAT}"
        f"&start={START_DATE}&end={END_DATE}"
        "&time-standard=LST"
        "&format=JSON"
    )
    print(f"[01_descargar_clima] Consultando NASA POWER ({START_DATE}..{END_DATE})...")
    req = urllib.request.Request(url, headers={"User-Agent": "SatUCI-Puno/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    param_data = payload["properties"]["parameter"]
    dates = sorted(param_data["T2M_MIN"].keys())

    rows = []
    for d in dates:
        vals = {p: float(param_data[p].get(d, -999.0)) for p in PARAMS}
        # Excluir días sin dato (-999) en las variables core del modelo
        if any(vals[k] <= -900.0 for k in ("T2M_MIN", "T2M_MAX", "RH2M")):
            continue
        fecha_iso = datetime.strptime(d, "%Y%m%d").strftime("%Y-%m-%d")
        t_min = vals["T2M_MIN"]
        t_max = vals["T2M_MAX"]
        rango = round(t_max - t_min, 4)
        rows.append({
            "fecha": fecha_iso,
            "temp_media": round(vals["T2M"], 4),
            "temp_min": round(t_min, 4),
            "temp_max": round(t_max, 4),
            "rango_termico": rango,
            "humedad_relativa": round(vals["RH2M"], 4),
            "viento_dir": round(vals["WD2M"], 4) if vals["WD2M"] > -900 else "",
            "humedad_suelo": round(vals["GWETROOT"], 4) if vals["GWETROOT"] > -900 else "",
            "precipitacion": round(vals["PRECTOTCORR"], 4) if vals["PRECTOTCORR"] > -900 else "",
        })

    # Calcular temp_min_lag3 = promedio móvil de temp_min de los 3 días previos (t-1, t-2, t-3)
    for i, r in enumerate(rows):
        if i >= 3:
            lag3 = (rows[i - 1]["temp_min"] + rows[i - 2]["temp_min"] + rows[i - 3]["temp_min"]) / 3.0
        elif i > 0:
            lag3 = sum(rows[j]["temp_min"] for j in range(i)) / i
        else:
            lag3 = r["temp_min"]
        r["temp_min_lag3"] = round(lag3, 4)

    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "fecha", "temp_media", "temp_min", "temp_max", "rango_termico",
        "humedad_relativa", "temp_min_lag3", "viento_dir", "humedad_suelo", "precipitacion"
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    n_2026 = sum(1 for r in rows if r["fecha"].startswith("2026-"))
    heladas_2026 = sum(1 for r in rows if r["fecha"].startswith("2026-") and r["temp_min"] < 0.0)
    print(f"[01_descargar_clima] OK -> Guardado {OUTPUT_CSV}")
    print(f"   Total días válidos (2023-2026): {len(rows)} | Rango: {rows[0]['fecha']} a {rows[-1]['fecha']}")
    print(f"   Días válidos 2026: {n_2026} | Días con helada (<0°C) en 2026: {heladas_2026}")


if __name__ == "__main__":
    download_nasa_power()
