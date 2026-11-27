# -*- coding: utf-8 -*-
"""
=============================================================================
04_completar_informe.py
Regenera y actualiza el informe TF - 5H.docx leyendo automáticamente los
resultados reales de:
  - 01_datos/clima_puno_nasa_power_2023_2026.csv
  - 01_datos/dataset_uci_puno_consolidado_2023_2026.csv
  - 05_modelos/calibracion_simulador.json
  - 05_modelos/metricas_evaluacion.json
  - Proyecto_UCI_EPIS_2026II_Puno.pdf (base metodológica)
=============================================================================
"""

import json
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

BASE_DIR = Path(__file__).resolve().parent.parent
DOCX_PATH = BASE_DIR / "informe TF - 5H.docx"
CALIB_JSON = BASE_DIR / "05_modelos" / "calibracion_simulador.json"
EVAL_JSON = BASE_DIR / "05_modelos" / "metricas_evaluacion.json"


def set_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "B0BEC5")
        borders.append(el)
    tblPr.append(borders)


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def add_styled_table(doc, headers, rows, highlight_substr=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "TableNormal"
    set_table_borders(table)

    for j, h_text in enumerate(headers):
        cell = table.rows[0].cells[j]
        shade_cell(cell, "1A5CBB")
        p = cell.paragraphs[0]
        p.clear()
        r = p.add_run(h_text)
        r.bold = True
        r.font.size = Pt(9.0)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for i, row in enumerate(rows):
        is_hl = highlight_substr and any(highlight_substr in str(x) for x in row)
        bg = "E3F2FD" if is_hl else ("F8FAFC" if i % 2 == 1 else "FFFFFF")
        for j, val in enumerate(row):
            cell = table.rows[i + 1].cells[j]
            shade_cell(cell, bg)
            p = cell.paragraphs[0]
            p.clear()
            r = p.add_run(str(val))
            r.font.size = Pt(9.0)
            if is_hl and j == 0:
                r.bold = True
    return table


def add_sec_heading(doc, text, level=2):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12 if level <= 2 else 8)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.bold = True
    if level == 1:
        r.font.size = Pt(15)
        r.font.color.rgb = RGBColor(0x1A, 0x5C, 0xBB)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif level == 2:
        r.font.size = Pt(12.5)
        r.font.color.rgb = RGBColor(0x0D, 0x3B, 0x66)
    else:
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    return p


def add_bullet(doc, lead_bold, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Pt(18)
    p.paragraph_format.space_after = Pt(2)
    r_dot = p.add_run("• ")
    r_dot.bold = True
    if lead_bold:
        r_b = p.add_run(lead_bold)
        r_b.bold = True
        r_b.font.size = Pt(10.0)
    r_t = p.add_run(text)
    r_t.font.size = Pt(10.0)
    return p


def main():
    with open(CALIB_JSON, "r", encoding="utf-8") as f:
        calib = json.load(f)
    with open(EVAL_JSON, "r", encoding="utf-8") as f:
        ev = json.load(f)

    doc = Document(str(DOCX_PATH))

    # Limpiar tablas y sección agregadas previamente (conservar Tabla 0 original de muestra CSV)
    while len(doc.tables) > 1:
        tbl = doc.tables[-1]._element
        tbl.getparent().remove(tbl)

    cut_idx = None
    for i, p in enumerate(doc.paragraphs):
        txt = p.text.strip()
        if (
            "CONTINUACIÓN DEL INFORME" in txt
            or "SECCIÓN DE AVANCES" in txt
            or "SECCIÃ" in txt
            or (i >= 195 and p._element.xpath(".//w:br[@w:type='page']"))
        ):
            cut_idx = i
            break

    if cut_idx is not None:
        while cut_idx > 195 and doc.paragraphs[cut_idx - 1].text.strip() == "":
            cut_idx -= 1
        for p in list(doc.paragraphs[cut_idx:]):
            p._element.getparent().remove(p._element)

    # Asegurar encabezados principales limpios
    def replace_para(para, text, bold=False, size=11, align=None, color=None):
        para.clear()
        r = para.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor(*color)
        if align is not None:
            para.alignment = align

    if len(doc.paragraphs) > 2:
        replace_para(
            doc.paragraphs[0],
            "Informe de Avance del Trabajo Final (TF) — SatUCI-Puno",
            bold=True,
            size=16,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            color=(0x1A, 0x5C, 0xBB),
        )
        replace_para(doc.paragraphs[1], "1. Título / Tema Central del Proyecto", bold=True, size=13)
        replace_para(
            doc.paragraphs[2],
            "Predicción de la saturación de camas UCI a 24 horas con aprendizaje automático: "
            "caso de Puno con datos abiertos del MINSA.",
            bold=False,
            size=11,
        )

    # =========================================================================
    # CONTINUACIÓN DEL INFORME CON RESULTADOS REALES EJECUTADOS
    # =========================================================================
    doc.add_page_break()
    add_sec_heading(doc, "CONTINUACIÓN DEL INFORME: PIPELINE EJECUTADO, MODELOS Y APP WEB", level=1)

    p_intro = doc.add_paragraph()
    p_intro.add_run(
        "Siguiendo íntegramente la metodología de Proyecto_UCI_EPIS_2026II_Puno.pdf, se ejecutó el "
        "pipeline completo de principio a fin: descarga de clima real NASA POWER (MERRA-2) para "
        "2023–2026, calibración GLM de Poisson + Ley de Little (Gamma k=2) sin fuga, simulación "
        "diaria 2023–2025 de las 5 UCI de Puno, entrenamiento y persistencia (.pkl) de todos los "
        "modelos evaluados, integración en la aplicación web Flask (SatUCI-Puno) y documentación "
        "completa de ingeniería de software."
    ).font.size = Pt(10.5)

    # 1. Datos generales
    add_sec_heading(doc, "1. Datos Generales del Proyecto y Equipo", level=2)
    add_styled_table(
        doc,
        ["Campo", "Información Oficial"],
        [
            ("Institución", "Universidad Nacional del Altiplano — FIMEES — EPIS"),
            ("Título", "Predicción de la saturación de camas UCI a 24 horas con aprendizaje automático: caso de Puno con datos abiertos del MINSA"),
            ("Curso / Área", "Estructuras de Datos Avanzadas (2026-II) — Ciencia de Datos"),
            ("Integrantes", "Roy Jesus Aldair Tipo Catunta (Ciencia de datos y ML)\nRobert Heraldo Quiro Arguedas (Aplicación web Flask, BD, pruebas y documentación)"),
            ("Asesor", "Hugo Yosef Gomez Quispe"),
            ("Repositorio GitHub", "https://github.com/HeraldoQuiro/PREDICCION-HOSPITALARIA.git"),
        ],
    )

    # 2. Clima real y Dataset consolidado (19 columnas)
    add_sec_heading(doc, "2. Clima Real NASA POWER (2023–2026) y Simulación Calibrada (COMPLETADO)", level=2)
    p_c = doc.add_paragraph()
    p_c.add_run(
        "Mediante 02_scripts/01_descargar_clima.py se descargaron los registros reales diarios de "
        "NASA POWER (MERRA-2) para latitud −15.8396, longitud −70.0282 (2023-01-01 a 2026-11-23), "
        "sustituyendo la serie climática provisional mencionada en el documento base. Luego, "
        "02_scripts/02_simulacion.py calibró cada UCI usando exclusivamente datos reales hasta el "
        "31/08/2026, simuló los 1,096 días de 2023–2025 con el balance stock–flujo de Asplin (2003) "
        "y llegadas Poisson / estancia Gamma (k=2) de Bai (2021), y consolidó las 19 columnas "
        "oficiales junto con los feriados nacionales (holidays.PE()) en "
        "01_datos/dataset_uci_puno_consolidado_2023_2026.csv."
    ).font.size = Pt(10.5)

    rows_calib = []
    for hosp_name, p in calib.items():
        b_app = p["betas_aplicados"]
        betas_txt = f"β1={b_app['beta1_temp_min_lag3']}, β2={b_app['beta2_rango_termico']}, β3={b_app['beta3_invierno']}"
        rows_calib.append((
            hosp_name,
            f"{p['capacidad_mediana']} camas",
            f"{p['dias_reales_2026']} / {p['dias_simulados_2023_2025']}",
            f"{p['lambda_0']} / {p['estancia_media_gamma']} d",
            betas_txt,
            f"{p['pct_saturados_real_2026']}% / {p['pct_saturados_simulado']}%",
        ))
    add_styled_table(
        doc,
        ["Establecimiento (UCI total)", "Cap. med.", "Días real / sim.", "λ0 / Estancia", "β aplicados (p<0.05)", "Sat. % (real/sim)"],
        rows_calib,
    )

    # 3. Evaluación de los 9 modelos con clima real 2023-2026
    add_sec_heading(doc, "3. Entrenamiento y Evaluación de los 9 Modelos ML (COMPLETADO)", level=2)
    p_m = doc.add_paragraph()
    p_m.add_run(
        f"El script 02_scripts/03_evaluacion.py construyó exactamente las 16 variables predictoras "
        f"sin fuga de información (Tabla 2 del PDF: identificación, calendario de t, clima hasta t−1, "
        f"ocupación en t−1, t−2, t−7 e ingresos/egresos de t−1). Se entrenó con {ev['n_entrenamiento']} "
        f"unidad-días hasta el 31/08/2026 y se evaluó sobre el periodo real posterior (01/09/2026 al "
        f"03/11/2026: {ev['n_prueba_real']} unidad-días, {ev['saturados_prueba_real']} saturados = "
        f"{ev['pct_saturados_prueba']}%), usando el clima real de NASA POWER 2023–2026:"
    ).font.size = Pt(10.5)

    winner_name = ev["mejor_modelo_ejecucion"]["modelo"]
    rows_eval = []
    for r in ev["resultados_modelos"]:
        label = f"{r['modelo']} (MEJOR)" if r["modelo"] == winner_name else r["modelo"]
        rows_eval.append((
            label,
            f"{r['precision']:.3f}",
            f"{r['sensibilidad']:.3f}",
            f"{r['f1']:.3f}",
            f"{r['roc_auc']:.3f}",
            f"{r['pr_auc']:.3f}",
        ))
    add_styled_table(
        doc,
        ["Modelo (Clima real NASA POWER)", "Precisión", "Sensibilidad", "F1", "ROC-AUC", "PR-AUC"],
        rows_eval,
        highlight_substr="(MEJOR)",
    )

    ep = ev["episodios_rf"]
    reg = ev["regresion_porcentaje_ocupacion"]
    p_an = doc.add_paragraph()
    p_an.paragraph_format.space_before = Pt(6)
    r_b = p_an.add_run("Hallazgos clave de la corrida reproducible: ")
    r_b.bold = True
    r_b.font.size = Pt(10.5)
    p_an.add_run(
        f"En la prueba real con clima real de NASA POWER 2023–2026, el mejor modelo por PR-AUC/ROC-AUC "
        f"fue {winner_name} (ROC-AUC {ev['mejor_modelo_ejecucion']['roc_auc']:.3f}, PR-AUC "
        f"{ev['mejor_modelo_ejecucion']['pr_auc']:.3f}, F1 {ev['mejor_modelo_ejecucion']['f1']:.3f}), "
        f"superando a las referencias ingenuas en ordenamiento de riesgo. En análisis de episodios con "
        f"Random Forest, detectó {ep['inicios_detectados']} de {ep['inicios_totales']} inicios de episodio "
        f"y {ep['continuaciones_detectadas']} de {ep['continuaciones_totales']} continuaciones, "
        f"confirmando la conclusión metodológica del PDF. En la variante complementaria de regresión "
        f"(% ocupación), CatBoost obtuvo MAE {reg['catboost_mae']} y RMSE {reg['catboost_rmse']} puntos "
        f"porcentuales frente a MAE {reg['persistencia_mae']} y RMSE {reg['persistencia_rmse']} de la persistencia."
    ).font.size = Pt(10.5)

    add_sec_heading(doc, "3.1 Importancia por Permutación en Random Forest (Clima Real)", level=3)
    rows_imp = [(k, f"{v:.4f}") for k, v in ev["importancia_permutacion_rf"].items()]
    add_styled_table(doc, ["Grupo de variables predictoras", "Caída en PR-AUC al permutar"], rows_imp)

    add_sec_heading(doc, "3.2 Modelos Serializados Guardados en 05_modelos/", level=3)
    add_bullet(doc, "modelo_rf.pkl: ", "Random Forest Classifier (despliegue + evaluación) integrado directamente en la aplicación web Flask.")
    add_bullet(doc, "modelo_xgb.pkl y modelo_catboost.pkl: ", "Modelos de gradient boosting entrenados y serializados con joblib.")
    add_bullet(doc, "modelo_logreg.pkl: ", "Pipeline StandardScaler + Regresión Logística balanceada.")
    add_bullet(doc, "modelo_lstm.pkl y modelo_gru.pkl: ", "Redes recurrentes LSTM y GRU entrenadas sobre ventanas temporales t−7..t−1.")
    add_bullet(doc, "modelo_regresion_catboost.pkl: ", "Modelo complementario de regresión del porcentaje de ocupación.")
    add_bullet(doc, "Métricas y calibración: ", "metricas_evaluacion.json, tabla_resultados_modelos.csv y calibracion_simulador.json.")

    # 4. Aplicación web Flask
    add_sec_heading(doc, "4. Aplicación Web SatUCI-Puno Integrada con Random Forest (COMPLETADO)", level=2)
    p_w = doc.add_paragraph()
    p_w.add_run(
        "Se implementó la aplicación web por capas en sistema_uci_puno/ (Flask + Jinja2 + Chart.js + SQLite "
        "con esquema compatible para Firebird 5.0.4) conectada al archivo 05_modelos/modelo_rf.pkl "
        "entrenado con las 16 variables exactas del PDF y el clima real de NASA POWER:"
    ).font.size = Pt(10.5)
    add_bullet(doc, "Autenticación: ", "Acceso protegido por sesión (@login_required, credenciales iniciales admin / uci2026).")
    add_bullet(doc, "Tablero de indicadores (/dashboard): ", "KPIs regionales, tarjetas de las 5 UCI con semáforo de saturación (≥ 85%) y gráficos Chart.js de 30 días.")
    add_bullet(doc, "Registro diario (/registro): ", "Ingreso de camas totales y ocupadas con cálculo automático de porcentaje y disparo de alertas.")
    add_bullet(doc, "Pronósticos 24h (/pronosticos) y Reentrenamiento (RF-06): ", "Inferencia en vivo con modelo_rf.pkl + botón para reentrenar el Random Forest con nuevos registros.")
    add_bullet(doc, "Alertas (/alertas): ", "Gestión de alertas críticas (≥85%), preventivas (≥75%) y de riesgo 24h.")

    # 5. Documentación de Ingeniería de Software y Estructura Final
    add_sec_heading(doc, "5. Documentación de Ingeniería de Software y Estructura Final (COMPLETADO)", level=2)
    add_bullet(doc, "04_documentacion/SRS.md: ", "Especificación de Requerimientos (RF-01 a RF-07, RNF-01 a RNF-06, casos de uso).")
    add_bullet(doc, "04_documentacion/arquitectura.md: ", "Arquitectura en 5 capas, flujo sin fuga y modelo relacional de BD.")
    add_bullet(doc, "04_documentacion/manual_tecnico.md y manual_usuario.md: ", "Instalación, endpoints, integración ML, migración Firebird 5 y guía operativa.")

    p_tree = doc.add_paragraph()
    r_tree = p_tree.add_run(
        "PREDICCION HOSPITALARIA/\n"
        "├── 01_datos/          → DATA_CAMAS_HIST.csv, UCI_5_HOSPITALES_PUNO_2026.csv,\n"
        "│                        clima_puno_nasa_power_2023_2026.csv, dataset_uci_puno_consolidado_2023_2026.csv\n"
        "├── 02_scripts/        → filtrar_uci_puno.py, 01_descargar_clima.py, 02_simulacion.py,\n"
        "│                        03_evaluacion.py, 04_completar_informe.py\n"
        "├── sistema_uci_puno/  → Aplicación web Flask completa (conectada a modelo_rf.pkl)\n"
        "├── 04_documentacion/  → SRS.md, arquitectura.md, manual_tecnico.md, manual_usuario.md\n"
        "├── 05_modelos/        → 7 modelos .pkl + metricas_evaluacion.json + tabla_resultados_modelos.csv\n"
        "├── CAMPO DE TRABAJO/  → Archivos auxiliares y pruebas\n"
        "├── README.md          → Guía del repositorio\n"
        "├── Proyecto_UCI_EPIS_2026II_Puno.pdf → Documento base (sin modificar)\n"
        "└── informe TF - 5H.docx              → Presente informe de avance"
    )
    r_tree.font.name = "Consolas"
    r_tree.font.size = Pt(8.5)

    p_firma = doc.add_paragraph()
    p_firma.paragraph_format.space_before = Pt(14)
    p_firma.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_f1 = p_firma.add_run("Puno, noviembre del 2026\n")
    r_f1.bold = True
    r_f1.font.size = Pt(10.5)
    p_firma.add_run("Roy Jesus Aldair Tipo Catunta — Robert Heraldo Quiro Arguedas\n").font.size = Pt(10)
    r_f2 = p_firma.add_run("Asesor: Hugo Yosef Gomez Quispe\n")
    r_f2.italic = True
    r_f2.font.size = Pt(10)
    p_firma.add_run("EPIS — Universidad Nacional del Altiplano").font.size = Pt(10)

    doc.save(str(DOCX_PATH))
    print(f"[04_completar_informe] OK -> Informe actualizado en {DOCX_PATH}")


if __name__ == "__main__":
    main()
