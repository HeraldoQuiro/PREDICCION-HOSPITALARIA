"""
=============================================================================
CAPA DE SERVICIOS: dashboard_service.py
Agregación de métricas ejecutivas para el tablero de control, KPIs globales,
tarjetas de hospital con indicadores de saturación y estado regional.
=============================================================================
"""

import sqlite3
from datetime import datetime
from config import Config
from services.data_service import get_latest_status_all, get_db
from ml.predictor import predictor_service


def get_dashboard_summary():
    """
    Retorna el resumen consolidado de KPIs e indicadores para el dashboard principal.
    """
    latest_hospitals = get_latest_status_all()
    conn = get_db()
    cursor = conn.cursor()

    total_hospitales = len(latest_hospitals)
    saturados_hoy = 0
    alerta_hoy = 0
    normales_hoy = 0
    total_camas_regional = 0
    total_ocupadas_regional = 0

    enriched_cards = []

    for hosp in latest_hospitals:
        pct = hosp["porcentaje_ocupacion"]
        camas_tot = hosp["camas_uci_tot"]
        camas_ocup = hosp["camas_ocupadas_uci"]

        total_camas_regional += camas_tot
        total_ocupadas_regional += camas_ocup

        if pct >= Config.SATURATION_THRESHOLD:
            saturados_hoy += 1
        elif pct >= Config.WARNING_THRESHOLD:
            alerta_hoy += 1
        else:
            normales_hoy += 1

        # Obtener historial reciente para inferencia predictiva a 24 horas
        cursor.execute("""
            SELECT * FROM registros_diarios
            WHERE hospital_codigo = ?
            ORDER BY fecha DESC LIMIT 7
        """, (hosp["codigo"],))
        recent_records = cursor.fetchall()

        # Generar predicción a 24 horas
        forecast = predictor_service.predict_hospital(hosp, recent_records)

        card_data = {
            **hosp,
            "forecast_prob": forecast.get("probabilidad_porcentaje", 0.0),
            "forecast_prob_raw": forecast.get("probabilidad_saturacion", 0.0),
            "forecast_risk": forecast.get("nivel_riesgo", "Bajo"),
            "forecast_class": forecast.get("prediccion_clase", 0),
            "forecast_trend": forecast.get("tendencia", "estable"),
            "forecast_pct": forecast.get("porcentaje_predicho", pct)
        }
        enriched_cards.append(card_data)

    conn.close()

    # Ocupación promedio regional ponderada
    if total_camas_regional > 0:
        ocupacion_promedio_regional = round((total_ocupadas_regional / total_camas_regional) * 100.0, 1)
    else:
        ocupacion_promedio_regional = 0.0

    camas_disponibles_regional = total_camas_regional - total_ocupadas_regional

    # Nivel de alerta regional
    if saturados_hoy >= 2 or ocupacion_promedio_regional >= Config.SATURATION_THRESHOLD:
        estado_regional = "CRÍTICO"
        estado_regional_badge = "badge-danger"
        estado_regional_color = "#ff4757"
    elif saturados_hoy == 1 or alerta_hoy >= 2 or ocupacion_promedio_regional >= Config.WARNING_THRESHOLD:
        estado_regional = "EN ALERTA"
        estado_regional_badge = "badge-warning"
        estado_regional_color = "#f59e0b"
    else:
        estado_regional = "OPERATIVO"
        estado_regional_badge = "badge-success"
        estado_regional_color = "#10b981"

    # Fecha del reporte más reciente
    ultima_fecha = enriched_cards[0]["ultima_fecha"] if enriched_cards else datetime.now().strftime("%Y-%m-%d")

    return {
        "kpis": {
            "total_hospitales": total_hospitales,
            "saturados_hoy": saturados_hoy,
            "alerta_hoy": alerta_hoy,
            "normales_hoy": normales_hoy,
            "total_camas_regional": total_camas_regional,
            "total_ocupadas_regional": total_ocupadas_regional,
            "camas_disponibles_regional": camas_disponibles_regional,
            "ocupacion_promedio": ocupacion_promedio_regional,
            "estado_regional": estado_regional,
            "estado_regional_badge": estado_regional_badge,
            "estado_regional_color": estado_regional_color,
            "ultima_fecha": ultima_fecha,
            "umbral_saturacion": Config.SATURATION_THRESHOLD
        },
        "hospitals": enriched_cards
    }
