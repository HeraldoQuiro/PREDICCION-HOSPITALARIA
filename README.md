# 🏥 SatUCI-Puno — Predicción de Saturación de Camas UCI
## Proyecto de Trabajo Final — Estructuras de Datos Avanzadas 2026-II
### Universidad Nacional del Altiplano — EPIS (Ingeniería de Sistemas)

---

## Descripción

Sistema de predicción con aprendizaje automático que anticipa con **24 horas de anticipación** si una Unidad de Cuidados Intensivos (UCI) de los 5 principales establecimientos de salud de Puno entrará en **estado de saturación** (ocupación ≥ 85%).

**Resultado del modelo ganador (Random Forest):**
- ROC-AUC: **0.911** (+12.8% vs referencia)
- PR-AUC: **0.592** (+15.0% vs referencia)
- F1: **0.625**

---

## Equipo

| Nombre | Rol | Contacto |
|---|---|---|
| Roy Jesus Aldair Tipo Catunta | Líder · Ciencia de datos (ML) | aldairtc123456@gmail.com |
| Robert Heraldo Quiro Arguedas | Desarrollo de app web (Flask + BD) | heraldoquiroarguedas@gmail.com |
| Hugo Yosef Gomez Quispe | Asesor metodológico | — |

---

## Estructura del Proyecto

```
PREDICCION HOSPITALARIA/
├── 📁 01_datos/
│   ├── DATA_CAMAS_HIST.csv                          # Dataset completo MINSA (~19 MB)
│   ├── UCI_5_HOSPITALES_PUNO_2026.csv               # Datos filtrados: 5 UCI Puno (1,558 registros)
│   ├── clima_puno_nasa_power_2023_2026.csv          # ✅ Clima diario real NASA POWER MERRA-2 (2023–2026)
│   └── dataset_uci_puno_consolidado_2023_2026.csv   # ✅ Dataset consolidado 19 columnas (7,038 registros)
│
├── 📁 02_scripts/
│   ├── filtrar_uci_puno.py              # ✅ Filtrado datos MINSA → 5 hospitales Puno
│   ├── 01_descargar_clima.py            # ✅ Descarga clima real NASA POWER 2023-2026
│   ├── 02_simulacion.py                 # ✅ Calibración GLM Poisson/Gamma y simulación 2023-2025
│   ├── 03_evaluacion.py                 # ✅ Entrenamiento y evaluación temporal de los 9 modelos
│   └── 04_completar_informe.py          # ✅ Actualización automática de informe TF - 5H.docx
│
├── 📁 sistema_uci_puno/                 # ✅ Aplicación web Flask (integrada con modelo_rf.pkl)
│   ├── app.py                           # Punto de entrada
│   ├── requirements.txt                 # Dependencias Python
│   ├── config.py                        # Configuración
│   ├── database/ | ml/ | services/      # Capas de la app
│   ├── templates/                       # HTML Jinja2
│   └── static/                          # CSS + JS (dark mode, Chart.js)
│
├── 📁 04_documentacion/
│   ├── SRS.md                           # ✅ Especificación de Requerimientos
│   ├── arquitectura.md                  # ✅ Documento de Arquitectura
│   ├── manual_tecnico.md                # ✅ Manual Técnico (instalación)
│   └── manual_usuario.md                # ✅ Manual de Usuario
│
├── 📁 05_modelos/
│   ├── modelo_rf.pkl                    # ✅ Random Forest entrenado (usado por la app web)
│   ├── modelo_xgb.pkl                   # ✅ XGBoost entrenado
│   ├── modelo_catboost.pkl              # ✅ CatBoost entrenado
│   ├── modelo_logreg.pkl                # ✅ Regresión logística entrenada
│   ├── modelo_lstm.pkl                  # ✅ Red LSTM entrenada (ventana t-7..t-1)
│   ├── modelo_gru.pkl                   # ✅ Red GRU entrenada (ventana t-7..t-1)
│   ├── modelo_regresion_catboost.pkl    # ✅ Regresión % ocupación (CatBoost)
│   ├── metricas_evaluacion.json         # ✅ Métricas completas de evaluación
│   └── tabla_resultados_modelos.csv     # ✅ Tabla comparativa de los 9 modelos
│
├── 📁 CAMPO DE TRABAJO/                 # Archivos temporales y pruebas
│
├── informe TF - 5H.docx                 # ✅ Informe de avance actualizado
└── Proyecto_UCI_EPIS_2026II_Puno.pdf    # Documento base del proyecto
```

> ✅ = Completado | ⬜ = Pendiente

---

## Inicio Rápido — App Web

```bash
# 1. Instalar dependencias
cd sistema_uci_puno
pip install -r requirements.txt

# 2. Inicializar base de datos con datos reales
python database/init_db.py

# 3. Ejecutar la app
python app.py

# 4. Abrir en el navegador
# http://localhost:5000
# Usuario: admin | Contraseña: uci2026
```

---

## Los 5 Hospitales UCI de Puno

| Hospital | Institución | Camas UCI (mediana 2026) | Días reales 2026 (Tabla 4 PDF) |
|---|---|---|---|
| Hospital Regional Manuel Núñez Butrón | Gobierno Regional | 6 | 267 |
| Hospital Carlos Monje Medrano | Gobierno Regional | 3 | 307 |
| Clínica Adventista Americana de Juliaca | Privada | 2 | 300 |
| Clínica Monte Sinaí Juliaca | Privada | 1 | 269 |
| Hospital San Martín de Porres | Gobierno Regional | 9 | 306 |

---

## Tecnologías

- **ML:** scikit-learn (Random Forest), XGBoost, CatBoost, JAX (LSTM/GRU)
- **App Web:** Flask 2.3.3, Jinja2, JavaScript, Chart.js
- **BD:** SQLite (desarrollo) → Firebird 5.0.4 (producción)
- **Datos:** MINSA-REUNIS, NASA POWER (MERRA-2), holidays.PE()

---

## Repositorio

🔗 https://github.com/HeraldoQuiro/PREDICCION-HOSPITALARIA.git

---

## Referencias Bibliográficas clave

- Asplin et al. (2003). Modelo Entrada-Proceso-Salida UCI.
- Bai, J. (2021). Distribuciones Poisson (ingresos) y Gamma (estancia).
- Litvak & Bisognano (2011). Umbral de saturación crítica 85%.
- Morley et al. (2018). Revisión sistemática 102 estudios UCI.
- Shaibani et al. (2025). AI para predicción de saturación hospitalaria.
