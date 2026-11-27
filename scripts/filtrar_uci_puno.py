from pathlib import Path
import pandas as pd

# Rutas relativas a la estructura ordenada del proyecto (datos/)
BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "datos"

# 1. Cargar el archivo oficial del MINSA (detecta automáticamente separador y codificación)
archivo_entrada = DATOS_DIR / "DATA_CAMAS_HIST.csv"

try:
    df = pd.read_csv(archivo_entrada, sep=None, engine="python", encoding="utf-8-sig")
except UnicodeDecodeError:
    df = pd.read_csv(archivo_entrada, sep=None, engine="python", encoding="latin-1")

# Limpiar espacios ocultos en los nombres de las columnas
df.columns = df.columns.str.strip()

# 2. Filtrar los 5 establecimientos con camas UCI activas (> 0) en la región PUNO
df_puno = df[
    (df["CC_DISA"].astype(str).str.upper().str.strip() == "PUNO") & 
    (pd.to_numeric(df["CAMAS_UCI_TOT"], errors="coerce") > 0)
].copy()

# 3. Seleccionar columnas relevantes y estandarizar estructura
columnas_base = [
    "FECHACORTE",
    "CC_DISA",
    "CODIGO",
    "NOMBRE",
    "INSTITUCIÓN",
    "CAMAS_UCI_TOT",
    "CAMAS_UCI_DISP"
]

df_limpio = df_puno[columnas_base].copy()

# Convertir tipos de datos y calcular ocupación real diaria (UCI total)
df_limpio["FECHACORTE"] = pd.to_datetime(df_limpio["FECHACORTE"], format="%d/%m/%Y")
df_limpio["CAMAS_UCI_TOT"] = pd.to_numeric(df_limpio["CAMAS_UCI_TOT"])
df_limpio["CAMAS_UCI_DISP"] = pd.to_numeric(df_limpio["CAMAS_UCI_DISP"])

df_limpio["tipo_uci"] = "UCI total"
df_limpio["camas_ocupadas_uci"] = df_limpio["CAMAS_UCI_TOT"] - df_limpio["CAMAS_UCI_DISP"]
df_limpio["porcentaje_ocupacion"] = (df_limpio["camas_ocupadas_uci"] / df_limpio["CAMAS_UCI_TOT"]) * 100
df_limpio["estado_saturacion"] = (df_limpio["porcentaje_ocupacion"] >= 85.0).astype(int)

# Ordenar cronológicamente por establecimiento y fecha
df_limpio = df_limpio.sort_values(by=["NOMBRE", "FECHACORTE"]).reset_index(drop=True)

# 4. Guardar el archivo filtrado real de 2026
archivo_salida = DATOS_DIR / "UCI_5_HOSPITALES_PUNO_2026.csv"
df_limpio.to_csv(archivo_salida, index=False, encoding="utf-8-sig")

print("¡Filtrado de los 5 establecimientos de Puno completado!")
print(f"Total de registros reales 2026: {len(df_limpio)}\n")
print("Resumen por establecimiento:")
print(df_limpio.groupby(["CODIGO", "NOMBRE", "INSTITUCIÓN"]).agg(
    dias_registrados=("FECHACORTE", "count"),
    capacidad_camas=("CAMAS_UCI_TOT", "max"),
    ocupacion_promedio=("camas_ocupadas_uci", "mean"),
    dias_saturados=("estado_saturacion", "sum")
))
