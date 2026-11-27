# Manual Técnico — SatUCI-Puno
## Sistema de Predicción de Saturación de Camas UCI

**Proyecto:** Predicción UCI Puno EPIS 2026-II  
**Universidad:** Universidad Nacional del Altiplano — EPIS  

---

## 1. Requisitos del Sistema

### Software
- **Python:** 3.11 o superior
- **pip:** 24.0 o superior
- **Git:** Para control de versiones
- **Firebird 5.0.4** (solo producción — para desarrollo se usa SQLite)

### Hardware mínimo
- RAM: 4 GB
- Disco: 2 GB libres
- SO: Windows 10/11 o Ubuntu 20.04+

---

## 2. Instalación y Configuración

### 2.1 Clonar/Abrir el proyecto

```bash
# Desde la raíz del proyecto
cd "C:\PROJECTS\PREDICCION HOSPITALARIA"
```

### 2.2 Crear entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 2.3 Instalar dependencias

```bash
cd sistema_uci_puno
pip install -r requirements.txt
```

### 2.4 Inicializar la base de datos

```bash
python database/init_db.py
```

Este script crea la base de datos SQLite (`uci_puno.db`), crea todas las tablas e importa los datos reales del CSV `datos/UCI_5_HOSPITALES_PUNO_2026.csv`.

### 2.5 Ejecutar la aplicación

```bash
python app.py
```

Abrir en el navegador: **http://localhost:5000**

---

## 3. Credenciales por defecto

| Usuario | Contraseña | Rol |
|---|---|---|
| `admin` | `uci2026` | Administrador |
| `usuario` | `puno2026` | Personal de salud |

> ⚠️ **Cambiar las contraseñas antes de desplegar en producción.**

---

## 4. Estructura de Archivos

```
sistema_uci_puno/
├── app.py                    # Punto de entrada Flask, rutas principales
├── config.py                 # Configuración (claves, rutas de BD, etc.)
├── requirements.txt          # Dependencias Python
├── README.md                 # Instrucciones rápidas
├── uci_puno.db               # Base de datos SQLite (se crea con init_db.py)
│
├── database/
│   ├── schema.sql            # Esquema SQLite completo
│   ├── schema_firebird.sql   # Esquema Firebird 5 (para producción)
│   └── init_db.py            # Script de inicialización con datos reales
│
├── ml/
│   ├── predictor.py          # Carga modelo .pkl y genera predicciones
│   └── mock_predictor.py     # Predictor de respaldo (sin .pkl)
│
├── services/
│   ├── data_service.py       # Acceso a datos (CSV + BD)
│   ├── dashboard_service.py  # Estadísticas para el tablero
│   └── alert_service.py      # Lógica de alertas de saturación
│
├── templates/
│   ├── base.html             # Layout base con sidebar
│   ├── login.html            # Página de inicio de sesión
│   ├── dashboard.html        # Tablero principal
│   ├── registro.html         # Formulario de registro diario
│   ├── pronosticos.html      # Vista de pronósticos
│   └── alertas.html          # Vista de alertas
│
└── static/
    ├── css/
    │   └── style.css         # Estilos (dark mode, glassmorphism)
    └── js/
        └── main.js           # Chart.js + interactividad
```

---

## 5. Rutas de la Aplicación

| Método | URL | Descripción | Auth requerida |
|---|---|---|---|
| GET/POST | `/login` | Inicio de sesión | No |
| GET | `/logout` | Cierre de sesión | Sí |
| GET | `/` o `/dashboard` | Tablero principal | Sí |
| GET/POST | `/registro` | Registro diario | Sí |
| GET | `/pronosticos` | Pronósticos 24h | Sí |
| GET | `/alertas` | Alertas activas | Sí |
| POST | `/api/retrain` | Reentrenar modelo | Sí (admin) |

---

## 6. Integrar el Modelo Real

Cuando el modelo Random Forest esté entrenado:

1. Entrenar con los scripts en `scripts/`:
   ```bash
   python scripts/02_simulacion.py
   python scripts/03_evaluacion.py
   ```

2. El script guarda el modelo en `modelos/modelo_rf.pkl`

3. `predictor.py` carga automáticamente `modelos/modelo_rf.pkl` (o también puedes copiarlo a `sistema_uci_puno\ml\modelo_rf.pkl`).

4. `predictor.py` detectará automáticamente el archivo .pkl y lo usará en lugar del mock.

---

## 7. Migración a Firebird 5 (Producción)

1. Instalar Firebird 5.0.4 desde: https://firebirdsql.org/
2. Crear la base de datos:
   ```sql
   -- Usar isql o FlameRobin
   CREATE DATABASE 'uci_puno.fdb' USER 'SYSDBA' PASSWORD 'masterkey';
   ```
3. Ejecutar `database/schema_firebird.sql`
4. En `config.py`, cambiar:
   ```python
   DATABASE_TYPE = 'firebird'  # en lugar de 'sqlite'
   FIREBIRD_DSN = 'localhost:/path/to/uci_puno.fdb'
   ```

---

## 8. Variables de Entorno (producción)

Crear un archivo `.env` en `sistema_uci_puno/`:

```env
SECRET_KEY=una_clave_secreta_muy_larga_y_aleatoria
DATABASE_TYPE=sqlite
FLASK_ENV=production
FLASK_DEBUG=0
```

---

## 9. Problemas Conocidos

| Problema | Solución |
|---|---|
| `ModuleNotFoundError` al ejecutar app.py | Activar el entorno virtual y ejecutar `pip install -r requirements.txt` |
| BD no encontrada | Ejecutar `python database/init_db.py` primero |
| Modelo .pkl no encontrado | El sistema usa `mock_predictor.py` automáticamente hasta que exista el archivo |
| Puerto 5000 ocupado | Cambiar en `app.py`: `app.run(port=5001)` |

---

## 10. Control de Versiones

El proyecto usa Git. Repositorio: https://github.com/HeraldoQuiro/PREDICCION-HOSPITALARIA.git

```bash
git add .
git commit -m "descripción del cambio"
git push origin main
```

---

*Manual Técnico v1.0 — Noviembre 2026*
