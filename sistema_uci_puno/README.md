# SatUCI-Puno: Sistema de Predicción de Saturación de Camas UCI a 24 Horas

Aplicación Web de monitoreo y predicción anticipatoria de saturación hospitalaria en Unidades de Cuidados Intensivos (UCI) para la región Puno, Perú.

Desarrollado en el marco del curso **Estructuras de Datos Avanzadas (2026-II)** de la **Universidad Nacional del Altiplano (UNAP)**, Escuela Profesional de Ingeniería de Sistemas (EPIS).

---

## 👥 Equipo de Desarrollo

- **Roy Aldair Tipo Catunta** — *Modelos de Machine Learning y Ciencia de Datos*
- **Robert Heraldo Quiro Arguedas** — *Aplicación Web Full-Stack (Flask, HTML5, CSS3, JS, SQLite)*
- **Docente Asesor:** Hugo Yosef Gomez Quispe
- **Institución:** Universidad Nacional del Altiplano (Puno, Perú) — EPIS

---

## 🎯 Contexto y Problema a Resolver

Las Unidades de Cuidados Intensivos (UCI) cuentan con una capacidad crítica de camas. Cuando una unidad alcanza el **85% o más de ocupación** (*Litvak & Bisognano, 2011, Health Affairs*), se produce un cuello de botella asistencial que retrasa admisiones urgentes y eleva la tasa de morbimortalidad.

Tradicionalmente, la gestión hospitalaria reacciona cuando las camas ya están colapsadas. **SatUCI-Puno** utiliza modelos de aprendizaje automático para predecir con **24 horas de ventaja anticipatoria** ($t$) si una unidad entrará en saturación, permitiendo a los comités de gestión y al **CRUE/SAMU Puno** coordinar derivaciones y pre-altas a tiempo.

---

## 🏥 Los 5 Establecimientos UCI de la Región Puno (REUNIS 2026)

| Código | Establecimiento de Salud | Institución | Ciudad | Camas UCI | Nivel |
|---|---|---|---|---|---|
| **3299** | CARLOS MONJE MEDRANO | GOBIERNO REGIONAL | Juliaca | 3 camas (mediana 2026) | MINSA / GORE |
| **10815** | CLÍNICA ADVENTISTA AMERICANA | PRIVADO | Juliaca | 2 camas | II-1 |
| **11978** | CLÍNICA MONTE SINAI | PRIVADO | Juliaca | 1 cama | II-1 |
| **3251** | HOSPITAL REGIONAL MANUEL NUÑEZ BUTRÓN | GOBIERNO REGIONAL | Puno | 6 camas | III-1 |
| **31179** | HOSPITAL SAN MARTÍN DE PORRES | GOBIERNO REGIONAL | Macusani / Carabaya | 9 camas | II-1 |

---

## 🧠 Desempeño del Modelo de Machine Learning

El sistema implementa el modelo campeón seleccionado tras validación cruzada y benchmarking:

- **Algoritmo:** **Random Forest Classifier** (optimizado con class-weighting balanceado)
- **ROC-AUC:** `0.911` (Excelente poder de discriminación entre saturado / no saturado)
- **PR-AUC:** `0.592` (Alta precisión en la clase minoritaria de saturación)
- **F1-Score:** `0.625`
- **Horizonte de Inferencia:** 24 horas ($t$), alimentado exclusivamente con información conocida hasta $t-1$ para evitar fuga de datos (*data leakage*).
- **16 Variables Predictoras:**
  1. Rezagos de ocupación histórica: `ocupacion_lag1`, `ocupacion_lag2`, `ocupacion_lag3`, `ocupacion_lag7`
  2. Dinámica de flujo: `velocidad_3d`, `media_movil_7d`, `camas_ocupadas_lag1`, `ratio_capacidad`
  3. Clima altiplánico (NASA POWER / SENAMHI): `temp_min_lag1`, `rango_termico_lag1`
  4. Calendario y estacionalidad: `dia_semana`, `es_fin_semana`, `mes`
  5. Identificación: `camas_totales`, `codigo_hospital`, `tipo_institucion`

---

## 📁 Estructura del Proyecto Web

```
sistema_uci_puno/
├── app.py                    # Aplicación principal Flask, rutas y APIs
├── config.py                 # Configuración centralizada, rutas y constantes
├── requirements.txt          # Dependencias de Python
├── README.md                 # Documentación completa y manual de usuario
├── database/
│   ├── schema.sql            # Esquema DDL de SQLite
│   └── init_db.py            # Inicializador de BD y carga de los 1,560 registros 2026
├── ml/
│   ├── predictor.py          # Carga y ejecución del modelo Random Forest (.pkl)
│   └── mock_predictor.py     # Predictor estadístico calibrado de fallback
├── services/
│   ├── data_service.py       # Consultas SQL, persistencia y series de tiempo
│   ├── dashboard_service.py  # Agregación ejecutiva de KPIs y estados
│   └── alert_service.py      # Motor de reglas y alertas de saturación
├── templates/
│   ├── base.html             # Layout base con sidebar neón y topbar
│   ├── login.html            # Pantalla de inicio de sesión con glassmorphism
│   ├── dashboard.html        # Tablero de control interactivo con Chart.js
│   ├── registro.html         # Formulario de registro diario con cálculo en vivo
│   ├── pronosticos.html      # Tabla de predicciones a 24h y métricas ML
│   ├── alertas.html          # Listado y gestión de alertas de saturación
│   ├── 404.html              # Manejo de error 404
│   └── 500.html              # Manejo de error 500
└── static/
    ├── css/
    │   └── style.css         # Dark mode, glassmorphism y diseño neón
    └── js/
        └── main.js           # Gráficas Chart.js y dinamismo del frontend
```

---

## 🚀 Instalación y Puesta en Marcha

### Prerrequisitos
- Python 3.10 o superior (recomendado Python 3.11+)
- Gestor de paquetes `pip`

### 1. Navegar a la carpeta de la aplicación
```bash
cd "C:\PROJECTS\PREDICCION HOSPITALARIA\sistema_uci_puno"
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Inicializar la Base de Datos
El script `init_db.py` crea las tablas SQLite, registra los 5 hospitales, el usuario administrador y carga los **1,560 registros reales de 2026** desde `UCI_5_HOSPITALES_PUNO_2026.csv`:
```bash
python database/init_db.py
```
*(Nota: Si no se ejecuta manualmente, `app.py` lo inicializará automáticamente en su primer arranque).*

### 4. Iniciar el servidor web
```bash
python app.py
```

### 5. Acceder en el navegador
Abra su navegador web e ingrese a:
👉 **`http://localhost:5000`**

---

## 🔑 Credenciales de Acceso por Defecto

- **Usuario:** `admin`
- **Contraseña:** `uci2026`

*Todas las rutas del sistema (excepto `/login`) están estrictamente protegidas por sesión criptográfica de Flask.*

---

## 🎨 Características de Diseño y UI/UX

- **Dark Mode + Glassmorphism:** Fondo deep navy (`#0a0e1a`) con tarjetas en vidrio esmerilado (`backdrop-filter: blur(16px)`).
- **Paleta de Colores de Alta Tecnología:**
  - Acento principal: Teal neón (`#00d4ff`)
  - Alerta crítica / Saturación: Rojo carmesí (`#ff4757`) con pulso de luz animado
  - Advertencia preventiva: Ámbar (`#f59e0b`)
  - Estado óptimo: Esmeralda (`#10b981`)
- **Visualización con Chart.js:**
  - Gráfica multi-serie de evolución a 30, 14 y 7 días con línea discontinua de umbral al 85%.
  - Gráfica apilada de distribución de camas ocupadas vs. disponibles.
- **Registro Interactivo:** Cálculo dinámico en tiempo real de porcentaje de ocupación, camas disponibles y estado mientras el usuario tipea.
- **Reloj Digital en Vivo:** Muestra la hora local de Puno con punto pulsante en el topbar.

---

## 🔄 Guía de Migración a Firebird 5 en Producción

Para el despliegue en servidores hospitalarios de producción donde se requiera **Firebird 5.0.4+** en lugar de SQLite:

1. **Instalar el driver oficial de Firebird para Python:**
   ```bash
   pip install firebird-driver
   ```

2. **Diferencias de sintaxis DDL (SQLite vs Firebird 5 Dialecto 3):**
   - Reemplazar `INTEGER PRIMARY KEY AUTOINCREMENT` por:
     ```sql
     BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY
     ```
   - Reemplazar `BOOLEAN` / `INTEGER` para flags por:
     ```sql
     SMALLINT DEFAULT 0 CHECK (activo IN (0, 1))
     ```
   - Reemplazar `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` por:
     ```sql
     TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
     ```

3. **Cadena de conexión Firebird:**
   En `config.py`, cambiar `DATABASE_PATH` por:
   ```python
   FIREBIRD_DSN = "localhost/3050:C:/PROJECTS/PREDICCION HOSPITALARIA/database/UCI_PUNO.FDB"
   FIREBIRD_USER = "SYSDBA"
   FIREBIRD_PASSWORD = "masterkey"
   ```

4. **Conexión en `data_service.py`:**
   ```python
   from firebird.driver import connect, driver_config
   conn = connect(
       database=Config.FIREBIRD_DSN,
       user=Config.FIREBIRD_USER,
       password=Config.FIREBIRD_PASSWORD,
       charset='UTF8'
   )
   ```

---

*Proyecto desarrollado para el curso Estructuras de Datos Avanzadas — Semestre 2026-II — EPIS UNAP.*
