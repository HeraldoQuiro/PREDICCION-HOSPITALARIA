"""
=============================================================================
CAPA DE SERVICIOS: alert_service.py
Gestión y consulta del sistema de alertas tempranas de saturación UCI.
Categoriza eventos según umbrales críticos (≥85%), preventivos (≥75%) y
predicciones a 24 horas con alta probabilidad (≥60%).
=============================================================================
"""

import sqlite3
from config import Config
from services.data_service import get_db, ensure_db_initialized


def get_alerts(unread_only=False, alert_type=None):
    """
    Retorna la lista de alertas registradas en el sistema, ordenadas por severidad y fecha.
    """
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT a.*, h.nombre as hospital_nombre, h.institucion, h.ciudad, h.telefono
        FROM alertas a
        JOIN hospitales h ON a.hospital_codigo = h.codigo
        WHERE 1=1
    """
    params = []

    if unread_only:
        query += " AND a.leida = 0"
    
    if alert_type and alert_type != "ALL":
        query += " AND a.tipo_alerta = ?"
        params.append(alert_type)

    query += " ORDER BY a.leida ASC, a.fecha DESC, a.id DESC LIMIT 100"

    cursor.execute(query, params)
    alerts = [dict(r) for r in cursor.fetchall()]

    # Estadísticas para filtros en la vista
    cursor.execute("SELECT COUNT(*) as count FROM alertas WHERE nivel = 'ROJA' AND leida = 0")
    criticas_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM alertas WHERE nivel = 'AMARILLA' AND leida = 0")
    advertencias_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM alertas WHERE tipo_alerta = 'PREVENTIVA_24H' AND leida = 0")
    preventivas_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM alertas WHERE leida = 0")
    total_activas = cursor.fetchone()["count"]

    conn.close()

    return {
        "alerts": alerts,
        "counts": {
            "total_activas": total_activas,
            "criticas": criticas_count,
            "advertencias": advertencias_count,
            "preventivas": preventivas_count,
            "total_registradas": len(alerts)
        }
    }


def get_unread_count():
    """Retorna el número de alertas no leídas para el badge del topbar."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM alertas WHERE leida = 0")
    count = cursor.fetchone()["count"]
    conn.close()
    return count


def mark_alert_read(alert_id):
    """Marca una alerta específica como atendida/leída."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE alertas SET leida = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return True


def mark_all_read():
    """Marca todas las alertas como atendidas."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE alertas SET leida = 1 WHERE leida = 0")
    conn.commit()
    conn.close()
    return True
