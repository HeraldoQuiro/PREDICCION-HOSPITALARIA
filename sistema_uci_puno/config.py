"""
=============================================================================
SISTEMA DE PREDICCIÓN DE SATURACIÓN DE CAMAS UCI — PUNO 2026 (SatUCI-Puno)
Configuración General del Sistema Web
Universidad Nacional del Altiplano — EPIS
Curso: Estructuras de Datos Avanzadas, 2026-II
Equipo:
  - Roy Aldair Tipo Catunta (Modelos de Machine Learning)
  - Robert Heraldo Quiro Arguedas (Aplicación Web Flask)
Asesor: Hugo Yosef Gomez Quispe
=============================================================================
"""

import os
from pathlib import Path

# Directorio base del aplicativo
BASE_DIR = Path(__file__).resolve().parent

# Posibles ubicaciones del CSV oficial MINSA 2026
CSV_CANDIDATE_PATHS = [
    r"C:\PROJECTS\PREDICCION HOSPITALARIA\01_datos\UCI_5_HOSPITALES_PUNO_2026.csv",
    str(BASE_DIR.parent / "01_datos" / "UCI_5_HOSPITALES_PUNO_2026.csv"),
    str(BASE_DIR / "data" / "UCI_5_HOSPITALES_PUNO_2026.csv"),
    str(BASE_DIR / "database" / "UCI_5_HOSPITALES_PUNO_2026.csv"),
]

# Posibles ubicaciones del modelo .pkl
MODEL_CANDIDATE_PATHS = [
    r"C:\PROJECTS\PREDICCION HOSPITALARIA\05_modelos\modelo_rf.pkl",
    str(BASE_DIR.parent / "05_modelos" / "modelo_rf.pkl"),
    r"C:\PROJECTS\PREDICCION HOSPITALARIA\05_modelos\rf_uci_model.pkl",
    str(BASE_DIR.parent / "05_modelos" / "rf_uci_model.pkl"),
    str(BASE_DIR / "ml" / "rf_uci_model.pkl"),
]


class Config:
    """Configuración principal de la aplicación Flask SatUCI-Puno."""

    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "sat-uci-puno-2026-secret-key-epis-unap"
    )

    # Base de datos SQLite (Desarrollo y portabilidad)
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "database" / "uci_puno.db")
    )

    # Resolución dinámica de la ruta del archivo CSV
    CSV_DATA_PATH = None
    for path in CSV_CANDIDATE_PATHS:
        if os.path.exists(path):
            CSV_DATA_PATH = path
            break
    if not CSV_DATA_PATH:
        CSV_DATA_PATH = CSV_CANDIDATE_PATHS[0]

    # Resolución dinámica de la ruta del modelo ML
    MODEL_PATH = None
    for path in MODEL_CANDIDATE_PATHS:
        if os.path.exists(path):
            MODEL_PATH = path
            break
    if not MODEL_PATH:
        MODEL_PATH = str(BASE_DIR.parent / "05_modelos" / "modelo_rf.pkl")

    # Umbrales clínicos y de gestión hospitalaria (MINSA & Litvak & Bisognano, 2011)
    SATURATION_THRESHOLD = 85.0  # >= 85% saturación crítica (estado_saturacion = 1)
    WARNING_THRESHOLD = 75.0     # >= 75% advertencia amarilla (zona de riesgo)
    PREDICTION_ALERT_THRESHOLD = 0.60  # Probabilidad >= 60% para alerta preventiva 24h

    # Credenciales de acceso por defecto
    DEFAULT_ADMIN_USER = "admin"
    DEFAULT_ADMIN_PASS = "uci2026"

    # Metadatos del Proyecto
    APP_NAME = "SatUCI Puno"
    APP_VERSION = "1.0.0"
    APP_SUBTITLE = "Predicción de Saturación UCI a 24h"
    UNIVERSITY = "Universidad Nacional del Altiplano"
    FACULTY = "Facultad de Ingeniería Mecánica Eléctrica, Electrónica y Sistemas"
    SCHOOL = "Escuela Profesional de Ingeniería de Sistemas (EPIS)"
    COURSE = "Estructuras de Datos Avanzadas — 2026-II"
    AUTHORS = "Roy Aldair Tipo Catunta · Robert Heraldo Quiro Arguedas"
    ADVISOR = "Hugo Yosef Gomez Quispe"
    BEST_MODEL_NAME = "Random Forest Classifier"
    BEST_MODEL_ROC_AUC = 0.911
    BEST_MODEL_PR_AUC = 0.592
    BEST_MODEL_F1 = 0.625

    # 5 Establecimientos de Salud con Camas UCI de la Región Puno (REUNIS 2026)
    # Capacidad = mediana de camas UCI totales en 2026 (Tabla 4 del informe base)
    HOSPITALS = [
        {
            "codigo": 3299,
            "nombre": "CARLOS MONJE MEDRANO",
            "institucion": "GOBIERNO REGIONAL",
            "ciudad": "Juliaca, Puno",
            "camas_uci_tot": 3,
            "tipo_uci": "UCI total",
            "direccion": "Región Puno — REUNIS MINSA",
            "telefono": "—",
            "nivel": "MINSA / GORE"
        },
        {
            "codigo": 10815,
            "nombre": "CLINICA ADVENTISTA AMERICANA DE JULIACA",
            "institucion": "PRIVADO",
            "ciudad": "Juliaca, Puno",
            "camas_uci_tot": 2,
            "tipo_uci": "UCI total",
            "direccion": "Región Puno — REUNIS MINSA",
            "telefono": "—",
            "nivel": "Privado"
        },
        {
            "codigo": 11978,
            "nombre": "CLINICA MONTE SINAI JULIACA",
            "institucion": "PRIVADO",
            "ciudad": "Juliaca, Puno",
            "camas_uci_tot": 1,
            "tipo_uci": "UCI total",
            "direccion": "Región Puno — REUNIS MINSA",
            "telefono": "—",
            "nivel": "Privado"
        },
        {
            "codigo": 3251,
            "nombre": "HOSPITAL REGIONAL MANUEL NUÑEZ BUTRON",
            "institucion": "GOBIERNO REGIONAL",
            "ciudad": "Puno",
            "camas_uci_tot": 6,
            "tipo_uci": "UCI total",
            "direccion": "Región Puno — REUNIS MINSA",
            "telefono": "—",
            "nivel": "MINSA / GORE"
        },
        {
            "codigo": 31179,
            "nombre": "HOSPITAL SAN MARTIN DE PORRES",
            "institucion": "GOBIERNO REGIONAL",
            "ciudad": "Puno",
            "camas_uci_tot": 9,
            "tipo_uci": "UCI total",
            "direccion": "Región Puno — REUNIS MINSA",
            "telefono": "—",
            "nivel": "MINSA / GORE"
        }
    ]
