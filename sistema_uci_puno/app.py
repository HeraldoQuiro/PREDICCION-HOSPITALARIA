"""
=============================================================================
SISTEMA DE PREDICCIÓN DE SATURACIÓN DE CAMAS UCI — PUNO 2026 (SatUCI-Puno)
Aplicación Principal Flask
Universidad Nacional del Altiplano — EPIS
Curso: Estructuras de Datos Avanzadas, 2026-II
Equipo:
  - Roy Aldair Tipo Catunta (Machine Learning)
  - Robert Heraldo Quiro Arguedas (Aplicación Web Flask)
=============================================================================
"""

import os
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, session, flash, jsonify
)
from werkzeug.security import check_password_hash

from config import Config
from services import data_service, dashboard_service, alert_service
from ml.predictor import predictor_service

app = Flask(__name__)
app.config.from_object(Config)


# =============================================================================
# MIDDLEWARE & DECORADORES DE AUTENTICACIÓN
# =============================================================================

def login_required(f):
    """Decorador para proteger todas las rutas que requieren inicio de sesión."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            flash("Debe iniciar sesión para acceder al sistema.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_global_template_vars():
    """Inyecta variables globales en todas las plantillas Jinja2."""
    unread_alerts = 0
    if "user" in session:
        try:
            unread_alerts = alert_service.get_unread_count()
        except Exception:
            unread_alerts = 0

    return {
        "app_config": Config,
        "current_user": session.get("user"),
        "unread_alerts_count": unread_alerts,
        "current_year": datetime.now().year,
        "current_date_str": datetime.now().strftime("%d/%m/%Y"),
        "now": datetime.now()
    }


# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@app.route("/")
def index():
    """Ruta raíz: redirige al dashboard si está autenticado, o a login."""
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Página de inicio de sesión."""
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        # Validar contra SQLite
        data_service.ensure_db_initialized()
        conn = data_service.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        user_row = cursor.fetchone()
        conn.close()

        valid = False
        if user_row:
            if check_password_hash(user_row["password_hash"], password):
                valid = True
                user_info = {
                    "username": user_row["username"],
                    "nombre": user_row["nombre"],
                    "rol": user_row["rol"],
                    "email": user_row["email"]
                }
        # Fallback de credenciales por defecto (admin / uci2026)
        elif username == Config.DEFAULT_ADMIN_USER and password == Config.DEFAULT_ADMIN_PASS:
            valid = True
            user_info = {
                "username": Config.DEFAULT_ADMIN_USER,
                "nombre": "Administrador SatUCI",
                "rol": "admin",
                "email": "admin.uci@unap.edu.pe"
            }

        if valid:
            session["user"] = user_info
            flash(f"¡Bienvenido al sistema SatUCI-Puno, {user_info['nombre']}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))
        else:
            flash("Credenciales incorrectas. Verifique usuario y contraseña.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Cierra la sesión del usuario actual."""
    session.pop("user", None)
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("login"))


# =============================================================================
# RUTAS PRINCIPALES DEL SISTEMA
# =============================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """Tablero principal con KPIs, tarjetas de hospitales y gráficas interactivas."""
    summary = dashboard_service.get_dashboard_summary()
    recent_logs = data_service.get_historical_records(limit=8)
    return render_template(
        "dashboard.html",
        kpis=summary["kpis"],
        hospitals=summary["hospitals"],
        recent_logs=recent_logs
    )


@app.route("/registro", methods=["GET", "POST"])
@login_required
def registro():
    """Formulario de registro diario de ocupación de camas UCI."""
    if request.method == "POST":
        try:
            hospital_codigo = int(request.form.get("hospital_codigo", 0))
            fecha = request.form.get("fecha", datetime.now().strftime("%Y-%m-%d")).strip()
            camas_tot = int(request.form.get("camas_uci_tot", 0))
            camas_ocup = int(request.form.get("camas_ocupadas_uci", 0))
            observaciones = request.form.get("observaciones", "").strip()

            result = data_service.insert_daily_record(
                hospital_codigo=hospital_codigo,
                fecha=fecha,
                camas_tot=camas_tot,
                camas_ocup=camas_ocup,
                observaciones=observaciones
            )

            pct = result["porcentaje"]
            if result["saturado"]:
                flash(
                    f"¡Registro guardado! La UCI reporta {pct}% de ocupación: SATURACIÓN CRÍTICA (≥85%). Alerta generada.",
                    "danger"
                )
            elif pct >= Config.WARNING_THRESHOLD:
                flash(
                    f"¡Registro guardado! La UCI reporta {pct}% de ocupación: Nivel de Advertencia (≥75%).",
                    "warning"
                )
            else:
                flash(
                    f"¡Registro diario guardado exitosamente! Ocupación calculada: {pct}%.",
                    "success"
                )
            return redirect(url_for("registro"))

        except ValueError as e:
            flash(f"Error de validación: {str(e)}", "danger")
        except Exception as e:
            flash(f"Ocurrió un error al guardar el registro: {str(e)}", "danger")

    hospitals = data_service.get_all_hospitals()
    recent_entries = data_service.get_historical_records(limit=15)
    default_date = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "registro.html",
        hospitals=hospitals,
        recent_entries=recent_entries,
        default_date=default_date
    )


@app.route("/pronosticos")
@login_required
def pronosticos():
    """Pronósticos de saturación de camas UCI a 24 horas por establecimiento."""
    hospitals = data_service.get_all_hospitals()
    conn = data_service.get_db()
    cursor = conn.cursor()

    forecasts = []
    total_sat_predicted = 0
    high_risk_count = 0

    for hosp in hospitals:
        cursor.execute("""
            SELECT * FROM registros_diarios
            WHERE hospital_codigo = ?
            ORDER BY fecha DESC LIMIT 7
        """, (hosp["codigo"],))
        recent_records = cursor.fetchall()

        forecast = predictor_service.predict_hospital(hosp, recent_records)
        forecasts.append(forecast)

        if forecast["prediccion_clase"] == 1:
            total_sat_predicted += 1
        if forecast["nivel_riesgo"] in ["Alto", "Crítico"]:
            high_risk_count += 1

    conn.close()

    model_info = {
        "nombre": Config.BEST_MODEL_NAME,
        "roc_auc": Config.BEST_MODEL_ROC_AUC,
        "pr_auc": Config.BEST_MODEL_PR_AUC,
        "f1": Config.BEST_MODEL_F1,
        "horizonte": "24 horas (t)",
        "features_count": 16,
        "umbral_decision": f"{Config.SATURATION_THRESHOLD}% ocupación"
    }

    return render_template(
        "pronosticos.html",
        forecasts=forecasts,
        model_info=model_info,
        total_sat_predicted=total_sat_predicted,
        high_risk_count=high_risk_count
    )


@app.route("/pronosticos/reentrenar", methods=["POST"])
@login_required
def reentrenar_modelo():
    """Dispara el reentrenamiento del modelo Random Forest con datos actualizados (RF-06)."""
    try:
        metrics = predictor_service.train_and_save_model()
        flash(
            f"¡Modelo re-entrenado exitosamente! ROC-AUC: {metrics['roc_auc']} | F1: {metrics['f1_score']} ({metrics['total_muestras']} observaciones).",
            "success"
        )
    except Exception as e:
        flash(f"Aviso durante el entrenamiento: {str(e)}. Se mantendrá el modelo en memoria.", "warning")

    return redirect(url_for("pronosticos"))


@app.route("/alertas")
@login_required
def alertas():
    """Listado y gestión de alertas de saturación y advertencias preventivas."""
    filtro = request.args.get("filtro", "ALL")
    alerts_data = alert_service.get_alerts(alert_type=filtro)

    return render_template(
        "alertas.html",
        alerts=alerts_data["alerts"],
        counts=alerts_data["counts"],
        filtro_actual=filtro
    )


@app.route("/alertas/<int:alert_id>/leer", methods=["POST"])
@login_required
def marcar_alerta(alert_id):
    """Marca una alerta individual como atendida."""
    alert_service.mark_alert_read(alert_id)
    if request.is_json:
        return jsonify({"success": True, "alert_id": alert_id})
    flash("Alerta marcada como atendida.", "info")
    return redirect(url_for("alertas"))


@app.route("/alertas/marcar-todas", methods=["POST"])
@login_required
def marcar_todas_alertas():
    """Marca todas las alertas como atendidas."""
    alert_service.mark_all_read()
    flash("Todas las alertas han sido marcadas como atendidas.", "success")
    return redirect(url_for("alertas"))


# =============================================================================
# ENDPOINTS DE API REST (PARA CHART.JS Y FORMULARIOS AJAX)
# =============================================================================

@app.route("/api/chart/trend")
@login_required
def api_chart_trend():
    """Retorna las series temporales de ocupación de los 5 hospitales para Chart.js."""
    days = request.args.get("days", 30, type=int)
    data = data_service.get_occupancy_chart_data(days=days)
    return jsonify(data)


@app.route("/api/chart/beds")
@login_required
def api_chart_beds():
    """Retorna la distribución de camas ocupadas y disponibles para el gráfico de barras."""
    data = data_service.get_bed_distribution_data()
    return jsonify(data)


@app.route("/api/hospital/<int:codigo>/latest")
@login_required
def api_hospital_latest(codigo):
    """Retorna el último registro de un hospital para auto-completar el formulario de registro."""
    conn = data_service.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, h.nombre, h.camas_uci_tot as capacidad_nominal
        FROM hospitales h
        LEFT JOIN registros_diarios r ON h.codigo = r.hospital_codigo
        WHERE h.codigo = ?
        ORDER BY r.fecha DESC LIMIT 1
    """, (codigo,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return jsonify({
            "codigo": codigo,
            "nombre": row["nombre"],
            "capacidad_nominal": row["capacidad_nominal"],
            "camas_uci_tot": row["camas_uci_tot"] or row["capacidad_nominal"],
            "camas_ocupadas_uci": row["camas_ocupadas_uci"] or 0,
            "camas_uci_disp": row["camas_uci_disp"] or row["capacidad_nominal"],
            "porcentaje_ocupacion": row["porcentaje_ocupacion"] or 0.0,
            "ultima_fecha": row["fecha"] or datetime.now().strftime("%Y-%m-%d")
        })
    return jsonify({"error": "Hospital no encontrado"}), 404


@app.route("/api/stats")
@login_required
def api_stats():
    """Retorna resumen estadístico de los KPIs regionales en formato JSON."""
    summary = dashboard_service.get_dashboard_summary()
    return jsonify(summary["kpis"])


# =============================================================================
# MANEJADORES DE ERRORES HTTP
# =============================================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500


# =============================================================================
# INICIALIZACIÓN Y ARRANQUE
# =============================================================================

data_service.ensure_db_initialized()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ["true", "1"]
    print("=" * 70)
    print(" [SatUCI-Puno] Servidor Web de Monitoreo UCI iniciado")
    print(f" URL: http://localhost:{port}")
    print(f" Credenciales: Usuario '{Config.DEFAULT_ADMIN_USER}' | Contraseña '{Config.DEFAULT_ADMIN_PASS}'")
    print("=" * 70)
    app.run(host="0.0.0.0", port=port, debug=debug)
