#!/bin/bash
#
# profile_perf.sh - Perfilado con perf de cada caso de msprime.
# En una misma ejecución corre perf record (hotspots) y perf stat (contadores).
#
# Uso:
#   ./profile_perf.sh              # corre los casos definidos en CASOS
#   ./profile_perf.sh 1 3 5        # corre solo los casos 1, 3 y 5
#   REPS=5 ./profile_perf.sh       # repite cada caso 5 veces (por defecto 3)
#
# Salida (una por caso):
#   logs/perf/caseN.txt         -> perf stat: contadores (media ± desvío de REPS corridas)
#   logs/perf/caseN.data        -> perf record: muestras crudas
#   logs/perf/caseN.report.log  -> perf report: hotspots

set -euo pipefail

# ============================================================
# Configuración
# ============================================================
BASE="/home/fedecf/msprime-benchmarks"
PYTHON="${BASE}/.venv/bin/python"
SCRIPT="${BASE}/ms_sim.py"
OUTDIR="${BASE}/logs/perf"

# Casos por defecto (editá esta lista según los que tengas)
CASOS_DEFAULT=(1 2 3 4 5 6)


EVENTOS="cache-references,cache-misses,cycles,instructions,branches,faults,migrations"

# Repeticiones de perf stat -r (media ± desvío de cada contador)
REPS="${REPS:-3}"

# numpy levanta hilos de OpenBLAS que quedan girando ociosos y ensucian los perfiles
export OPENBLAS_NUM_THREADS=1

# Casos: argumentos de la línea de comandos o la lista por defecto
if [ "$#" -gt 0 ]; then
    CASOS=("$@")
else
    CASOS=("${CASOS_DEFAULT[@]}")
fi

# ============================================================
# Verificaciones
# ============================================================
if ! command -v perf &>/dev/null; then
    echo "ERROR: 'perf' no está instalado."
    echo "Instalalo con:  sudo apt install linux-tools-common linux-tools-\$(uname -r)"
    exit 1
fi

for f in "$PYTHON" "$SCRIPT"; do
    if [ ! -e "$f" ]; then
        echo "ERROR: no existe $f"
        exit 1
    fi
done

mkdir -p "$OUTDIR"

echo "============================================================"
echo "  Perfilado con perf record + perf stat"
echo "  Casos         : ${CASOS[*]}"
echo "  Repeticiones  : ${REPS}"
echo "  Eventos       : ${EVENTOS}"
echo "  Salida en     : ${OUTDIR}"
echo "============================================================"

# ============================================================
# Perfilar cada caso: perf record (hotspots) y perf stat (contadores)
# ============================================================
for caso in "${CASOS[@]}"; do
    TXT="${OUTDIR}/case${caso}.txt"
    DATA="${OUTDIR}/case${caso}.data"
    REPORT="${OUTDIR}/case${caso}.report.log"

    echo
    echo ">>> Caso ${caso}"

    # perf record renombra un .data existente a .data.old; se borra antes
    sudo rm -f "$DATA"
    # sudo limpia el entorno: OPENBLAS_NUM_THREADS se pasa explícito con env
    sudo env OPENBLAS_NUM_THREADS="$OPENBLAS_NUM_THREADS" \
        perf record -g -F 99 -o "$DATA" -- \
        perf stat -r "$REPS" -B -e "$EVENTOS" -o "$TXT" \
        -- "$PYTHON" "$SCRIPT" "$caso" > /dev/null
    sudo chown "$(id -u):$(id -g)" "$DATA" "$TXT"
    perf report --stdio --comms python -i "$DATA" > "$REPORT"

    cat "$TXT"
done

echo
echo "============================================================"
echo "  Perfilado finalizado. Resultados en ${OUTDIR}"
echo "============================================================"
