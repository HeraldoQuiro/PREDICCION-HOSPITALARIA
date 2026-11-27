# -*- coding: utf-8 -*-
"""
=============================================================================
MÓDULO ML: Predictor de Saturación UCI a 24 horas (Random Forest)
Universidad Nacional del Altiplano - EPIS (2026-II)
Carga el modelo Random Forest entrenado por scripts/03_evaluacion.py
(modelos/modelo_rf.pkl) usando exactamente las 16 variables sin fuga de
información (Tabla 2 del PDF) + clima real NASA POWER 2023-2026 + feriados PE.
=============================================================================
"""

import csv as csv_mod
import os
import sys
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from config import Config
from ml.mock_predictor import calculate_hospital_forecast

CLIMA_CSV_PATH = APP_ROOT.parent / "datos" / "clima_puno_nasa_power_2023_2026.csv"
CONSOLIDATED_CSV_PATH = APP_ROOT.parent / "datos" / "dataset_uci_puno_consolidado_2023_2026.csv"

FEATURES_16_PDF = [
    "establecimiento_id",
    "tipo_uci_id",
    "dia_semana",
    "es_fin_de_semana",
    "mes",
    "es_feriado",
    "temp_min_ayer",
    "temp_max_ayer",
    "rango_termico_ayer",
    "humedad_relativa_ayer",
    "temp_min_lag3",
    "ocupacion_ayer",
    "ocupacion_hace_2_dias",
    "ocupacion_hace_7_dias",
    "ingresos_ayer",
    "egresos_ayer",
]

DEFAULT_CODE_TO_ID = {
    3299: 0,   # CARLOS MONJE MEDRANO
    10815: 1,  # CLINICA ADVENTISTA AMERICANA DE JULIACA
    11978: 2,  # CLINICA MONTE SINAI JULIACA
    3251: 3,   # HOSPITAL REGIONAL MANUEL NUÑEZ BUTRON
    31179: 4,  # HOSPITAL SAN MARTIN DE PORRES
}


def _load_clima_lookup():
    """Carga el clima real NASA POWER indexado por fecha ISO (YYYY-MM-DD)."""
    lookup = {}
    if CLIMA_CSV_PATH.exists():
        try:
            with open(CLIMA_CSV_PATH, "r", encoding="utf-8-sig") as f:
                for row in csv_mod.DictReader(f):
                    lookup[row["fecha"].strip()] = {
                        "temp_min": float(row["temp_min"]),
                        "temp_max": float(row["temp_max"]),
                        "rango_termico": float(row["rango_termico"]),
                        "humedad_relativa": float(row["humedad_relativa"]),
                        "temp_min_lag3": float(row["temp_min_lag3"]),
                    }
        except Exception:
            pass
    return lookup


def _is_peru_holiday(dt_obj):
    try:
        import holidays
        pe_h = holidays.PE(years=[dt_obj.year])
        return 1 if dt_obj.date() in pe_h else 0
    except Exception:
        # Fallback con feriados fijos principales del Perú
        fixed = {(1, 1), (5, 1), (6, 29), (7, 28), (7, 29), (8, 6), (8, 30), (10, 8), (11, 1), (12, 8), (12, 9), (12, 25)}
        return 1 if (dt_obj.month, dt_obj.day) in fixed else 0


class UCIPredictor:
    """
    Carga y ejecuta el modelo Random Forest entrenado (modelos/modelo_rf.pkl)
    usando el esquema exacto de 16 predictores sin fuga del PDF.
    """

    def __init__(self, model_path=None):
        self.model_path = model_path or Config.MODEL_PATH
        self.model = None
        self.meta = {}
        self.code_to_id = dict(DEFAULT_CODE_TO_ID)
        self.is_loaded = False
        self.feature_names = list(FEATURES_16_PDF)
        self.clima_lookup = _load_clima_lookup()
        self._load_model()

    def _load_model(self):
        if self.model_path and os.path.exists(self.model_path):
            try:
                import joblib
                loaded = joblib.load(self.model_path)
                if isinstance(loaded, dict) and "model" in loaded:
                    self.model = loaded["model"]
                    self.meta = loaded
                    if "code_to_id" in loaded:
                        self.code_to_id = {int(k): int(v) for k, v in loaded["code_to_id"].items()}
                    if "features_16" in loaded:
                        self.feature_names = list(loaded["features_16"])
                else:
                    self.model = loaded
                    self.meta = {}
                self.is_loaded = True
                print(f"[ML Predictor] Modelo cargado exitosamente desde: {self.model_path}")
            except Exception as e:
                print(f"[ML Predictor] Aviso: No se pudo cargar el archivo .pkl ({e}). Usando modo calibrado.")
                self.model = None
                self.is_loaded = False
        else:
            self.model = None
            self.is_loaded = False

    def _get_clima_for_date(self, date_str, month):
        """Obtiene el clima real NASA POWER para date_str o la fecha previa más cercana."""
        if date_str in self.clima_lookup:
            return self.clima_lookup[date_str]
        if self.clima_lookup:
            # Buscar la fecha disponible más reciente <= date_str
            prev_dates = [d for d in self.clima_lookup.keys() if d <= date_str]
            if prev_dates:
                return self.clima_lookup[max(prev_dates)]
        # Respaldo estacional Puno si aún no existe el CSV de NASA POWER
        if 5 <= month <= 10:
            return {"temp_min": 0.6, "temp_max": 15.2, "rango_termico": 14.6, "humedad_relativa": 48.5, "temp_min_lag3": 0.6}
        return {"temp_min": 4.5, "temp_max": 15.3, "rango_termico": 10.8, "humedad_relativa": 68.5, "temp_min_lag3": 4.5}

    def predict_hospital(self, hospital_info, recent_records):
        """Genera la predicción de saturación a 24 horas para un hospital específico."""
        if not self.is_loaded and os.path.exists(self.model_path):
            self._load_model()

        if self.is_loaded and self.model is not None and len(recent_records) >= 2:
            try:
                return self._predict_with_model(hospital_info, recent_records)
            except Exception as e:
                print(f"[ML Predictor] Error en inferencia del modelo ({e}). Usando mock_predictor fallback.")
                return calculate_hospital_forecast(recent_records, hospital_info)
        return calculate_hospital_forecast(recent_records, hospital_info)

    def _predict_with_model(self, hospital_info, recent_records):
        """Ejecuta inferencia con las 16 variables exactas de la Tabla 2 del PDF."""
        import numpy as np

        pcts = [float(r["porcentaje_ocupacion"]) for r in recent_records[:7]]
        camas_ocup = [int(r["camas_ocupadas_uci"]) for r in recent_records[:7]]
        tot = int(recent_records[0]["camas_uci_tot"] or hospital_info["camas_uci_tot"] or 1)
        codigo = int(hospital_info["codigo"])

        last_date_str = str(recent_records[0]["fecha"])
        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        next_date = last_date + timedelta(days=1)

        # Identificación (2)
        estab_id = self.code_to_id.get(codigo, 0)
        tipo_uci_id = 0

        # Calendario del día t (4)
        dia_semana = next_date.weekday()
        es_fin_semana = 1 if dia_semana >= 5 else 0
        mes = next_date.month
        es_feriado = _is_peru_holiday(next_date)

        # Clima hasta t-1 (5) — NASA POWER real
        clima_ayer = self._get_clima_for_date(last_date_str, last_date.month)
        temp_min_ayer = clima_ayer["temp_min"]
        temp_max_ayer = clima_ayer["temp_max"]
        rango_termico_ayer = clima_ayer["rango_termico"]
        humedad_relativa_ayer = clima_ayer["humedad_relativa"]
        temp_min_lag3 = clima_ayer["temp_min_lag3"]

        # Ocupación (%) y flujo hasta t-1 (5) — coincide exactamente con 03_evaluacion.py
        ocup_ayer_camas = camas_ocup[0]
        ocup_hace_2_camas = camas_ocup[1] if len(camas_ocup) >= 2 else camas_ocup[0]
        ocup_ayer = pcts[0]
        ocup_hace_2 = pcts[1] if len(pcts) >= 2 else pcts[0]
        ocup_hace_7 = pcts[6] if len(pcts) >= 7 else pcts[-1]
        diff_ayer = ocup_ayer_camas - ocup_hace_2_camas
        ingresos_ayer = max(0, diff_ayer)
        egresos_ayer = max(0, -diff_ayer)

        # Vector exacto de 16 features (Tabla 2 del PDF)
        X = np.array([[
            estab_id, tipo_uci_id,
            dia_semana, es_fin_semana, mes, es_feriado,
            temp_min_ayer, temp_max_ayer, rango_termico_ayer, humedad_relativa_ayer, temp_min_lag3,
            ocup_ayer, ocup_hace_2, ocup_hace_7, ingresos_ayer, egresos_ayer
        ]], dtype=np.float64)

        probs = self.model.predict_proba(X)[0]
        prob_sat = float(probs[1]) if len(probs) > 1 else float(probs[0])
        pred_class = 1 if prob_sat >= 0.5 else 0

        lag1_pct = pcts[0]
        lag3_pct = pcts[2] if len(pcts) >= 3 else pcts[-1]
        velocidad = (lag1_pct - lag3_pct) / 2.0
        media_7d = sum(pcts) / len(pcts)
        porcentaje_pred = max(0.0, min(100.0, lag1_pct + (velocidad * 0.5)))

        if prob_sat >= 0.75:
            nivel = "Crítico"
        elif prob_sat >= 0.50:
            nivel = "Alto"
        elif prob_sat >= 0.25:
            nivel = "Moderado"
        else:
            nivel = "Bajo"

        tendencia = "ascendente" if velocidad > 3.0 else ("descendente" if velocidad < -3.0 else "estable")
        variacion_str = f"{'+' if velocidad >= 0 else ''}{velocidad:.1f}%"

        metrics_meta = self.meta.get("metrics", {})
        roc_label = metrics_meta.get("roc_auc", Config.BEST_MODEL_ROC_AUC)
        pr_label = metrics_meta.get("pr_auc", Config.BEST_MODEL_PR_AUC)

        factores = [
            f"Random Forest (16 variables sin fuga · ROC-AUC {roc_label} · PR-AUC {pr_label})",
            f"Ocupación t-1: {ocup_ayer_camas}/{tot} camas ({lag1_pct:.1f}%) | Media 7d: {media_7d:.1f}%",
            f"Clima NASA POWER t-1: Tmín {temp_min_ayer:.1f}°C · Amplitud {rango_termico_ayer:.1f}°C · HR {humedad_relativa_ayer:.0f}%",
        ]

        if nivel == "Crítico":
            rec = "ALERTA CRÍTICA 24H: Mantener vigilancia de saturación y coordinar referencias interhospitalarias."
        elif nivel == "Alto":
            rec = "ALERTA PREVENTIVA: Probabilidad elevada de saturación mañana. Revisar altas programadas y turnos."
        elif nivel == "Moderado":
            rec = "VIGILANCIA: Ocupación moderada con riesgo intermedio. Monitorear admisiones de turno nocturno."
        else:
            rec = "OPERACIÓN NORMAL: Disponibilidad de camas UCI dentro de rango seguro para las próximas 24 horas."

        return {
            "hospital_codigo": codigo,
            "hospital_nombre": hospital_info["nombre"],
            "ocupacion_actual": round(lag1_pct, 1),
            "camas_ocupadas_actual": ocup_ayer_camas,
            "camas_totales": tot,
            "probabilidad_saturacion": round(prob_sat, 3),
            "probabilidad_porcentaje": round(prob_sat * 100.0, 1),
            "porcentaje_predicho": round(porcentaje_pred, 1),
            "prediccion_clase": pred_class,
            "nivel_riesgo": nivel,
            "tendencia": tendencia,
            "variacion_esperada": variacion_str,
            "factores_clave": factores,
            "recomendacion": rec,
            "modelo_usado": f"Random Forest .pkl (ROC-AUC {roc_label})",
            "fecha_objetivo": next_date.strftime("%Y-%m-%d"),
            "fecha_prediccion": last_date_str,
        }

    def train_and_save_model(self, csv_path=None, output_path=None):
        """
        Reentrena el modelo Random Forest (RF-06) con las 16 variables exactas del PDF
        usando el dataset consolidado 2023-2026 + registros nuevos en SQLite,
        y lo guarda en modelos/modelo_rf.pkl.
        """
        import joblib
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

        target_out = output_path or Config.MODEL_PATH
        self.clima_lookup = _load_clima_lookup()

        # Usar el dataset consolidado 2023-2026 si existe; si no, construir desde CSV real
        source_csv = str(CONSOLIDATED_CSV_PATH) if CONSOLIDATED_CSV_PATH.exists() else (csv_path or Config.CSV_DATA_PATH)
        if not os.path.exists(source_csv):
            raise FileNotFoundError(f"Dataset no encontrado en: {source_csv}")

        df = pd.read_csv(source_csv, encoding="utf-8-sig")
        if "fecha" not in df.columns and "FECHACORTE" in df.columns:
            df = df.rename(columns={"FECHACORTE": "fecha", "CODIGO": "codigo", "NOMBRE": "establecimiento"})

        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.sort_values(["establecimiento", "fecha"]).reset_index(drop=True)

        # Fusionar registros nuevos ingresados desde la app web en SQLite (si son posteriores)
        if os.path.exists(Config.DATABASE_PATH) and "codigo" in df.columns:
            try:
                conn = sqlite3.connect(Config.DATABASE_PATH)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("""
                    SELECT r.hospital_codigo AS codigo, h.nombre AS establecimiento,
                           r.fecha, r.camas_uci_tot AS capacidad_camas_uci,
                           r.camas_ocupadas_uci, r.porcentaje_ocupacion, r.estado_saturacion
                    FROM registros_diarios r
                    JOIN hospitales h ON r.hospital_codigo = h.codigo
                """)
                db_rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                if db_rows:
                    max_csv_date = df["fecha"].max()
                    new_rows = [r for r in db_rows if pd.Timestamp(r["fecha"]) > max_csv_date]
                    if new_rows:
                        df_new = pd.DataFrame(new_rows)
                        df_new["fecha"] = pd.to_datetime(df_new["fecha"])
                        df_new["region"] = "PUNO"
                        df_new["tipo_uci"] = "UCI total"
                        df_new["dia_semana"] = df_new["fecha"].dt.weekday
                        df_new["es_fin_de_semana"] = (df_new["dia_semana"] >= 5).astype(int)
                        df_new["mes"] = df_new["fecha"].dt.month
                        df_new["es_feriado"] = df_new["fecha"].apply(_is_peru_holiday)
                        for col in ("temp_min", "temp_max", "rango_termico", "humedad_relativa", "temp_min_lag3"):
                            df_new[col] = df_new["fecha"].apply(
                                lambda dt: self._get_clima_for_date(dt.strftime("%Y-%m-%d"), dt.month)[col]
                            )
                        df_new["ingresos_uci_dia"] = 0
                        df_new["egresos_uci_dia"] = 0
                        df = pd.concat([df, df_new], ignore_index=True)
                        df = df.sort_values(["establecimiento", "fecha"]).drop_duplicates(
                            subset=["codigo", "fecha"], keep="last"
                        ).reset_index(drop=True)
            except Exception:
                pass

        hosp_names = sorted(df["establecimiento"].unique().tolist())
        hosp_to_id = {name: i for i, name in enumerate(hosp_names)}
        code_to_id = (
            df.drop_duplicates("codigo").set_index("codigo")["establecimiento"].map(hosp_to_id).to_dict()
            if "codigo" in df.columns
            else dict(DEFAULT_CODE_TO_ID)
        )
        df["establecimiento_id"] = df["establecimiento"].map(hosp_to_id).astype(int)
        df["tipo_uci_id"] = 0

        g = df.groupby("establecimiento", sort=False)
        df["temp_min_ayer"] = g["temp_min"].shift(1)
        df["temp_max_ayer"] = g["temp_max"].shift(1)
        df["rango_termico_ayer"] = g["rango_termico"].shift(1)
        df["humedad_relativa_ayer"] = g["humedad_relativa"].shift(1)
        df["ocupacion_ayer"] = g["porcentaje_ocupacion"].shift(1)
        df["ocupacion_hace_2_dias"] = g["porcentaje_ocupacion"].shift(2)
        df["ocupacion_hace_7_dias"] = g["porcentaje_ocupacion"].shift(7)
        df["ingresos_ayer"] = g["ingresos_uci_dia"].shift(1)
        df["egresos_ayer"] = g["egresos_uci_dia"].shift(1)

        clean_df = df.dropna(subset=FEATURES_16_PDF + ["estado_saturacion"]).copy()
        train_df = clean_df[clean_df["fecha"] <= pd.Timestamp("2026-08-31")]
        test_df = clean_df[(clean_df["fecha"] >= pd.Timestamp("2026-09-01")) & (clean_df["fecha"] <= pd.Timestamp("2026-11-03"))]

        rf_eval = RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        )
        if len(train_df) >= 50 and len(test_df) >= 20:
            rf_eval.fit(train_df[FEATURES_16_PDF].to_numpy(), train_df["estado_saturacion"].to_numpy(dtype=int))
            y_te = test_df["estado_saturacion"].to_numpy(dtype=int)
            p_te = rf_eval.predict_proba(test_df[FEATURES_16_PDF].to_numpy())[:, 1]
            roc_auc = float(roc_auc_score(y_te, p_te))
            pr_auc = float(average_precision_score(y_te, p_te))
            f1 = float(f1_score(y_te, (p_te >= 0.5).astype(int), zero_division=0))
        else:
            X_all = clean_df[FEATURES_16_PDF].to_numpy()
            y_all = clean_df["estado_saturacion"].to_numpy(dtype=int)
            rf_eval.fit(X_all, y_all)
            p_all = rf_eval.predict_proba(X_all)[:, 1]
            roc_auc = float(roc_auc_score(y_all, p_all))
            pr_auc = float(average_precision_score(y_all, p_all))
            f1 = float(f1_score(y_all, (p_all >= 0.5).astype(int), zero_division=0))

        # Modelo final reentrenado con todo el historial consolidado
        rf_full = RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=2,
            random_state=42, n_jobs=-1
        )
        rf_full.fit(clean_df[FEATURES_16_PDF].to_numpy(), clean_df["estado_saturacion"].to_numpy(dtype=int))

        bundle = {
            "model": rf_full,
            "eval_model": rf_eval,
            "features_16": FEATURES_16_PDF,
            "hosp_to_id": hosp_to_id,
            "code_to_id": {int(k): int(v) for k, v in code_to_id.items()},
            "metrics": {"roc_auc": round(roc_auc, 3), "pr_auc": round(pr_auc, 3), "f1": round(f1, 3)},
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        os.makedirs(os.path.dirname(target_out), exist_ok=True)
        joblib.dump(bundle, target_out)

        self.model = rf_full
        self.meta = bundle
        self.code_to_id = bundle["code_to_id"]
        self.is_loaded = True
        self.model_path = target_out

        return {
            "roc_auc": round(roc_auc, 3),
            "pr_auc": round(pr_auc, 3),
            "f1_score": round(f1, 3),
            "total_muestras": len(clean_df),
            "model_path": target_out,
            "trained_at": bundle["trained_at"],
        }


# Instancia singleton para uso general
predictor_service = UCIPredictor()
