# -*- coding: utf-8 -*-
"""
=============================================================================
02_simulacion.py
Simulación calibrada del historial UCI 2023-2025 + Consolidación de 19 variables
(Secciones 4.1, 4.2, 6.1 y 6.2 de Proyecto_UCI_EPIS_2026II_Puno.pdf)

Metodología estricta sin fuga de información:
- Corte de calibración: 2026-08-31 (ningún parámetro ve datos >= 2026-09-01).
- Ingresos diarios I_t ~ Poisson(lambda_t), con GLM de Poisson sobre datos reales
  hasta el corte; coeficientes beta sin significancia (p >= 0.05) se fijan en 0.
- Estancia D_i = max(1, round(Gamma(k=2, theta))) calibrada con Ley de Little
  (estancia media = ocupación media / ingresos medios hasta el corte).
- Balance diario stock-flujo (Asplin et al., 2003; Bai, 2021):
    O_t = min(C, max(0, O_{t-1} + I_t - E_t))
- Clima real NASA POWER 2023-2026 y feriados oficiales del Perú (holidays.PE()).

Salidas:
- datos/dataset_uci_puno_consolidado_2023_2026.csv (19 columnas oficiales + metadata)
- modelos/calibracion_simulador.json
=============================================================================
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import holidays
import statsmodels.api as sm

BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "datos"
MODELOS_DIR = BASE_DIR / "modelos"

UCI_CSV = DATOS_DIR / "UCI_5_HOSPITALES_PUNO_2026.csv"
CLIMA_CSV = DATOS_DIR / "clima_puno_nasa_power_2023_2026.csv"
OUT_CSV = DATOS_DIR / "dataset_uci_puno_consolidado_2023_2026.csv"
OUT_CALIB_JSON = MODELOS_DIR / "calibracion_simulador.json"

CALIB_CUTOFF = pd.Timestamp("2026-08-31")
SIM_START = pd.Timestamp("2023-01-01")
SIM_END = pd.Timestamp("2025-12-31")
GAMMA_SHAPE_K = 2.0
RANDOM_SEED = 42

# Nombres canónicos de los 5 establecimientos UCI de Puno (agrupando por CODIGO oficial)
CANONICAL_NAMES = {
    3251: "HOSPITAL REGIONAL MANUEL NUÑEZ BUTRON",
    3299: "CARLOS MONJE MEDRANO",
    10815: "CLINICA ADVENTISTA AMERICANA DE JULIACA",
    11978: "CLINICA MONTE SINAI JULIACA",
    31179: "HOSPITAL SAN MARTIN DE PORRES",
}


def load_real_2026():
    df = pd.read_csv(UCI_CSV, encoding="utf-8-sig")
    df["fecha"] = pd.to_datetime(df["FECHACORTE"])
    df["codigo"] = df["CODIGO"].astype(int)
    df["establecimiento"] = df["codigo"].map(CANONICAL_NAMES).fillna(df["NOMBRE"].str.strip())
    df["region"] = "PUNO"
    df["tipo_uci"] = "UCI total"
    df["capacidad_camas_uci"] = pd.to_numeric(df["CAMAS_UCI_TOT"], errors="coerce").astype(int)
    df["camas_ocupadas_uci"] = pd.to_numeric(df["camas_ocupadas_uci"], errors="coerce").clip(lower=0).astype(int)
    df["camas_ocupadas_uci"] = np.minimum(df["camas_ocupadas_uci"], df["capacidad_camas_uci"])

    # Resolver duplicados por (codigo, fecha) tomando el último registro del día
    df = df.sort_values(["codigo", "fecha"]).drop_duplicates(subset=["codigo", "fecha"], keep="last")
    df["porcentaje_ocupacion"] = (df["camas_ocupadas_uci"] / df["capacidad_camas_uci"]) * 100.0
    df["estado_saturacion"] = (df["porcentaje_ocupacion"] >= 85.0).astype(int)

    # Aproximar ingresos y egresos diarios reales mediante variaciones consecutivas de ocupación (Tabla 4 del PDF)
    df["ingresos_uci_dia"] = 0
    df["egresos_uci_dia"] = 0
    for cod, grp in df.groupby("codigo"):
        idx = grp.index
        diff = grp["camas_ocupadas_uci"].diff().fillna(0)
        df.loc[idx, "ingresos_uci_dia"] = np.maximum(0, diff).astype(int)
        df.loc[idx, "egresos_uci_dia"] = np.maximum(0, -diff).astype(int)

    return df


def calibrate_unit(df_unit, clima_df):
    """Calibra parámetros (lambda_0, beta_1..beta_3, estancia media) usando solo datos <= CALIB_CUTOFF."""
    calib = df_unit[df_unit["fecha"] <= CALIB_CUTOFF].copy()
    calib = calib.merge(clima_df, on="fecha", how="left")
    calib["invierno"] = calib["fecha"].dt.month.isin([6, 7, 8]).astype(int)

    capacidad_mediana = int(round(calib["capacidad_camas_uci"].median()))
    ocup_media = float(calib["camas_ocupadas_uci"].mean())
    ingresos_tot = int(calib["ingresos_uci_dia"].sum())
    ingresos_medio = float(calib["ingresos_uci_dia"].mean())

    # Estancia promedio por Ley de Little (ocupación media / ingresos medios)
    if ingresos_medio > 1e-4 and ocup_media > 0:
        estancia_media = float(np.clip(ocup_media / ingresos_medio, 1.5, 25.0))
    else:
        estancia_media = 4.5

    # Regresión GLM de Poisson para estimar beta1 (temp_min_lag3), beta2 (rango_termico), beta3 (invierno)
    beta_applied = {"beta1_temp_min_lag3": 0.0, "beta2_rango_termico": 0.0, "beta3_invierno": 0.0}
    beta_estimated = {}

    glm_data = calib.dropna(subset=["temp_min_lag3", "rango_termico", "ingresos_uci_dia"])
    if ingresos_tot >= 5 and len(glm_data) >= 30:
        try:
            X = sm.add_constant(glm_data[["temp_min_lag3", "rango_termico", "invierno"]])
            y = glm_data["ingresos_uci_dia"]
            res = sm.GLM(y, X, family=sm.families.Poisson()).fit()
            mapping = {
                "temp_min_lag3": "beta1_temp_min_lag3",
                "rango_termico": "beta2_rango_termico",
                "invierno": "beta3_invierno",
            }
            for col, bname in mapping.items():
                coef = float(res.params[col])
                pval = float(res.pvalues[col])
                beta_estimated[bname] = {"coef": round(coef, 4), "p_value": round(pval, 4)}
                # Solo se aplica si es estadísticamente significativo (p < 0.05)
                if pval < 0.05:
                    beta_applied[bname] = coef
        except Exception as e:
            beta_estimated["nota"] = f"No estimable ({e})"
    else:
        beta_estimated["nota"] = f"Ingresos insuficientes ({ingresos_tot}) para GLM Poisson"

    # Ajustar tasa base lambda_0 para reproducir simultáneamente ocupación media y tasa de saturación reales (<= corte)
    sat_real_calib = float(calib["estado_saturacion"].mean())
    lambda_0 = max(0.01, ingresos_medio)
    if ocup_media > 0:
        best_lam = lambda_0
        best_err = 1e9
        theta = estancia_media / GAMMA_SHAPE_K
        # Rango amplio alrededor de la tasa por Ley de Little (ocup_media / estancia_media)
        base_est = max(0.01, ocup_media / max(1.0, estancia_media))
        grid = np.unique(np.concatenate([
            np.linspace(max(0.005, base_est * 0.25), base_est * 2.5, 45),
            np.linspace(0.01, max(0.8, base_est * 3.0), 25),
        ]))
        for cand in grid:
            rng_cal = np.random.default_rng(RANDOM_SEED + capacidad_mediana)
            sim_occ, sim_sat = _quick_sim_stats(float(cand), capacidad_mediana, theta, rng_cal)
            occ_err = abs(sim_occ - ocup_media) / max(1.0, float(capacidad_mediana))
            sat_err = abs(sim_sat - sat_real_calib)
            err = occ_err + 1.5 * sat_err
            if err < best_err:
                best_err = err
                best_lam = float(cand)
        lambda_0 = float(best_lam)

    # Medias climáticas del periodo de calibración para centrar las covariables (exp(0)=1 en el promedio)
    mean_tmin_lag3 = float(calib["temp_min_lag3"].mean()) if calib["temp_min_lag3"].notna().any() else 2.5
    mean_rango = float(calib["rango_termico"].mean()) if calib["rango_termico"].notna().any() else 12.9

    return {
        "capacidad_mediana": capacidad_mediana,
        "dias_reales_calib": int(len(calib)),
        "ocupacion_media_real_calib": round(ocup_media, 3),
        "ingresos_medios_real_calib": round(ingresos_medio, 4),
        "lambda_0": round(lambda_0, 4),
        "estancia_media_gamma": round(estancia_media, 2),
        "gamma_k": GAMMA_SHAPE_K,
        "gamma_theta": round(estancia_media / GAMMA_SHAPE_K, 4),
        "clima_ref_means": {
            "temp_min_lag3": round(mean_tmin_lag3, 4),
            "rango_termico": round(mean_rango, 4),
        },
        "betas_aplicados": {k: round(v, 4) for k, v in beta_applied.items()},
        "betas_estimados_glm": beta_estimated,
    }


def _quick_sim_stats(lam, cap, theta, rng, n_days=600):
    """Simulación de calentamiento + equilibrio retornando (ocupación media, tasa de saturación)."""
    discharges = {}
    occ = 0
    hist_occ = []
    hist_sat = []
    for t in range(n_days):
        ing = int(rng.poisson(lam))
        eg = min(discharges.pop(t, 0), occ)
        new_occ = occ - eg + ing
        accepted = ing - max(0, new_occ - cap)
        occ = min(cap, max(0, new_occ))
        if accepted > 0:
            stays = np.maximum(1, np.round(rng.gamma(GAMMA_SHAPE_K, theta, size=accepted))).astype(int)
            for d in stays:
                discharges[t + int(d)] = discharges.get(t + int(d), 0) + 1
        if t >= 60:
            hist_occ.append(occ)
            hist_sat.append(1.0 if (occ / cap) * 100.0 >= 85.0 else 0.0)
    return float(np.mean(hist_occ)), float(np.mean(hist_sat))


def simulate_unit_2023_2025(codigo, nombre, params, clima_df, rng):
    """Simula día a día 2023-01-01 a 2025-12-31 (1,096 días) usando Asplin (2003) + Bai (2021)."""
    dates = pd.date_range(SIM_START, SIM_END, freq="D")
    clima_map = clima_df.set_index("fecha").to_dict("index")

    cap = params["capacidad_mediana"]
    lam0 = params["lambda_0"]
    b1 = params["betas_aplicados"]["beta1_temp_min_lag3"]
    b2 = params["betas_aplicados"]["beta2_rango_termico"]
    b3 = params["betas_aplicados"]["beta3_invierno"]
    theta = params["gamma_theta"]

    # Periodo de calentamiento (warm-up) de 45 días para no iniciar en cero artificial
    discharges = {}
    occ = 0
    warmup_days = 45
    for w in range(-warmup_days, 0):
        ing = int(rng.poisson(lam0))
        eg = min(discharges.pop(w, 0), occ)
        raw_occ = occ - eg + ing
        accepted = ing - max(0, raw_occ - cap)
        occ = min(cap, max(0, raw_occ))
        if accepted > 0:
            stays = np.maximum(1, np.round(rng.gamma(GAMMA_SHAPE_K, theta, size=accepted))).astype(int)
            for d in stays:
                discharges[w + int(d)] = discharges.get(w + int(d), 0) + 1

    mean_tmin = params.get("clima_ref_means", {}).get("temp_min_lag3", 2.5)
    mean_rango = params.get("clima_ref_means", {}).get("rango_termico", 12.9)

    rows = []
    for t, dt in enumerate(dates):
        cinfo = clima_map.get(dt, {})
        tmin_lag3 = float(cinfo.get("temp_min_lag3", mean_tmin))
        rango = float(cinfo.get("rango_termico", mean_rango))
        inv = 1 if dt.month in (6, 7, 8) else 0

        lam_t = lam0 * np.exp(b1 * (tmin_lag3 - mean_tmin) + b2 * (rango - mean_rango) + b3 * inv)
        lam_t = float(np.clip(lam_t, 0.001, cap * 2.0))

        ing = int(rng.poisson(lam_t))
        eg = min(discharges.pop(t, 0), occ)
        raw_occ = occ - eg + ing
        accepted = ing - max(0, raw_occ - cap)
        occ = min(cap, max(0, raw_occ))

        if accepted > 0:
            stays = np.maximum(1, np.round(rng.gamma(GAMMA_SHAPE_K, theta, size=accepted))).astype(int)
            for d in stays:
                discharges[t + int(d)] = discharges.get(t + int(d), 0) + 1

        pct = (occ / cap) * 100.0 if cap > 0 else 0.0
        sat = 1 if pct >= 85.0 else 0
        rows.append({
            "fecha": dt,
            "codigo": codigo,
            "region": "PUNO",
            "establecimiento": nombre,
            "tipo_uci": "UCI total",
            "capacidad_camas_uci": cap,
            "ingresos_uci_dia": ing,
            "egresos_uci_dia": eg,
            "camas_ocupadas_uci": occ,
            "porcentaje_ocupacion": round(pct, 2),
            "estado_saturacion": sat,
            "origen_datos": "simulado",
        })
    return pd.DataFrame(rows)


def main():
    print("[02_simulacion] Cargando datos reales 2026 y clima real NASA POWER 2023-2026...")
    df_real = load_real_2026()
    df_real["origen_datos"] = "real"

    clima = pd.read_csv(CLIMA_CSV, encoding="utf-8-sig")
    clima["fecha"] = pd.to_datetime(clima["fecha"])

    rng = np.random.default_rng(RANDOM_SEED)
    sim_dfs = []
    calibracion_report = {}

    for cod in sorted(CANONICAL_NAMES.keys()):
        nombre = CANONICAL_NAMES[cod]
        df_unit = df_real[df_real["codigo"] == cod].copy()
        params = calibrate_unit(df_unit, clima)
        df_sim_unit = simulate_unit_2023_2025(cod, nombre, params, clima, rng)

        sat_real_pct = round(float(df_unit["estado_saturacion"].mean() * 100.0), 1)
        sat_sim_pct = round(float(df_sim_unit["estado_saturacion"].mean() * 100.0), 1)
        params["dias_reales_2026"] = int(len(df_unit))
        params["dias_simulados_2023_2025"] = int(len(df_sim_unit))
        params["pct_saturados_real_2026"] = sat_real_pct
        params["pct_saturados_simulado"] = sat_sim_pct
        calibracion_report[nombre] = params

        print(
            f"  - {nombre} (C={params['capacidad_mediana']}): "
            f"λ0={params['lambda_0']} | estancia={params['estancia_media_gamma']}d | "
            f"sat real={sat_real_pct}% vs sim={sat_sim_pct}%"
        )
        sim_dfs.append(df_sim_unit)

    df_sim_all = pd.concat(sim_dfs, ignore_index=True)

    # Unir simulado (2023-2025) + real (2026)
    base_cols = [
        "fecha", "codigo", "region", "establecimiento", "tipo_uci",
        "capacidad_camas_uci", "ingresos_uci_dia", "egresos_uci_dia",
        "camas_ocupadas_uci", "porcentaje_ocupacion", "estado_saturacion", "origen_datos"
    ]
    df_all = pd.concat([df_sim_all[base_cols], df_real[base_cols]], ignore_index=True)
    df_all = df_all.sort_values(["establecimiento", "fecha"]).reset_index(drop=True)

    # Bloque Calendario + Feriados Perú (holidays.PE)
    pe_holidays = holidays.PE(years=[2023, 2024, 2025, 2026])
    df_all["dia_semana"] = df_all["fecha"].dt.day_of_week
    df_all["es_fin_de_semana"] = (df_all["dia_semana"] >= 5).astype(int)
    df_all["mes"] = df_all["fecha"].dt.month
    df_all["es_feriado"] = df_all["fecha"].dt.date.apply(lambda d: 1 if d in pe_holidays else 0)

    # Bloque Clima real NASA POWER (2023-2026)
    clima_cols = ["fecha", "temp_min", "temp_max", "rango_termico", "humedad_relativa", "temp_min_lag3"]
    df_all = df_all.merge(clima[clima_cols], on="fecha", how="left")
    # Forward-fill solo si los últimos 1-2 días de 2026 aún no se publican en NASA POWER
    for c in ["temp_min", "temp_max", "rango_termico", "humedad_relativa", "temp_min_lag3"]:
        df_all[c] = df_all.groupby("establecimiento")[c].ffill().bfill()

    # Orden oficial exacto de las 19 columnas de la Tabla 1 del PDF (+ codigo y origen_datos para trazabilidad)
    ordered_19_cols = [
        "fecha", "region", "establecimiento", "tipo_uci",
        "dia_semana", "es_fin_de_semana", "mes", "es_feriado",
        "temp_min", "temp_max", "rango_termico", "humedad_relativa", "temp_min_lag3",
        "capacidad_camas_uci", "ingresos_uci_dia", "egresos_uci_dia", "camas_ocupadas_uci",
        "porcentaje_ocupacion", "estado_saturacion",
        "codigo", "origen_datos"
    ]
    df_all = df_all[ordered_19_cols]
    df_all["fecha"] = df_all["fecha"].dt.strftime("%Y-%m-%d")

    df_all.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_CALIB_JSON, "w", encoding="utf-8") as f:
        json.dump(calibracion_report, f, indent=2, ensure_ascii=False)

    print(f"\n[02_simulacion] OK -> Dataset consolidado guardado en: {OUT_CSV}")
    print(f"   Total filas: {len(df_all)} (simulado: {len(df_sim_all)}, real 2026: {len(df_real)})")
    print(f"   Calibración guardada en: {OUT_CALIB_JSON}")


if __name__ == "__main__":
    main()
