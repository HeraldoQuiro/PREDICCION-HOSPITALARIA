"""
=============================================================================
CAPA DE SERVICIOS: data_service.py
Gestión de consultas SQLite, lectura de registros de ocupación, persistencia
de nuevos reportes diarios y generación de series temporales para Chart.js.
=============================================================================
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from config import Config


def get_db():
    """Retorna una conexión a la base de datos SQLite con row_factory activado."""
    db_path = Config.DATABASE_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db_initialized():
    """Verifica si la base de datos existe y tiene tablas; si no, la inicializa."""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hospitales'")
        table_exists = cursor.fetchone()
        if not table_exists:
            from database.init_db import init_database
            conn.close()
            init_database()
            return
        
        # Verificar que tenga registros
        cursor.execute("SELECT COUNT(*) as count FROM registros_diarios")
        if cursor.fetchone()["count"] == 0:
            from database.init_db import init_database
            conn.close()
            init_database()
            return
    except Exception as e:
        print(f"[DataService] Verificación DB: {e}. Inicializando...")
        from database.init_db import init_database
        conn.close()
        init_database()
        return
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_all_hospitals():
    """Retorna la lista de los 5 hospitales monitoreados."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT codigo, nombre, institucion, ciudad, camas_uci_tot, tipo_uci, direccion, telefono, nivel, activo
        FROM hospitales
        ORDER BY codigo ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_hospital_by_code(codigo):
    """Retorna los datos de un hospital por su código oficial MINSA."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hospitales WHERE codigo = ?", (codigo,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_status_all():
    """
    Retorna el estado más reciente de ocupación de cada uno de los 5 hospitales,
    junto con sus camas totales, ocupadas, disponibles, % y estado de saturación.
    """
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()

    hospitals = get_all_hospitals()
    result = []

    for hosp in hospitals:
        cursor.execute("""
            SELECT * FROM registros_diarios
            WHERE hospital_codigo = ?
            ORDER BY fecha DESC LIMIT 1
        """, (hosp["codigo"],))
        latest = cursor.fetchone()

        # Obtener los últimos 7 días para sparklines/tendencia
        cursor.execute("""
            SELECT fecha, porcentaje_ocupacion, camas_ocupadas_uci
            FROM registros_diarios
            WHERE hospital_codigo = ?
            ORDER BY fecha DESC LIMIT 7
        """, (hosp["codigo"],))
        recent_7 = [dict(r) for r in cursor.fetchall()]
        sparkline = [r["porcentaje_ocupacion"] for r in reversed(recent_7)]

        if latest:
            pct = latest["porcentaje_ocupacion"]
            camas_tot = latest["camas_uci_tot"]
            camas_ocup = latest["camas_ocupadas_uci"]
            camas_disp = latest["camas_uci_disp"]
            fecha = latest["fecha"]
            sat = latest["estado_saturacion"]
        else:
            pct = 0.0
            camas_tot = hosp["camas_uci_tot"]
            camas_ocup = 0
            camas_disp = camas_tot
            fecha = datetime.now().strftime("%Y-%m-%d")
            sat = 0

        # Semáforo de color
        if pct >= Config.SATURATION_THRESHOLD:
            status_color = "danger"
            status_text = "Saturado"
            badge_class = "badge-danger"
        elif pct >= Config.WARNING_THRESHOLD:
            status_color = "warning"
            status_text = "En Alerta"
            badge_class = "badge-warning"
        else:
            status_color = "success"
            status_text = "Normal"
            badge_class = "badge-success"

        result.append({
            "codigo": hosp["codigo"],
            "nombre": hosp["nombre"],
            "institucion": hosp["institucion"],
            "ciudad": hosp["ciudad"],
            "direccion": hosp.get("direccion", ""),
            "telefono": hosp.get("telefono", ""),
            "nivel": hosp.get("nivel", "Nivel II"),
            "camas_uci_tot": camas_tot,
            "camas_ocupadas_uci": camas_ocup,
            "camas_uci_disp": camas_disp,
            "porcentaje_ocupacion": round(pct, 1),
            "estado_saturacion": sat,
            "ultima_fecha": fecha,
            "status_color": status_color,
            "status_text": status_text,
            "badge_class": badge_class,
            "sparkline": sparkline
        })

    conn.close()
    return result


def get_occupancy_chart_data(days=30):
    """
    Retorna datos de tendencia histórica formateados para Chart.js:
    - Labels: lista de fechas cronológicas.
    - Datasets: una serie por cada hospital.
    """
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()

    # Obtener las últimas 'days' fechas únicas ordenadas
    cursor.execute("""
        SELECT DISTINCT fecha FROM registros_diarios
        ORDER BY fecha DESC LIMIT ?
    """, (days,))
    fechas = [r["fecha"] for r in cursor.fetchall()]
    fechas.reverse()

    if not fechas:
        conn.close()
        return {"labels": [], "datasets": []}

    hospitals = get_all_hospitals()
    
    # Paleta de colores para cada hospital (acorde al tema dark/neon)
    colors = [
        {"border": "#00d4ff", "bg": "rgba(0, 212, 255, 0.15)"},      # Carlos Monje: Teal
        {"border": "#a855f7", "bg": "rgba(168, 85, 247, 0.15)"},    # Adventista: Morado
        {"border": "#f59e0b", "bg": "rgba(245, 158, 11, 0.15)"},    # Monte Sinai: Amber
        {"border": "#10b981", "bg": "rgba(16, 185, 129, 0.15)"},    # Manuel Nuñez: Esmeralda
        {"border": "#ec4899", "bg": "rgba(236, 72, 153, 0.15)"}     # San Martín: Rosa neón
    ]

    datasets = []
    for idx, hosp in enumerate(hospitals):
        color = colors[idx % len(colors)]
        
        # Consultar registros para este hospital en las fechas seleccionadas
        cursor.execute("""
            SELECT fecha, porcentaje_ocupacion FROM registros_diarios
            WHERE hospital_codigo = ? AND fecha IN ({})
            ORDER BY fecha ASC
        """.format(",".join("?" for _ in fechas)), (hosp["codigo"], *fechas))
        
        records_dict = {r["fecha"]: round(r["porcentaje_ocupacion"], 1) for r in cursor.fetchall()}
        
        # Mapear valores alineados con las etiquetas de fecha
        data_points = [records_dict.get(f, None) for f in fechas]

        # Nombres simplificados para la leyenda
        short_name = hosp["nombre"].replace("HOSPITAL REGIONAL ", "").replace("CLINICA ", "CLÍNICA ")

        datasets.append({
            "label": short_name,
            "data": data_points,
            "borderColor": color["border"],
            "backgroundColor": color["bg"],
            "borderWidth": 2.5,
            "pointRadius": 2,
            "pointHoverRadius": 6,
            "tension": 0.35,
            "fill": False
        })

    conn.close()
    return {
        "labels": fechas,
        "datasets": datasets,
        "threshold": Config.SATURATION_THRESHOLD
    }


def get_bed_distribution_data():
    """
    Retorna la distribución actual de camas ocupadas vs disponibles por hospital
    para el gráfico de barras comparativo de capacidad.
    """
    latest_status = get_latest_status_all()
    labels = []
    occupied = []
    available = []

    for h in latest_status:
        short = h["nombre"].replace("HOSPITAL REGIONAL ", "HR ").replace("HOSPITAL ", "H. ").replace("CLINICA ", "CL. ")
        labels.append(short)
        occupied.append(h["camas_ocupadas_uci"])
        available.append(h["camas_uci_disp"])

    return {
        "labels": labels,
        "occupied": occupied,
        "available": available
    }


def get_historical_records(limit=100, hospital_codigo=None):
    """Retorna los registros de ocupación más recientes para la tabla histórica."""
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()

    if hospital_codigo:
        cursor.execute("""
            SELECT r.*, h.nombre as hospital_nombre, h.institucion, h.ciudad
            FROM registros_diarios r
            JOIN hospitales h ON r.hospital_codigo = h.codigo
            WHERE r.hospital_codigo = ?
            ORDER BY r.fecha DESC, r.id DESC LIMIT ?
        """, (hospital_codigo, limit))
    else:
        cursor.execute("""
            SELECT r.*, h.nombre as hospital_nombre, h.institucion, h.ciudad
            FROM registros_diarios r
            JOIN hospitales h ON r.hospital_codigo = h.codigo
            ORDER BY r.fecha DESC, r.hospital_codigo ASC LIMIT ?
        """, (limit,))

    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def insert_daily_record(hospital_codigo, fecha, camas_tot, camas_ocup, observaciones=""):
    """
    Registra o actualiza el reporte diario de un hospital.
    Calcula automáticamente camas disponibles, porcentaje de ocupación y estado de saturación.
    Crea o actualiza alertas si se superan los umbrales.
    """
    ensure_db_initialized()
    conn = get_db()
    cursor = conn.cursor()

    camas_tot = int(camas_tot)
    camas_ocup = int(camas_ocup)
    if camas_tot <= 0:
        raise ValueError("El total de camas UCI debe ser mayor a 0.")
    if camas_ocup < 0:
        raise ValueError("Las camas ocupadas no pueden ser negativas.")
    if camas_ocup > camas_tot:
        raise ValueError("Las camas ocupadas no pueden superar la capacidad total.")

    camas_disp = camas_tot - camas_ocup
    porcentaje = round((camas_ocup / camas_tot) * 100.0, 2)
    estado_sat = 1 if porcentaje >= Config.SATURATION_THRESHOLD else 0

    # Insertar o actualizar registro
    cursor.execute("""
        INSERT INTO registros_diarios 
        (hospital_codigo, fecha, camas_uci_tot, camas_uci_disp, camas_ocupadas_uci, porcentaje_ocupacion, estado_saturacion, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hospital_codigo, fecha) DO UPDATE SET
            camas_uci_tot = excluded.camas_uci_tot,
            camas_uci_disp = excluded.camas_uci_disp,
            camas_ocupadas_uci = excluded.camas_ocupadas_uci,
            porcentaje_ocupacion = excluded.porcentaje_ocupacion,
            estado_saturacion = excluded.estado_saturacion,
            observaciones = excluded.observaciones,
            created_at = CURRENT_TIMESTAMP
    """, (hospital_codigo, fecha, camas_tot, camas_disp, camas_ocup, porcentaje, estado_sat, observaciones))

    # Obtener nombre del hospital
    cursor.execute("SELECT nombre FROM hospitales WHERE codigo = ?", (hospital_codigo,))
    hosp_name = cursor.fetchone()["nombre"]

    # Generar alertas automáticas según umbral
    if porcentaje >= Config.SATURATION_THRESHOLD:
        cursor.execute("""
            INSERT INTO alertas 
            (hospital_codigo, fecha, tipo_alerta, nivel, porcentaje_ocupacion, probabilidad_saturacion, camas_ocupadas, camas_totales, mensaje, leida)
            VALUES (?, ?, 'CRITICA', 'ROJA', ?, 0.95, ?, ?, ?, 0)
        """, (
            hospital_codigo, fecha, porcentaje, camas_ocup, camas_tot,
            f"ALERTA ROJA: {hosp_name} ha alcanzado estado de SATURACIÓN ({porcentaje}% - {camas_ocup}/{camas_tot} camas ocupadas)."
        ))
    elif porcentaje >= Config.WARNING_THRESHOLD:
        cursor.execute("""
            INSERT INTO alertas 
            (hospital_codigo, fecha, tipo_alerta, nivel, porcentaje_ocupacion, probabilidad_saturacion, camas_ocupadas, camas_totales, mensaje, leida)
            VALUES (?, ?, 'ADVERTENCIA', 'AMARILLA', ?, 0.70, ?, ?, ?, 0)
        """, (
            hospital_codigo, fecha, porcentaje, camas_ocup, camas_tot,
            f"ADVERTENCIA AMARILLA: {hosp_name} se encuentra en riesgo preventivo ({porcentaje}% ocupado)."
        ))

    conn.commit()
    conn.close()

    # Recalcular pronósticos con el nuevo registro
    try:
        from ml.mock_predictor import generate_initial_forecasts
        conn_pred = get_db()
        generate_initial_forecasts(conn_pred)
        conn_pred.close()
    except Exception as e:
        print(f"[DataService] Recálculo de pronósticos tras registro: {e}")

    return {
        "hospital_codigo": hospital_codigo,
        "fecha": fecha,
        "porcentaje": porcentaje,
        "saturado": bool(estado_sat)
    }
