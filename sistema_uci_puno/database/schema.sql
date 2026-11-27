-- =============================================================================
-- ESQUEMA DE BASE DE DATOS: SatUCI-Puno (SQLite)
-- Sistema de Predicción de Saturación de Camas UCI a 24 horas
-- Universidad Nacional del Altiplano - EPIS (2026-II)
-- Autores: Roy Aldair Tipo Catunta & Robert Heraldo Quiro Arguedas
-- =============================================================================

-- Tabla de Usuarios del Sistema
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'admin',
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Hospitales Monitoreados (5 UCIs de Puno)
CREATE TABLE IF NOT EXISTS hospitales (
    codigo INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    institucion TEXT NOT NULL,
    ciudad TEXT NOT NULL,
    camas_uci_tot INTEGER NOT NULL,
    tipo_uci TEXT DEFAULT 'UCI total',
    direccion TEXT,
    telefono TEXT,
    nivel TEXT,
    activo INTEGER DEFAULT 1
);

-- Tabla de Registros Diarios de Ocupación UCI
CREATE TABLE IF NOT EXISTS registros_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_codigo INTEGER NOT NULL,
    fecha DATE NOT NULL,
    camas_uci_tot INTEGER NOT NULL,
    camas_uci_disp INTEGER NOT NULL,
    camas_ocupadas_uci INTEGER NOT NULL,
    porcentaje_ocupacion REAL NOT NULL,
    estado_saturacion INTEGER NOT NULL,
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_codigo) REFERENCES hospitales(codigo) ON DELETE CASCADE,
    UNIQUE(hospital_codigo, fecha)
);

-- Tabla de Alertas de Saturación
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_codigo INTEGER NOT NULL,
    fecha DATE NOT NULL,
    tipo_alerta TEXT NOT NULL,          -- 'CRITICA', 'ADVERTENCIA', 'PREVENTIVA_24H'
    nivel TEXT NOT NULL,                -- 'ROJA', 'AMARILLA', 'AZUL'
    porcentaje_ocupacion REAL NOT NULL,
    probabilidad_saturacion REAL DEFAULT 0.0,
    camas_ocupadas INTEGER,
    camas_totales INTEGER,
    mensaje TEXT NOT NULL,
    leida INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_codigo) REFERENCES hospitales(codigo) ON DELETE CASCADE
);

-- Tabla de Pronósticos de Saturación a 24 Horas
CREATE TABLE IF NOT EXISTS pronosticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_codigo INTEGER NOT NULL,
    fecha_prediccion DATE NOT NULL,     -- Fecha en la que se generó la predicción (t-1)
    fecha_objetivo DATE NOT NULL,       -- Fecha que se predice (t)
    ocupacion_actual REAL NOT NULL,
    probabilidad_saturacion REAL NOT NULL,
    porcentaje_predicho REAL NOT NULL,
    prediccion_clase INTEGER NOT NULL,  -- 1: Saturado, 0: No Saturado
    nivel_riesgo TEXT NOT NULL,         -- 'Bajo', 'Moderado', 'Alto', 'Crítico'
    tendencia TEXT NOT NULL,            -- 'ascendente', 'descendente', 'estable'
    factores_riesgo TEXT,
    recomendacion TEXT,
    modelo_usado TEXT DEFAULT 'Random Forest Classifier',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_codigo) REFERENCES hospitales(codigo) ON DELETE CASCADE
);

-- Índices para optimizar consultas de dashboard y series temporales
CREATE INDEX IF NOT EXISTS idx_reg_hosp_fecha ON registros_diarios(hospital_codigo, fecha);
CREATE INDEX IF NOT EXISTS idx_reg_fecha ON registros_diarios(fecha);
CREATE INDEX IF NOT EXISTS idx_alertas_leida ON alertas(leida, fecha);
CREATE INDEX IF NOT EXISTS idx_pronosticos_objetivo ON pronosticos(hospital_codigo, fecha_objetivo);
