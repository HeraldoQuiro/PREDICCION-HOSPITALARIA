# Manual de Usuario — SatUCI-Puno
## Sistema de Predicción de Saturación de Camas UCI

**Versión:** 1.0 | **Fecha:** Noviembre 2026

---

## ¿Qué es SatUCI-Puno?

SatUCI-Puno es un sistema web que **predice con 24 horas de anticipación** si una Unidad de Cuidados Intensivos (UCI) de los 5 principales hospitales de Puno entrará en estado de **saturación** (cuando el 85% o más de las camas están ocupadas).

> ⚠️ **Importante:** Este sistema es una herramienta de apoyo a la gestión hospitalaria, NO un sistema de diagnóstico clínico. Las predicciones son probabilidades basadas en datos históricos.

---

## Acceso al Sistema

### Iniciar Sesión

1. Abrir el navegador web (Chrome, Firefox o Edge)
2. Ir a la dirección: **http://localhost:5000**
3. Ingresar sus credenciales:

| Campo | Valor |
|---|---|
| Usuario | `admin` |
| Contraseña | `uci2026` |

4. Hacer clic en **"Iniciar Sesión"**

---

## Pantallas del Sistema

### 🏠 Dashboard (Tablero Principal)

El tablero es la pantalla principal. Muestra de un vistazo el estado actual de las 5 UCI monitoreadas.

**Elementos del tablero:**

| Elemento | Descripción |
|---|---|
| **Tarjetas de hospital** | Una por cada UCI. Muestra nombre, % de ocupación actual y estado (Normal / Alerta / Saturado) |
| **KPI: Hospitales monitoreados** | Total de hospitales con datos activos (5) |
| **KPI: Saturados hoy** | Cantidad de UCI en estado de saturación (≥ 85%) |
| **KPI: Ocupación promedio** | Promedio de % de ocupación de todas las UCI |
| **Gráfica de tendencia** | Evolución de la ocupación de los últimos 30 días |

**Código de colores:**
- 🟢 **Verde** (Normal): Ocupación < 70%
- 🟡 **Amarillo** (Alerta): Ocupación entre 70% y 84%
- 🔴 **Rojo** (Saturado): Ocupación ≥ 85%

---

### 📝 Registro Diario

Esta pantalla permite ingresar los datos diarios de cada UCI.

**Cómo registrar datos:**

1. Ir al menú lateral → **"Registro Diario"**
2. Seleccionar el hospital en el menú desplegable
3. Elegir la fecha del registro (por defecto: hoy)
4. Ingresar:
   - **Camas totales habilitadas:** Número total de camas UCI ese día
   - **Camas ocupadas:** Número de camas con paciente
5. El sistema calculará automáticamente:
   - % de ocupación
   - Estado de saturación (Saturado / No saturado)
6. Hacer clic en **"Guardar Registro"**

> 💡 **Tip:** Se recomienda ingresar los datos al cierre del día (preferiblemente antes de las 23:00 hrs), ya que el sistema usa esta información para generar el pronóstico del día siguiente.

---

### 📊 Pronósticos (Predicciones a 24 horas)

Muestra la predicción de saturación para **mañana** en cada una de las 5 UCI.

**Qué muestra:**

| Columna | Descripción |
|---|---|
| Hospital | Nombre del establecimiento |
| Ocupación actual | % de ocupación del día de hoy |
| Probabilidad de saturación mañana | Porcentaje de probabilidad (0-100%) |
| Predicción | "SATURADO" o "NO SATURADO" |
| Nivel de riesgo | Alto / Medio / Bajo |

**Interpretación:**
- **Probabilidad ≥ 60%:** Riesgo alto de saturación mañana — considerar medidas preventivas
- **Probabilidad 40-59%:** Riesgo moderado — mantener vigilancia
- **Probabilidad < 40%:** Riesgo bajo

> 📌 **Nota:** El modelo fue validado con datos reales de Puno (01/09–03/11/2026). No anticipa con exactitud los *inicios* de nuevos episodios de saturación, pero mantiene correctamente las alertas de unidades ya saturadas.

---

### 🚨 Alertas

Lista de hospitales que requieren atención inmediata, ordenada por severidad.

**Tipos de alerta:**

| Icono | Tipo | Criterio |
|---|---|---|
| 🔴 | **SATURACIÓN** | Ocupación actual ≥ 85% |
| 🟡 | **ALERTA PREVENTIVA** | Ocupación actual 70-84% |
| ⚠️ | **PREDICCIÓN DE RIESGO** | Probabilidad de saturación mañana ≥ 60% |

**Acciones recomendadas ante una alerta:**
- Verificar disponibilidad de camas en hospitales de referencia
- Coordinar posibles traslados de pacientes
- Programar altas clínicas próximas si es factible
- Ajustar asignación de personal de guardia

---

## Navegación

El menú lateral izquierdo permite acceder a todas las secciones:

| Icono | Sección |
|---|---|
| 🏠 | Dashboard |
| 📝 | Registro Diario |
| 📊 | Pronósticos |
| 🚨 | Alertas |
| 🚪 | Cerrar Sesión |

---

## Preguntas Frecuentes

**¿Con qué frecuencia se actualizan los pronósticos?**
Los pronósticos se actualizan automáticamente cada vez que se ingresan nuevos datos en el Registro Diario. Para un pronóstico confiable, se recomienda ingresar los datos del día cada tarde.

**¿Qué significa "probabilidad de saturación"?**
Es el porcentaje de confianza del modelo en que la UCI tendrá ocupación ≥ 85% mañana. Un 70% de probabilidad significa que, según el historial, 7 de cada 10 veces con condiciones similares la UCI terminó saturada.

**¿El sistema reemplaza el criterio médico?**
No. Es una herramienta de apoyo a la planificación. Las decisiones clínicas siempre deben seguir el protocolo médico.

**¿Qué hospitales están incluidos?**
Los 5 establecimientos con camas UCI activas reportadas en REUNIS-MINSA 2026 para la región Puno:
1. Hospital Regional Manuel Núñez Butrón
2. Hospital Carlos Monje Medrano
3. Clínica Adventista Americana de Juliaca
4. Clínica Monte Sinaí Juliaca
5. Hospital San Martín de Porres

---

*Manual de Usuario v1.0 — Sistema SatUCI-Puno*  
*Proyecto: Predicción UCI Puno EPIS 2026-II, Universidad Nacional del Altiplano*
