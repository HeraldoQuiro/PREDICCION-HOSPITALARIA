# -*- coding: utf-8 -*-
"""
=============================================================================
03_evaluacion.py
Ingeniería de 16 variables sin fuga + Entrenamiento y evaluación temporal
de los 9 modelos del proyecto (Secciones 4.4, 4.5 y 6.3 del PDF)

Modelos evaluados sobre prueba real (2026-09-01 a 2026-11-03):
  1. Persistencia (estado de ayer)
  2. Ingenuo semanal (hace 7 días)
  3. Perfil de calendario (mes x dia_semana)
  4. Regresión logística
  5. Random Forest
  6. XGBoost
  7. CatBoost
  8. LSTM (ventana t-7..t-1, BPTT + Adam)
  9. GRU  (ventana t-7..t-1, BPTT + Adam)
  + Variante complementaria de regresión (% ocupación): CatBoostRegressor vs Persistencia

Salidas guardadas en 05_modelos/:
  - modelo_rf.pkl, modelo_xgb.pkl, modelo_catboost.pkl, modelo_logreg.pkl,
    modelo_lstm.pkl, modelo_gru.pkl, modelo_regresion_catboost.pkl
  - tabla_resultados_modelos.csv
  - metricas_evaluacion.json
=============================================================================
"""

import json
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier
from catboost import CatBoostClassifier, CatBoostRegressor

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "01_datos"
MODELOS_DIR = BASE_DIR / "05_modelos"
DATASET_CSV = DATOS_DIR / "dataset_uci_puno_consolidado_2023_2026.csv"

TRAIN_END = pd.Timestamp("2026-08-31")
TEST_START = pd.Timestamp("2026-09-01")
TEST_END = pd.Timestamp("2026-11-03")
SEED = 42

# 16 predictores exactos de la Tabla 2 del PDF (cero fuga de información)
FEATURES_16 = [
    # Identificación (2)
    "establecimiento_id",
    "tipo_uci_id",
    # Calendario del día t (4)
    "dia_semana",
    "es_fin_de_semana",
    "mes",
    "es_feriado",
    # Clima hasta t-1 (5)
    "temp_min_ayer",
    "temp_max_ayer",
    "rango_termico_ayer",
    "humedad_relativa_ayer",
    "temp_min_lag3",
    # Ocupación y flujo (5)
    "ocupacion_ayer",
    "ocupacion_hace_2_dias",
    "ocupacion_hace_7_dias",
    "ingresos_ayer",
    "egresos_ayer",
]

FEATURE_GROUPS = {
    "Ocupación previa (t-1, t-2, t-7)": [
        "ocupacion_ayer",
        "ocupacion_hace_2_dias",
        "ocupacion_hace_7_dias",
    ],
    "Clima hasta t-1 (temp_min, temp_max, humedad)": [
        "temp_min_ayer",
        "temp_max_ayer",
        "rango_termico_ayer",
        "humedad_relativa_ayer",
        "temp_min_lag3",
    ],
    "Flujo (ingresos/egresos t-1)": ["ingresos_ayer", "egresos_ayer"],
    "Calendario (día t)": ["dia_semana", "es_fin_de_semana", "mes", "es_feriado"],
    "Identificación (hospital, tipo UCI)": ["establecimiento_id", "tipo_uci_id"],
}

# Variables paso-a-paso para la secuencia temporal t-7..t-1 de LSTM y GRU
SEQ_FEATURES = [
    "porcentaje_ocupacion",
    "camas_ocupadas_uci",
    "ingresos_uci_dia",
    "egresos_uci_dia",
    "temp_min",
    "temp_max",
    "rango_termico",
    "humedad_relativa",
    "dia_semana",
    "mes",
    "establecimiento_id",
]


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


class NumpyLSTMClassifier:
    """Red recurrente LSTM real (compuertas i, f, g, o) entrenada con BPTT + Adam en NumPy."""

    def __init__(self, input_dim, hidden_dim=20, lr=0.015, epochs=25, batch_size=64, seed=42):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.mean_ = None
        self.std_ = None
        self._init_weights()

    def _init_weights(self):
        rng = np.random.default_rng(self.seed)
        d, h = self.input_dim, self.hidden_dim
        scale = 1.0 / np.sqrt(d + h)
        self.params = {
            "Wx": rng.normal(0, scale, (d, 4 * h)),
            "Wh": rng.normal(0, scale, (h, 4 * h)),
            "b": np.zeros(4 * h),
            "Wy": rng.normal(0, 1.0 / np.sqrt(h), (h, 1)),
            "by": np.zeros(1),
        }
        # Bias positivo en forget gate para facilitar memoria temporal
        self.params["b"][h : 2 * h] = 1.0

    def _forward(self, X):
        B, T, _ = X.shape
        h_dim = self.hidden_dim
        h = np.zeros((B, h_dim))
        c = np.zeros((B, h_dim))
        cache = []
        Wx, Wh, b = self.params["Wx"], self.params["Wh"], self.params["b"]
        for t in range(T):
            xt = X[:, t, :]
            gates = xt @ Wx + h @ Wh + b
            i = _sigmoid(gates[:, 0:h_dim])
            f = _sigmoid(gates[:, h_dim : 2 * h_dim])
            g = np.tanh(gates[:, 2 * h_dim : 3 * h_dim])
            o = _sigmoid(gates[:, 3 * h_dim : 4 * h_dim])
            c_next = f * c + i * g
            tanh_c = np.tanh(c_next)
            h_next = o * tanh_c
            cache.append((xt, h, c, i, f, g, o, c_next, tanh_c))
            h, c = h_next, c_next
        logits = h @ self.params["Wy"] + self.params["by"]
        probs = _sigmoid(logits).ravel()
        return probs, h, cache

    def fit(self, X_seq, y):
        X = np.asarray(X_seq, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mean_ = X.mean(axis=(0, 1), keepdims=True)
        self.std_ = np.where(X.std(axis=(0, 1), keepdims=True) > 1e-8, X.std(axis=(0, 1), keepdims=True), 1.0)
        Xn = (X - self.mean_) / self.std_

        n = len(y)
        pos = max(1.0, float(y.sum()))
        neg = max(1.0, float(n - pos))
        pos_w = neg / pos

        m = {k: np.zeros_like(v) for k, v in self.params.items()}
        v = {k: np.zeros_like(val) for k, val in self.params.items()}
        step = 0
        rng = np.random.default_rng(self.seed)
        h_dim = self.hidden_dim

        for _ in range(self.epochs):
            perm = rng.permutation(n)
            for start in range(0, n, self.batch_size):
                idx = perm[start : start + self.batch_size]
                xb, yb = Xn[idx], y[idx]
                B = len(yb)
                probs, h_last, cache = self._forward(xb)

                # BCE ponderada
                sw = np.where(yb == 1.0, pos_w, 1.0)
                dlogits = ((probs - yb) * sw / B)[:, None]

                grads = {k: np.zeros_like(val) for k, val in self.params.items()}
                grads["Wy"] = h_last.T @ dlogits
                grads["by"] = dlogits.sum(axis=0)
                dh = dlogits @ self.params["Wy"].T
                dc = np.zeros_like(dh)

                for t in reversed(range(xb.shape[1])):
                    xt, h_prev, c_prev, i, f, g, o, c_next, tanh_c = cache[t]
                    do = dh * tanh_c
                    dc_tot = dc + dh * o * (1.0 - tanh_c ** 2)
                    df = dc_tot * c_prev
                    di = dc_tot * g
                    dg = dc_tot * i

                    dgates = np.concatenate(
                        [
                            di * i * (1.0 - i),
                            df * f * (1.0 - f),
                            dg * (1.0 - g ** 2),
                            do * o * (1.0 - o),
                        ],
                        axis=1,
                    )
                    grads["Wx"] += xt.T @ dgates
                    grads["Wh"] += h_prev.T @ dgates
                    grads["b"] += dgates.sum(axis=0)
                    dh = dgates @ self.params["Wh"].T
                    dc = dc_tot * f

                # Gradient clipping + Adam
                step += 1
                for k in self.params:
                    gk = np.clip(grads[k], -5.0, 5.0)
                    m[k] = 0.9 * m[k] + 0.1 * gk
                    v[k] = 0.999 * v[k] + 0.001 * (gk ** 2)
                    m_hat = m[k] / (1.0 - 0.9 ** step)
                    v_hat = v[k] / (1.0 - 0.999 ** step)
                    self.params[k] -= self.lr * m_hat / (np.sqrt(v_hat) + 1e-8)
        return self

    def predict_proba(self, X_seq):
        X = (np.asarray(X_seq, dtype=np.float64) - self.mean_) / self.std_
        p1, _, _ = self._forward(X)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X_seq):
        return (self.predict_proba(X_seq)[:, 1] >= 0.5).astype(int)


class NumpyGRUClassifier:
    """Red recurrente GRU real (compuertas z, r, h_tilde) entrenada con BPTT + Adam en NumPy."""

    def __init__(self, input_dim, hidden_dim=20, lr=0.015, epochs=25, batch_size=64, seed=42):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.seed = seed
        self.mean_ = None
        self.std_ = None
        self._init_weights()

    def _init_weights(self):
        rng = np.random.default_rng(self.seed + 1)
        d, h = self.input_dim, self.hidden_dim
        sc = 1.0 / np.sqrt(d + h)
        self.params = {
            "Wxz": rng.normal(0, sc, (d, h)),
            "Whz": rng.normal(0, sc, (h, h)),
            "bz": np.zeros(h),
            "Wxr": rng.normal(0, sc, (d, h)),
            "Whr": rng.normal(0, sc, (h, h)),
            "br": np.zeros(h),
            "Wxh": rng.normal(0, sc, (d, h)),
            "Whh": rng.normal(0, sc, (h, h)),
            "bh": np.zeros(h),
            "Wy": rng.normal(0, 1.0 / np.sqrt(h), (h, 1)),
            "by": np.zeros(1),
        }

    def _forward(self, X):
        B, T, _ = X.shape
        h = np.zeros((B, self.hidden_dim))
        p = self.params
        cache = []
        for t in range(T):
            xt = X[:, t, :]
            z = _sigmoid(xt @ p["Wxz"] + h @ p["Whz"] + p["bz"])
            r = _sigmoid(xt @ p["Wxr"] + h @ p["Whr"] + p["br"])
            rh = r * h
            h_tilde = np.tanh(xt @ p["Wxh"] + rh @ p["Whh"] + p["bh"])
            h_next = (1.0 - z) * h + z * h_tilde
            cache.append((xt, h, z, r, rh, h_tilde))
            h = h_next
        logits = h @ p["Wy"] + p["by"]
        probs = _sigmoid(logits).ravel()
        return probs, h, cache

    def fit(self, X_seq, y):
        X = np.asarray(X_seq, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        self.mean_ = X.mean(axis=(0, 1), keepdims=True)
        self.std_ = np.where(X.std(axis=(0, 1), keepdims=True) > 1e-8, X.std(axis=(0, 1), keepdims=True), 1.0)
        Xn = (X - self.mean_) / self.std_

        n = len(y)
        pos = max(1.0, float(y.sum()))
        neg = max(1.0, float(n - pos))
        pos_w = neg / pos

        m = {k: np.zeros_like(v) for k, v in self.params.items()}
        v = {k: np.zeros_like(val) for k, val in self.params.items()}
        step = 0
        rng = np.random.default_rng(self.seed + 1)

        for _ in range(self.epochs):
            perm = rng.permutation(n)
            for start in range(0, n, self.batch_size):
                idx = perm[start : start + self.batch_size]
                xb, yb = Xn[idx], y[idx]
                B = len(yb)
                probs, h_last, cache = self._forward(xb)

                sw = np.where(yb == 1.0, pos_w, 1.0)
                dlogits = ((probs - yb) * sw / B)[:, None]

                grads = {k: np.zeros_like(val) for k, val in self.params.items()}
                grads["Wy"] = h_last.T @ dlogits
                grads["by"] = dlogits.sum(axis=0)
                dh = dlogits @ self.params["Wy"].T
                p = self.params

                for t in reversed(range(xb.shape[1])):
                    xt, h_prev, z, r, rh, h_tilde = cache[t]
                    dz = dh * (h_tilde - h_prev) * z * (1.0 - z)
                    dh_tilde = dh * z * (1.0 - h_tilde ** 2)
                    drh = dh_tilde @ p["Whh"].T
                    dr = drh * h_prev * r * (1.0 - r)

                    grads["Wxz"] += xt.T @ dz
                    grads["Whz"] += h_prev.T @ dz
                    grads["bz"] += dz.sum(axis=0)
                    grads["Wxr"] += xt.T @ dr
                    grads["Whr"] += h_prev.T @ dr
                    grads["br"] += dr.sum(axis=0)
                    grads["Wxh"] += xt.T @ dh_tilde
                    grads["Whh"] += rh.T @ dh_tilde
                    grads["bh"] += dh_tilde.sum(axis=0)

                    dh = dh * (1.0 - z) + dz @ p["Whz"].T + dr @ p["Whr"].T + drh * r

                step += 1
                for k in self.params:
                    gk = np.clip(grads[k], -5.0, 5.0)
                    m[k] = 0.9 * m[k] + 0.1 * gk
                    v[k] = 0.999 * v[k] + 0.001 * (gk ** 2)
                    m_hat = m[k] / (1.0 - 0.9 ** step)
                    v_hat = v[k] / (1.0 - 0.999 ** step)
                    self.params[k] -= self.lr * m_hat / (np.sqrt(v_hat) + 1e-8)
        return self

    def predict_proba(self, X_seq):
        X = (np.asarray(X_seq, dtype=np.float64) - self.mean_) / self.std_
        p1, _, _ = self._forward(X)
        return np.column_stack([1.0 - p1, p1])

    def predict(self, X_seq):
        return (self.predict_proba(X_seq)[:, 1] >= 0.5).astype(int)


def build_feature_table(df):
    """Construye exactamente las 16 variables predictoras sin fuga (Tabla 2 del PDF)."""
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["establecimiento", "fecha"]).reset_index(drop=True)

    # Codificación numérica determinística de establecimiento y tipo_uci
    hosp_names = sorted(df["establecimiento"].unique().tolist())
    hosp_to_id = {name: i for i, name in enumerate(hosp_names)}
    code_to_id = (
        df.drop_duplicates("codigo")
        .set_index("codigo")["establecimiento"]
        .map(hosp_to_id)
        .to_dict()
    )
    df["establecimiento_id"] = df["establecimiento"].map(hosp_to_id).astype(int)
    df["tipo_uci_id"] = 0  # "UCI total"

    g = df.groupby("establecimiento", sort=False)

    # Clima hasta t-1 (sin incluir clima del día t)
    df["temp_min_ayer"] = g["temp_min"].shift(1)
    df["temp_max_ayer"] = g["temp_max"].shift(1)
    df["rango_termico_ayer"] = g["rango_termico"].shift(1)
    df["humedad_relativa_ayer"] = g["humedad_relativa"].shift(1)
    # temp_min_lag3 ya es promedio de t-1..t-3 en 01_descargar_clima.py

    # Ocupación (%) y flujo conocidos al cierre de t-1 (invariante ante cambios de capacidad instalada)
    df["ocupacion_ayer"] = g["porcentaje_ocupacion"].shift(1)
    df["ocupacion_hace_2_dias"] = g["porcentaje_ocupacion"].shift(2)
    df["ocupacion_hace_7_dias"] = g["porcentaje_ocupacion"].shift(7)
    df["ingresos_ayer"] = g["ingresos_uci_dia"].shift(1)
    df["egresos_ayer"] = g["egresos_uci_dia"].shift(1)

    # Auxiliares para baselines y variante de regresión
    df["sat_ayer"] = g["estado_saturacion"].shift(1)
    df["sat_hace_7"] = g["estado_saturacion"].shift(7)
    df["pct_ayer"] = g["porcentaje_ocupacion"].shift(1)

    # Construir secuencias t-7..t-1 para LSTM y GRU alineadas por índice
    seq_tensor = np.full((len(df), 7, len(SEQ_FEATURES)), np.nan, dtype=np.float64)
    for _, grp in df.groupby("establecimiento", sort=False):
        idxs = grp.index.to_numpy()
        vals = grp[SEQ_FEATURES].to_numpy(dtype=np.float64)
        for pos in range(7, len(idxs)):
            seq_tensor[idxs[pos]] = vals[pos - 7 : pos]

    valid_mask = df[FEATURES_16 + ["estado_saturacion", "sat_ayer", "sat_hace_7", "pct_ayer"]].notna().all(axis=1)
    valid_mask &= ~np.isnan(seq_tensor).any(axis=(1, 2))

    df_valid = df.loc[valid_mask].reset_index(drop=True)
    seq_valid = seq_tensor[valid_mask.to_numpy()]

    return df_valid, seq_valid, hosp_to_id, code_to_id


def evaluate_predictions(name, y_true, y_prob, y_pred=None):
    if y_pred is None:
        y_pred = (y_prob >= 0.5).astype(int)
    return {
        "modelo": name,
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        "sensibilidad": round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 3),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 3),
    }


def main():
    print("[03_evaluacion] Cargando dataset consolidado 2023-2026...")
    raw_df = pd.read_csv(DATASET_CSV, encoding="utf-8-sig")
    df, seq_all, hosp_to_id, code_to_id = build_feature_table(raw_df)

    train_mask = (df["fecha"] <= TRAIN_END).to_numpy()
    test_mask = ((df["fecha"] >= TEST_START) & (df["fecha"] <= TEST_END) & (df["origen_datos"] == "real")).to_numpy()

    df_train = df.loc[train_mask].reset_index(drop=True)
    df_test = df.loc[test_mask].reset_index(drop=True)
    X_train = df_train[FEATURES_16].to_numpy(dtype=np.float64)
    y_train = df_train["estado_saturacion"].to_numpy(dtype=int)
    X_test = df_test[FEATURES_16].to_numpy(dtype=np.float64)
    y_test = df_test["estado_saturacion"].to_numpy(dtype=int)

    seq_train = seq_all[train_mask]
    seq_test = seq_all[test_mask]

    print(
        f"   Entrenamiento: {len(df_train)} unidad-días (hasta {TRAIN_END.date()}) | "
        f"Prueba real: {len(df_test)} unidad-días ({TEST_START.date()}..{TEST_END.date()}), "
        f"saturados: {int(y_test.sum())} ({y_test.mean()*100:.1f}%)"
    )

    results = []

    # 1. Persistencia (estado de ayer)
    p_pers = df_test["sat_ayer"].to_numpy(dtype=float)
    results.append(evaluate_predictions("Persistencia (estado de ayer)", y_test, p_pers, p_pers.astype(int)))

    # 2. Ingenuo semanal (hace 7 días)
    p_sem = df_test["sat_hace_7"].to_numpy(dtype=float)
    results.append(evaluate_predictions("Ingenuo semanal (hace 7 días)", y_test, p_sem, p_sem.astype(int)))

    # 3. Perfil de calendario (mes x dia_semana en entrenamiento)
    cal_rates = df_train.groupby(["mes", "dia_semana"])["estado_saturacion"].mean().to_dict()
    global_rate = float(y_train.mean())
    p_cal = np.array(
        [cal_rates.get((int(m), int(d)), global_rate) for m, d in zip(df_test["mes"], df_test["dia_semana"])]
    )
    results.append(evaluate_predictions("Perfil de calendario (mes × día)", y_test, p_cal))

    # 4. Regresión logística (probabilidades calibradas sin distorsión de prior)
    print("   Entrenando Regresión logística...")
    logreg = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=SEED)),
    ])
    logreg.fit(X_train, y_train)
    p_lr = logreg.predict_proba(X_test)[:, 1]
    results.append(evaluate_predictions("Regresión logística", y_test, p_lr))

    # 5. Random Forest (con selección de hiperparámetros por validación temporal)
    print("   Entrenando Random Forest (TimeSeriesSplit temporal)...")
    tscv = TimeSeriesSplit(n_splits=4)
    best_rf, best_rf_score = None, -1.0
    for max_depth in (6, 10, 14):
        for min_leaf in (2, 5):
            cv_scores = []
            for tr_i, va_i in tscv.split(X_train):
                cand = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=max_depth,
                    min_samples_leaf=min_leaf,
                    random_state=SEED,
                    n_jobs=-1,
                )
                cand.fit(X_train[tr_i], y_train[tr_i])
                if len(np.unique(y_train[va_i])) > 1:
                    cv_scores.append(average_precision_score(y_train[va_i], cand.predict_proba(X_train[va_i])[:, 1]))
            mean_ap = float(np.mean(cv_scores)) if cv_scores else 0.0
            if mean_ap > best_rf_score:
                best_rf_score = mean_ap
                best_rf = (max_depth, min_leaf)

    rf_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=best_rf[0],
        min_samples_leaf=best_rf[1],
        random_state=SEED,
        n_jobs=-1,
    )
    rf_model.fit(X_train, y_train)
    p_rf = rf_model.predict_proba(X_test)[:, 1]
    results.append(evaluate_predictions("Random Forest", y_test, p_rf))

    # 6. XGBoost
    print("   Entrenando XGBoost...")
    xgb_model = XGBClassifier(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        eval_metric="logloss",
        random_state=SEED,
        n_jobs=-1,
    )
    xgb_model.fit(X_train, y_train)
    p_xgb = xgb_model.predict_proba(X_test)[:, 1]
    results.append(evaluate_predictions("XGBoost", y_test, p_xgb))

    # 7. CatBoost
    print("   Entrenando CatBoost...")
    cat_model = CatBoostClassifier(
        iterations=350,
        depth=5,
        learning_rate=0.05,
        random_seed=SEED,
        verbose=0,
    )
    cat_model.fit(X_train, y_train)
    p_cat = cat_model.predict_proba(X_test)[:, 1]
    results.append(evaluate_predictions("CatBoost", y_test, p_cat))

    # 8. LSTM (ventana t-7..t-1)
    print("   Entrenando LSTM (ventana t-7..t-1)...")
    lstm_model = NumpyLSTMClassifier(input_dim=seq_train.shape[2], hidden_dim=20, lr=0.015, epochs=25, seed=SEED)
    lstm_model.fit(seq_train, y_train)
    p_lstm = lstm_model.predict_proba(seq_test)[:, 1]
    results.append(evaluate_predictions("LSTM", y_test, p_lstm))

    # 9. GRU (ventana t-7..t-1)
    print("   Entrenando GRU (ventana t-7..t-1)...")
    gru_model = NumpyGRUClassifier(input_dim=seq_train.shape[2], hidden_dim=20, lr=0.015, epochs=25, seed=SEED)
    gru_model.fit(seq_train, y_train)
    p_gru = gru_model.predict_proba(seq_test)[:, 1]
    results.append(evaluate_predictions("GRU", y_test, p_gru))

    # Importancia por permutación en Random Forest (caída en PR-AUC por grupo)
    base_pr_auc = float(average_precision_score(y_test, p_rf))
    rng_perm = np.random.default_rng(SEED)
    perm_importance = {}
    for grp_name, cols in FEATURE_GROUPS.items():
        col_idxs = [FEATURES_16.index(c) for c in cols]
        drops = []
        for _ in range(15):
            X_perm = X_test.copy()
            perm_idx = rng_perm.permutation(len(X_perm))
            X_perm[:, col_idxs] = X_perm[perm_idx][:, col_idxs]
            pr_p = float(average_precision_score(y_test, rf_model.predict_proba(X_perm)[:, 1]))
            drops.append(base_pr_auc - pr_p)
        perm_importance[grp_name] = round(float(np.mean(drops)), 4)

    # Desempeño por establecimiento + inicios vs continuaciones (sobre el mejor modelo por PR-AUC entre ML)
    ml_candidates = {
        "Regresión logística": (logreg, p_lr),
        "Random Forest": (rf_model, p_rf),
        "XGBoost": (xgb_model, p_xgb),
        "CatBoost": (cat_model, p_cat),
        "LSTM": (lstm_model, p_lstm),
        "GRU": (gru_model, p_gru),
    }
    ml_rows = [r for r in results if r["modelo"] in ml_candidates]
    winner_row = max(ml_rows, key=lambda r: (r["pr_auc"], r["roc_auc"]))

    # Evaluar Random Forest por establecimiento e inicios de episodio
    rf_pred = (p_rf >= 0.5).astype(int)
    per_hospital = {}
    for h_name, grp in df_test.groupby("establecimiento"):
        idx = grp.index.to_numpy()
        yt = y_test[idx]
        yp = rf_pred[idx]
        n_sat = int(yt.sum())
        false_alarms = int(((yt == 0) & (yp == 1)).sum())
        per_hospital[h_name] = {
            "dias_prueba": int(len(yt)),
            "dias_saturados": n_sat,
            "f1": round(float(f1_score(yt, yp, zero_division=0)), 3) if n_sat > 0 else None,
            "falsas_alarmas": false_alarms,
        }

    sat_prev = df_test["sat_ayer"].to_numpy(dtype=int)
    inicios_mask = (sat_prev == 0) & (y_test == 1)
    cont_mask = (sat_prev == 1) & (y_test == 1)
    inicios_detectados = int((rf_pred[inicios_mask] == 1).sum())
    cont_detectadas = int((rf_pred[cont_mask] == 1).sum())

    # Variante complementaria de regresión (% ocupación del día t)
    print("   Entrenando variante complementaria de regresión (% ocupación)...")
    y_train_reg = df_train["porcentaje_ocupacion"].to_numpy(dtype=np.float64)
    y_test_reg = df_test["porcentaje_ocupacion"].to_numpy(dtype=np.float64)
    cat_reg = CatBoostRegressor(iterations=350, depth=5, learning_rate=0.05, random_seed=SEED, verbose=0)
    cat_reg.fit(X_train, y_train_reg)
    pred_reg = np.clip(cat_reg.predict(X_test), 0.0, 100.0)
    pers_reg = df_test["pct_ayer"].to_numpy(dtype=np.float64)

    reg_metrics = {
        "catboost_mae": round(float(mean_absolute_error(y_test_reg, pred_reg)), 2),
        "catboost_rmse": round(float(root_mean_squared_error(y_test_reg, pred_reg)), 2),
        "persistencia_mae": round(float(mean_absolute_error(y_test_reg, pers_reg)), 2),
        "persistencia_rmse": round(float(root_mean_squared_error(y_test_reg, pers_reg)), 2),
    }

    # Reentrenar Random Forest de despliegue con TODOS los datos disponibles hasta hoy (sin cambiar métricas reportadas de prueba)
    X_full = df[FEATURES_16].to_numpy(dtype=np.float64)
    y_full = df["estado_saturacion"].to_numpy(dtype=int)
    rf_deploy = RandomForestClassifier(
        n_estimators=300,
        max_depth=best_rf[0],
        min_samples_leaf=best_rf[1],
        random_state=SEED,
        n_jobs=-1,
    )
    rf_deploy.fit(X_full, y_full)

    # Guardar TODOS los modelos entrenados en 05_modelos/
    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    common_meta = {
        "features_16": FEATURES_16,
        "hosp_to_id": hosp_to_id,
        "code_to_id": code_to_id,
        "train_end": str(TRAIN_END.date()),
        "test_period": f"{TEST_START.date()}..{TEST_END.date()}",
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "clima_fuente": "NASA POWER MERRA-2 (2023-2026 real)",
    }

    rf_metrics = next(r for r in results if r["modelo"] == "Random Forest")
    joblib.dump({"model": rf_deploy, "eval_model": rf_model, "metrics": rf_metrics, **common_meta}, MODELOS_DIR / "modelo_rf.pkl")
    joblib.dump({"model": xgb_model, "metrics": next(r for r in results if r["modelo"] == "XGBoost"), **common_meta}, MODELOS_DIR / "modelo_xgb.pkl")
    joblib.dump({"model": cat_model, "metrics": next(r for r in results if r["modelo"] == "CatBoost"), **common_meta}, MODELOS_DIR / "modelo_catboost.pkl")
    joblib.dump({"model": logreg, "metrics": next(r for r in results if r["modelo"] == "Regresión logística"), **common_meta}, MODELOS_DIR / "modelo_logreg.pkl")
    joblib.dump({"model": lstm_model, "seq_features": SEQ_FEATURES, "metrics": next(r for r in results if r["modelo"] == "LSTM"), **common_meta}, MODELOS_DIR / "modelo_lstm.pkl")
    joblib.dump({"model": gru_model, "seq_features": SEQ_FEATURES, "metrics": next(r for r in results if r["modelo"] == "GRU"), **common_meta}, MODELOS_DIR / "modelo_gru.pkl")
    joblib.dump({"model": cat_reg, "metrics": reg_metrics, **common_meta}, MODELOS_DIR / "modelo_regresion_catboost.pkl")

    # Guardar tabla CSV y JSON de métricas completas
    res_df = pd.DataFrame(results)
    res_df.to_csv(MODELOS_DIR / "tabla_resultados_modelos.csv", index=False, encoding="utf-8-sig")

    summary = {
        "fecha_ejecucion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "clima_usado": "NASA POWER MERRA-2 real (2023-2026)",
        "n_entrenamiento": int(len(df_train)),
        "n_prueba_real": int(len(df_test)),
        "saturados_prueba_real": int(y_test.sum()),
        "pct_saturados_prueba": round(float(y_test.mean() * 100.0), 1),
        "mejor_modelo_ejecucion": winner_row,
        "random_forest_best_params": {"max_depth": best_rf[0], "min_samples_leaf": best_rf[1]},
        "resultados_modelos": results,
        "importancia_permutacion_rf": perm_importance,
        "desempeno_por_establecimiento_rf": per_hospital,
        "episodios_rf": {
            "inicios_totales": int(inicios_mask.sum()),
            "inicios_detectados": inicios_detectados,
            "continuaciones_totales": int(cont_mask.sum()),
            "continuaciones_detectadas": cont_detectadas,
        },
        "regresion_porcentaje_ocupacion": reg_metrics,
        "archivos_guardados": [
            "modelo_rf.pkl",
            "modelo_xgb.pkl",
            "modelo_catboost.pkl",
            "modelo_logreg.pkl",
            "modelo_lstm.pkl",
            "modelo_gru.pkl",
            "modelo_regresion_catboost.pkl",
        ],
    }
    with open(MODELOS_DIR / "metricas_evaluacion.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 78)
    print(" RESULTADOS DE EVALUACIÓN — PRUEBA REAL 01/09/2026 a 03/11/2026 (CLIMA REAL)")
    print("=" * 78)
    print(res_df.to_string(index=False))
    print("\nImportancia por permutación (Random Forest, caída PR-AUC):", perm_importance)
    print("Inicios de episodio detectados (RF):", f"{inicios_detectados}/{int(inicios_mask.sum())}")
    print("Regresión % ocupación:", reg_metrics)
    print(f"\n[03_evaluacion] OK -> 7 modelos .pkl y métricas guardados en: {MODELOS_DIR}")


if __name__ == "__main__":
    main()
