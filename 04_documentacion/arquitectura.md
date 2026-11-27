# Documento de Arquitectura del Sistema
## Sistema SatUCI-Puno — Predicción de Saturación de Camas UCI

**Versión:** 1.0 | **Fecha:** Noviembre 2026  
**Proyecto:** Predicción UCI Puno EPIS 2026-II, Universidad Nacional del Altiplano

---

## 1. Vista General de la Arquitectura

El sistema sigue una arquitectura de **3 capas** (presentación, lógica de negocio y datos), implementada con Flask y organizada en módulos por responsabilidad.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                         │
│   Jinja2 Templates (HTML)  +  CSS  +  JavaScript + Chart.js    │
│   login.html | dashboard.html | registro.html | alertas.html   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (Flask routes)
┌──────────────────────────▼──────────────────────────────────────┐
│                   CAPA DE LÓGICA DE NEGOCIO                     │
│                                                                 │
│  ┌─────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │  app.py     │  │   services/      │  │      ml/          │  │
│  │  (Rutas y   │  │  data_service.py │  │  predictor.py     │  │
│  │   sesión)   │  │  dashboard_svc   │  │  mock_predictor   │  │
│  │             │  │  alert_service   │  │  modelo RF .pkl   │  │
│  └─────────────┘  └──────────────────┘  └───────────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     CAPA DE DATOS                               │
│                                                                 │
│  ┌────────────────────┐    ┌────────────────────────────────┐   │
│  │  SQLite (dev)      │    │  Archivos CSV                  │   │
│  │  uci_puno.db       │    │  UCI_5_HOSPITALES_PUNO_2026.csv│   │
│  │  Firebird 5 (prod) │    │  (datos reales MINSA 2026)     │   │
│  └────────────────────┘    └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Diagrama de Componentes

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      SISTEMA SatUCI-Puno                    │
 │                                                             │
 │  ┌──────────────┐    ┌────────────────────────────────────┐ │
 │  │  Autenticación│    │          Dashboard                 │ │
 │  │  Flask Session│    │  - KPIs globales                   │ │
 │  │  Login/Logout │    │  - Tarjetas por hospital           │ │
 │  └──────────────┘    │  - Gráfica de tendencia (Chart.js) │ │
 │                       └────────────────────────────────────┘ │
 │  ┌──────────────────────────────────────────────────────────┐ │
 │  │                   Módulo ML                              │ │
 │  │  Entrada: 16 features (ocup. t-1,t-2,t-7, clima, cal.)  │ │
 │  │  Modelo: Random Forest (.pkl, joblib)                    │ │
 │  │  Salida: P(saturación mañana) por UCI                    │ │
 │  └──────────────────────────────────────────────────────────┘ │
 │                                                             │
 │  ┌──────────────────┐    ┌──────────────────────────────┐  │
 │  │  Registro Diario │    │        Alertas               │  │
 │  │  Formulario HTML │    │  🟡 Alerta: 70-84%           │  │
 │  │  → SQLite/Firebird│    │  🔴 Saturación: ≥85%        │  │
 │  └──────────────────┘    └──────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
```

---

## 3. Diagrama de Flujo de Datos

```
Fuentes externas:
┌─────────────────┐
│  MINSA-REUNIS   │──► DATA_CAMAS_HIST.csv ──► filtrar_uci_puno.py
│  (datos 2026)   │                             │
└─────────────────┘                             ▼
                                    UCI_5_HOSPITALES_PUNO_2026.csv
┌─────────────────┐                             │
│  NASA POWER     │──► Clima diario Puno        │
│  (temperatura   │    (temp_min, temp_max,     │
│   y humedad)    │     humedad_relativa)       │
└─────────────────┘             │               │
                                ▼               ▼
                          ┌─────────────────────────────┐
                          │     Simulación 2023-2025     │
                          │  (Poisson ingresos, Gamma    │
                          │   estancia, balance flujo)  │
                          └─────────────┬───────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────┐
                          │    Dataset Consolidado       │
                          │  6618 unidad-días entrena.   │
                          │  294 unidad-días prueba      │
                          └─────────────┬───────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────┐
                          │   Entrenamiento ML           │
                          │  Random Forest (ganador)     │
                          │  ROC-AUC: 0.911              │
                          │  PR-AUC: 0.592               │
                          └─────────────┬───────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────┐
                          │   modelo_rf.pkl (joblib)     │
                          │   Cargado por predictor.py   │
                          └─────────────┬───────────────┘
                                        │
                                        ▼
                          ┌─────────────────────────────┐
                          │   App Web Flask              │
                          │   Dashboard + Alertas        │
                          │   + Pronósticos              │
                          └─────────────────────────────┘
```

---

## 4. Modelo de Base de Datos (Esquema SQLite)

### Tabla: `usuarios`
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | Identificador único |
| username | TEXT | Nombre de usuario |
| password_hash | TEXT | Contraseña hasheada (werkzeug) |
| rol | TEXT | 'admin' o 'personal' |
| creado_en | DATETIME | Fecha de creación |

### Tabla: `hospitales`
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | Identificador único |
| codigo | TEXT | Código MINSA |
| nombre | TEXT | Nombre del establecimiento |
| institucion | TEXT | Gobierno Regional, Clínica, etc. |
| capacidad_camas | INTEGER | Camas UCI totales |
| latitud | REAL | Coordenada geográfica |
| longitud | REAL | Coordenada geográfica |

### Tabla: `registros_diarios`
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | Identificador único |
| hospital_id | INTEGER FK | Referencia a hospitales |
| fecha | DATE | Fecha del registro |
| camas_totales | INTEGER | Total de camas habilitadas |
| camas_ocupadas | INTEGER | Camas ocupadas ese día |
| porcentaje_ocupacion | REAL | % calculado |
| estado_saturacion | INTEGER | 1=Saturado (≥85%), 0=Normal |
| ingresos_dia | INTEGER | Pacientes que ingresaron |
| egresos_dia | INTEGER | Pacientes que salieron |
| registrado_por | INTEGER FK | Usuario que registró |
| registrado_en | DATETIME | Timestamp del registro |

### Tabla: `pronosticos`
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | Identificador único |
| hospital_id | INTEGER FK | Referencia a hospitales |
| fecha_prediccion | DATE | Día que se predice |
| prob_saturacion | REAL | Probabilidad (0.0 a 1.0) |
| clase_predicha | INTEGER | 1=Saturado, 0=No saturado |
| modelo_version | TEXT | Versión del modelo usado |
| generado_en | DATETIME | Timestamp de generación |

### Tabla: `alertas`
| Columna | Tipo | Descripción |
|---|---|---|
| id | INTEGER PK | Identificador único |
| hospital_id | INTEGER FK | Referencia a hospitales |
| tipo_alerta | TEXT | 'ALERTA' (70-84%) o 'SATURACION' (≥85%) |
| porcentaje | REAL | % que disparó la alerta |
| fecha | DATE | Fecha de la alerta |
| activa | INTEGER | 1=Activa, 0=Resuelta |

---

## 5. Diagrama de Despliegue

```
┌─────────────────────────────────────────┐
│          Computadora del equipo         │
│          (Windows / Ubuntu)             │
│                                         │
│  ┌──────────────────────────────────┐   │
│  │    Python 3.11 + Flask 2.3.3     │   │
│  │    Puerto: 5000 (dev)            │   │
│  │                                  │   │
│  │  app.py                          │   │
│  │  services/ | ml/ | templates/    │   │
│  │  static/   | database/           │   │
│  │                                  │   │
│  │  uci_puno.db (SQLite)            │   │
│  │  modelo_rf.pkl (joblib)          │   │
│  └──────────────┬───────────────────┘   │
│                 │                       │
│          localhost:5000                 │
└─────────────────┼───────────────────────┘
                  │
         ┌────────▼────────┐
         │  Navegador Web  │
         │  Chrome/Firefox │
         └─────────────────┘
```

**Para producción futura:**
- Reemplazar SQLite por **Firebird 5.0.4** (esquema compatible en `schema_firebird.sql`)
- Usar **Gunicorn** como servidor WSGI
- Desplegar en servidor del hospital o nube (DigitalOcean, AWS EC2)

---

## 6. Tecnologías y Versiones

| Tecnología | Versión | Uso |
|---|---|---|
| Python | 3.11+ | Lenguaje principal |
| Flask | 2.3.3 | Framework web |
| Jinja2 | (incluido en Flask) | Plantillas HTML |
| pandas | 3.0.6 | Manejo de datos |
| scikit-learn | 1.9.1 | Random Forest, métricas |
| XGBoost | 3.4.1 | Modelo alternativo |
| CatBoost | 1.2.10 | Modelo alternativo |
| joblib | — | Serialización .pkl |
| SQLite | 3.x | Base de datos desarrollo |
| Firebird | 5.0.4 | Base de datos producción |
| Chart.js | 4.x | Gráficas en frontend |
| JavaScript | ES6+ | Interactividad frontend |

---

## 7. Decisiones de Diseño

### 7.1 ¿Por qué Random Forest y no LSTM/GRU?
Con el dataset disponible (~6618 unidad-días de entrenamiento), Random Forest superó a las redes recurrentes en ROC-AUC (0.911 vs 0.882-0.893) y PR-AUC (0.592 vs 0.508-0.547). Las redes recurrentes requieren más datos para superar modelos de árbol.

### 7.2 ¿Por qué simulación y no solo datos reales?
Los datos públicos del MINSA (REUNIS) solo cubren 2026 — un año insuficiente para entrenar modelos robustos. Se simula el historial 2023-2025 con un balance de stock y flujo calibrado con los datos reales de 2026 (Asplin et al., 2003; Bai, 2021).

### 7.3 ¿Por qué SQLite en desarrollo?
Facilita la instalación y pruebas sin necesitar Firebird. El esquema es compatible con migración posterior a Firebird 5 (producción).

### 7.4 ¿Por qué no usar datos de pacientes individuales?
El sistema usa solo datos agregados (camas totales, ocupadas, % diario) de acceso público. No requiere acceso a historiales clínicos confidenciales.

---

*Documento de Arquitectura — Proyecto UCI Puno EPIS 2026-II*  
*Universidad Nacional del Altiplano — Escuela Profesional de Ingeniería de Sistemas*
