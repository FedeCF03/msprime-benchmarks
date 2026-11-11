#!/bin/bash
#
# profile_perf_opt.sh - Igual que profile_perf.sh del repo (mismo Python del .venv, mismos
# eventos, perf record + perf stat en una misma ejecución, solo OPENBLAS_NUM_THREADS=1),
# pero con una variante de msprime compilada en ~/msprime-opt/build, elegida con PYTHONPATH.
#
# Uso:
#   profile_perf_opt.sh <variante>             # corre los casos 1 a 6
#   profile_perf_opt.sh <variante> 1 3 5       # corre solo los casos 1, 3 y 5
#   REPS=3 profile_perf_opt.sh <variante>      # repeticiones de perf stat (por defecto 1)
#
# Salida (una por caso) en ~/msprime-benchmarks/logs/perf/optimizacion/:
#   caseN_<variante>.txt         -> perf stat: contadores
#   caseN_<variante>.data        -> perf record: muestras crudas
#   caseN_<variante>.report.log  -> perf report: hotspots

set -euo pipefail

VARIANTE=$1
shift
BASE="/home/fedecf/msprime-benchmarks"
PYTHON="${BASE}/.venv/bin/python"
SCRIPT="${BASE}/ms_sim.py"
OUTDIR="${BASE}/logs/perf/optimizacion"
MSPRIME="/home/fedecf/msprime-opt/build/v_${VARIANTE}"

CASOS_DEFAULT=(1 2 3 4 5 6)
EVENTOS="cache-references,cache-misses,cycles,instructions,branches,faults,migrations"
REPS="${REPS:-1}"
export OPENBLAS_NUM_THREADS=1

if [ "$#" -gt 0 ]; then
    CASOS=("$@")
else
    CASOS=("${CASOS_DEFAULT[@]}")
fi

[ -d "$MSPRIME" ] || { echo "ERROR: no existe $MSPRIME"; exit 1; }
mkdir -p "$OUTDIR"

for caso in "${CASOS[@]}"; do
    TXT="${OUTDIR}/case${caso}_${VARIANTE}.txt"
    DATA="${OUTDIR}/case${caso}_${VARIANTE}.data"
    REPORT="${OUTDIR}/case${caso}_${VARIANTE}.report.log"

    echo
    echo ">>> Caso ${caso}, variante ${VARIANTE}"

    # perf record renombra un .data existente a .data.old; se borra antes
    sudo rm -f "$DATA"
    # sudo limpia el entorno: OPENBLAS_NUM_THREADS y PYTHONPATH se pasan explícitos con env
    sudo env OPENBLAS_NUM_THREADS="$OPENBLAS_NUM_THREADS" PYTHONPATH="$MSPRIME" \
        perf record -g -F 99 -o "$DATA" -- \
        perf stat -r "$REPS" -B -e "$EVENTOS" -o "$TXT" \
        -- "$PYTHON" "$SCRIPT" "$caso" > /dev/null
    sudo chown "$(id -u):$(id -g)" "$DATA" "$TXT"
    perf report --stdio --comms python -i "$DATA" > "$REPORT"

    cat "$TXT"
done
