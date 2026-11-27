"""
=============================================================================
Inicializador de Base de Datos SQLite: SatUCI-Puno
Puebla tablas con hospitales oficiales, usuario administrador y datos históricos
MINSA 2026 (1,560 registros).
=============================================================================
"""

import os
import sys
import csv
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.security import generate_password_hash

# Agregar directorio padre al path para importar config
CURRENT_DIR = Path(__file__).resolve().parent
APP_ROOT = CURRENT_DIR.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from config import Config


def get_connection(db_path=None):
    """Retorna una conexión a la base de datos SQLite."""
    path = db_path or Config.DATABASE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_database(db_path=None, csv_path=None):
    """Crea las tablas y carga los datos iniciales."""
    target_db = db_path or Config.DATABASE_PATH
    target_csv = csv_path or Config.CSV_DATA_PATH
    
    print(f"[SatUCI-Puno] Inicializando base de datos en: {target_db}")
    conn = get_connection(target_db)
    cursor = conn.cursor()

    # 1. Ejecutar Schema DDL
    schema_file = CURRENT_DIR / "schema.sql"
    with open(schema_file, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())
    conn.commit()
    print("  ✓ Tablas creadas correctamente.")

    # 2. Insertar Usuario Administrador
    cursor.execute("SELECT id FROM usuarios WHERE username = ?", (Config.DEFAULT_ADMIN_USER,))
    if not cursor.fetchone():
        hashed_pw = generate_password_hash(Config.DEFAULT_ADMIN_PASS)
        cursor.execute(
            """
            INSERT INTO usuarios (username, password_hash, nombre, rol, email)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                Config.DEFAULT_ADMIN_USER,
                hashed_pw,
                "Administrador SatUCI",
                "admin",
                "admin.uci@unap.edu.pe"
            )
        )
        conn.commit()
        print(f"  ✓ Usuario '{Config.DEFAULT_ADMIN_USER}' creado (pass: {Config.DEFAULT_ADMIN_PASS}).")

    # 3. Insertar Hospitales Oficiales
    for hosp in Config.HOSPITALS:
        cursor.execute(
            """
            INSERT OR REPLACE INTO hospitales 
            (codigo, nombre, institucion, ciudad, camas_uci_tot, tipo_uci, direccion, telefono, nivel, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                hosp["codigo"],
                hosp["nombre"],
                hosp["institucion"],
                hosp["ciudad"],
                hosp["camas_uci_tot"],
                hosp["tipo_uci"],
                hosp.get("direccion", ""),
                hosp.get("telefono", ""),
                hosp.get("nivel", "Nivel II")
            )
        )
    conn.commit()
    print(f"  ✓ 5 Hospitales oficiales de Puno registrados.")

    # 4. Cargar Registros Diarios desde CSV MINSA 2026
    cursor.execute("SELECT COUNT(*) as count FROM registros_diarios")
    total_existing = cursor.fetchone()["count"]

    if total_existing == 0:
        csv_loaded = False
        if target_csv and os.path.exists(target_csv):
            print(f"  ✓ Leyendo dataset oficial desde: {target_csv}")
            try:
                # Intentar utf-8-sig primero, luego latin-1
                encodings = ["utf-8-sig", "latin-1", "utf-8"]
                rows_to_insert = []
                for enc in encodings:
                    try:
                        with open(target_csv, "r", encoding=enc) as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                fecha = row.get("FECHACORTE", "").strip()
                                codigo = int(row.get("CODIGO", 0))
                                camas_tot = int(float(row.get("CAMAS_UCI_TOT", 0)))
                                camas_disp = int(float(row.get("CAMAS_UCI_DISP", 0)))
                                camas_ocup = int(float(row.get("camas_ocupadas_uci", camas_tot - camas_disp)))
                                pct = float(row.get("porcentaje_ocupacion", 0.0))
                                sat = int(row.get("estado_saturacion", 1 if pct >= 85.0 else 0))
                                
                                rows_to_insert.append((
                                    codigo, fecha, camas_tot, camas_disp, camas_ocup, pct, sat, "Importado MINSA-REUNIS 2026"
                                ))
                        csv_loaded = True
                        break
                    except UnicodeDecodeError:
                        continue

                if csv_loaded and rows_to_insert:
                    cursor.executemany(
                        """
                        INSERT OR IGNORE INTO registros_diarios
                        (hospital_codigo, fecha, camas_uci_tot, camas_uci_disp, camas_ocupadas_uci, porcentaje_ocupacion, estado_saturacion, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        rows_to_insert
                    )
                    conn.commit()
                    print(f"  ✓ {len(rows_to_insert)} registros históricos cargados desde el CSV.")
            except Exception as e:
                print(f"  ⚠ Error al parsear CSV ({e}). Se generarán datos calibrados de respaldo.")
                csv_loaded = False

        if not csv_loaded:
            # Generador de datos calibrados de respaldo si no encuentra el archivo CSV
            print("  ℹ Generando historial calibrado de 330 días para los 5 hospitales...")
            base_date = datetime(2026, 1, 1)
            sim_rows = []
            import random
            random.seed(42)

            for day_offset in range(330):
                curr_date = (base_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
                for hosp in Config.HOSPITALS:
                    cap = hosp["camas_uci_tot"]
                    # Simular ocupación realista con fluctuación invernal (jun-ago más alta)
                    month = (base_date + timedelta(days=day_offset)).month
                    winter_boost = 0.15 if 5 <= month <= 8 else 0.0
                    base_rate = 0.55 + winter_boost + random.uniform(-0.25, 0.25)
                    base_rate = max(0.0, min(1.0, base_rate))
                    ocup = int(round(cap * base_rate))
                    ocup = min(cap, max(0, ocup))
                    disp = cap - ocup
                    pct = (ocup / cap) * 100.0 if cap > 0 else 0.0
                    sat = 1 if pct >= 85.0 else 0
                    
                    sim_rows.append((
                        hosp["codigo"], curr_date, cap, disp, ocup, round(pct, 2), sat, "Simulación estadística calibrada"
                    ))
            
            cursor.executemany(
                """
                INSERT OR IGNORE INTO registros_diarios
                (hospital_codigo, fecha, camas_uci_tot, camas_uci_disp, camas_ocupadas_uci, porcentaje_ocupacion, estado_saturacion, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                sim_rows
            )
            conn.commit()
            print(f"  ✓ {len(sim_rows)} registros calibrados insertados en la base de datos.")

    # 5. Generar Alertas Activas Iniciales
    cursor.execute("SELECT COUNT(*) as count FROM alertas")
    if cursor.fetchone()["count"] == 0:
        print("  ✓ Evaluando alertas operativas iniciales...")
        # Obtener último registro de cada hospital
        for hosp in Config.HOSPITALS:
            cursor.execute(
                """
                SELECT * FROM registros_diarios 
                WHERE hospital_codigo = ? 
                ORDER BY fecha DESC LIMIT 1
                """,
                (hosp["codigo"],)
            )
            latest = cursor.fetchone()
            if latest:
                pct = latest["porcentaje_ocupacion"]
                fecha = latest["fecha"]
                ocup = latest["camas_ocupadas_uci"]
                tot = latest["camas_uci_tot"]
                
                if pct >= Config.SATURATION_THRESHOLD:
                    cursor.execute(
                        """
                        INSERT INTO alertas 
                        (hospital_codigo, fecha, tipo_alerta, nivel, porcentaje_ocupacion, probabilidad_saturacion, camas_ocupadas, camas_totales, mensaje, leida)
                        VALUES (?, ?, 'CRITICA', 'ROJA', ?, 0.88, ?, ?, ?, 0)
                        """,
                        (
                            hosp["codigo"], fecha, pct, ocup, tot,
                            f"ALERTA CRÍTICA: UCI saturada al {pct:.1f}% ({ocup}/{tot} camas). Se requiere activación de contingencia y derivación."
                        )
                    )
                elif pct >= Config.WARNING_THRESHOLD:
                    cursor.execute(
                        """
                        INSERT INTO alertas 
                        (hospital_codigo, fecha, tipo_alerta, nivel, porcentaje_ocupacion, probabilidad_saturacion, camas_ocupadas, camas_totales, mensaje, leida)
                        VALUES (?, ?, 'ADVERTENCIA', 'AMARILLA', ?, 0.65, ?, ?, ?, 0)
                        """,
                        (
                            hosp["codigo"], fecha, pct, ocup, tot,
                            f"ADVERTENCIA PREVENTIVA: Ocupación alta al {pct:.1f}% ({ocup}/{tot} camas). Monitoreo continuo a 24 horas."
                        )
                    )
        conn.commit()

    # 6. Generar Pronósticos Iniciales a 24 Horas
    cursor.execute("SELECT COUNT(*) as count FROM pronosticos")
    if cursor.fetchone()["count"] == 0:
        print("  ✓ Generando pronósticos predictivos a 24 horas iniciales...")
        try:
            from ml.mock_predictor import generate_initial_forecasts
            generate_initial_forecasts(conn)
            print("  ✓ Pronósticos predictivos a 24 horas generados.")
        except Exception as e:
            print(f"  ⚠ Aviso al generar pronósticos ({e}). Se calcularán dinámicamente en la aplicación.")

    conn.close()
    print("\n[SatUCI-Puno] ¡Inicialización completada con éxito!\n")


if __name__ == "__main__":
    init_database()
