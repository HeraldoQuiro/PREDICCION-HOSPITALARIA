# Especificación de Requerimientos de Software (SRS)
## Sistema de Predicción de Saturación de Camas UCI — Puno 2026

**Versión:** 1.0  
**Fecha:** Noviembre 2026  
**Autores:** Roy Aldair Tipo Catunta · Robert Heraldo Quiro Arguedas  
**Asesor:** Hugo Yosef Gomez Quispe  
**Institución:** Universidad Nacional del Altiplano — EPIS  
**Curso:** Estructuras de Datos Avanzadas, 2026-II  

---

## 1. Introducción

### 1.1 Propósito

Este documento especifica los requerimientos funcionales y no funcionales del sistema web de predicción de saturación de camas UCI para establecimientos de salud de la región Puno. El sistema anticipa con 24 horas de anticipación si una Unidad de Cuidados Intensivos entrará en estado de saturación (ocupación ≥ 85%).

### 1.2 Alcance del Sistema

El sistema se denomina **SatUCI-Puno** y comprende:

- Un módulo de ciencia de datos (simulación, entrenamiento de modelos ML)
- Una aplicación web Flask con tablero de indicadores, registro diario, pronósticos y alertas
- Una base de datos (SQLite para desarrollo, Firebird 5 para producción)

### 1.3 Definiciones y Acrónimos

| Término | Definición |
|---|---|
| UCI | Unidad de Cuidados Intensivos |
| Saturación | Estado en que la ocupación de camas ≥ 85% |
| t-1 | Día anterior al día que se predice |
| ROC-AUC | Área bajo la curva ROC (métrica de clasificación) |
| PR-AUC | Área bajo la curva Precisión-Recall |
| REUNIS | Sistema de información del MINSA |
| MINSA | Ministerio de Salud del Perú |

---

## 2. Descripción General del Sistema

### 2.1 Perspectiva del Sistema

```
[Fuentes de datos]          [Módulo ML]           [App Web]
  MINSA-REUNIS   ──────►  Simulación 2023-25  ──► Dashboard
  NASA POWER     ──────►  Entrenamiento RF    ──► Pronósticos
  Feriados PE    ──────►  Modelo .pkl         ──► Alertas
                          predictor.py        ──► Registro
```

### 2.2 Usuarios del Sistema

| Rol | Descripción |
|---|---|
| Administrador | Acceso completo: datos, modelos, configuración |
| Personal de salud | Acceso a dashboard, registro diario y alertas |

### 2.3 Restricciones

- El sistema usa únicamente datos agregados y públicos (no datos clínicos ni personales)
- El horizonte de predicción es exactamente 24 horas
- Solo cubre las 5 UCI de Puno con reporte activo en REUNIS (año 2026)

---

## 3. Requerimientos Funcionales

### RF-01: Autenticación de Usuarios
- **Descripción:** El sistema debe permitir el inicio de sesión con usuario y contraseña.
- **Entrada:** Credenciales de usuario (email/username + contraseña).
- **Salida:** Sesión iniciada o mensaje de error.
- **Prioridad:** Alta

### RF-02: Dashboard Principal
- **Descripción:** Mostrar en tiempo real el estado de ocupación de las 5 UCI de Puno.
- **Contenido:**
  - Tarjeta por hospital: nombre, % de ocupación actual, estado (Normal/Alerta/Saturado)
  - KPIs globales: hospitales monitoreados, hospitales saturados hoy, ocupación promedio
  - Gráfica de tendencia de ocupación de los últimos 30 días
- **Prioridad:** Alta

### RF-03: Registro Diario de Datos
- **Descripción:** Formulario para ingresar datos diarios de cada UCI.
- **Campos:**
  - Hospital (selector de los 5 establecimientos)
  - Fecha del registro
  - Camas totales habilitadas
  - Camas ocupadas
  - (Calculado automáticamente: % de ocupación, estado de saturación)
- **Prioridad:** Alta

### RF-04: Pronósticos de Saturación a 24 horas
- **Descripción:** Mostrar la probabilidad predicha de saturación para el día siguiente por UCI.
- **Modelo usado:** Random Forest (cargado desde archivo .pkl)
- **Variables de entrada:** 16 predictores (ocupación t-1, t-2, t-7, ingresos/egresos t-1, clima t-1, calendario t, identificación)
- **Salida:** Probabilidad (0–100%) y clase predicha (Saturado / No saturado)
- **Prioridad:** Alta

### RF-05: Sistema de Alertas
- **Descripción:** Generar y mostrar alertas cuando una UCI se acerca o supera el umbral de saturación.
- **Reglas:**
  - 🟡 Alerta Amarilla: Ocupación entre 70% y 84%
  - 🔴 Alerta Roja: Ocupación ≥ 85% (saturación)
  - 🔴 Alerta Preventiva: Probabilidad predicha de saturación mañana ≥ 60%
- **Prioridad:** Alta

### RF-06: Reentrenamiento del Modelo
- **Descripción:** Permitir al administrador disparar el reentrenamiento del modelo desde la web.
- **Proceso:** Recargar datos actualizados → re-entrenar Random Forest → guardar nuevo .pkl
- **Prioridad:** Media

### RF-07: Cierre de Sesión
- **Descripción:** El usuario puede cerrar su sesión de forma segura.
- **Prioridad:** Alta

---

## 4. Requerimientos No Funcionales

### RNF-01: Rendimiento
- El dashboard debe cargarse en menos de 3 segundos.
- Las predicciones deben generarse en menos de 1 segundo.

### RNF-02: Seguridad
- Todas las rutas (excepto login) deben requerir autenticación.
- Las contraseñas deben almacenarse con hash (bcrypt o werkzeug).
- Protección básica contra CSRF en formularios.

### RNF-03: Usabilidad
- Interfaz responsive (desktop y tablet).
- Indicadores de saturación visualmente distinguibles (semáforo de colores).
- Mensajes de error claros al usuario.

### RNF-04: Disponibilidad
- El sistema debe estar disponible durante horario hospitalario (06:00–22:00).

### RNF-05: Portabilidad
- Debe ejecutarse en Windows y Linux.
- Base de datos: SQLite para desarrollo, Firebird 5 para producción.

### RNF-06: Mantenibilidad
- Código comentado y organizado en capas (presentación, servicios, ML, datos).
- Configuración separada en `config.py`.

---

## 5. Requerimientos del Sistema

| Componente | Requisito |
|---|---|
| Python | 3.11 o superior |
| Flask | 2.3.3 |
| scikit-learn | 1.9.1 |
| pandas | 3.0.6 |
| SQLite / Firebird | SQLite (dev), Firebird 5.0.4+ (prod) |
| Navegador | Chrome, Firefox, Edge (versiones modernas) |

---

## 6. Casos de Uso

### CU-01: Iniciar Sesión
- **Actor:** Cualquier usuario del sistema
- **Precondición:** No estar autenticado
- **Flujo Principal:**
  1. Usuario ingresa a `/login`
  2. Ingresa usuario y contraseña
  3. Sistema valida credenciales
  4. Redirige al dashboard
- **Flujo Alternativo:** Credenciales incorrectas → mensaje de error

### CU-02: Ver Dashboard
- **Actor:** Usuario autenticado
- **Precondición:** Sesión activa
- **Flujo Principal:**
  1. Acceder a `/dashboard`
  2. Sistema carga datos del CSV/BD
  3. Muestra tarjetas por hospital con estado actual
  4. Muestra gráfica de tendencia

### CU-03: Registrar Datos Diarios
- **Actor:** Personal de salud
- **Precondición:** Sesión activa
- **Flujo Principal:**
  1. Acceder a `/registro`
  2. Seleccionar hospital y fecha
  3. Ingresar camas totales y ocupadas
  4. Sistema calcula % y estado
  5. Guardar en base de datos

### CU-04: Ver Pronósticos
- **Actor:** Usuario autenticado
- **Flujo Principal:**
  1. Acceder a `/pronosticos`
  2. Sistema carga las últimas features de cada UCI
  3. Llama al modelo .pkl (Random Forest)
  4. Muestra probabilidad de saturación mañana por hospital

### CU-05: Ver Alertas
- **Actor:** Usuario autenticado
- **Flujo Principal:**
  1. Acceder a `/alertas`
  2. Sistema filtra UCIs con ocupación ≥ 70% o predicción de riesgo ≥ 60%
  3. Muestra lista ordenada por severidad

---

## 7. Restricciones Éticas

Este sistema usa únicamente datos agregados de acceso público (MINSA, NASA POWER) y datos simulados. No contiene información clínica ni datos personales de pacientes. No es una herramienta clínica de diagnóstico — es un sistema de apoyo a la gestión hospitalaria.

---

*Documento generado: Noviembre 2026 — Proyecto UCI Puno EPIS 2026-II*
