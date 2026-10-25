#!/usr/bin/env bash
#
# profile_perf.sh - Perfila casos con `perf stat` y guarda logs.
# Opcional: genera reporte de texto con `perf report` (REPORT=1).
#
# Uso:
#   ./profile_perf.sh              # todos los casos (1-6)
#   ./profile_perf.sh 1 3 5        # solo esos casos
#
# Variables de entorno:
#   REPORT=0     desactiva el reporte con call-graph. Por defecto SÍ se genera
#                logs/perf/caseN.report.log (además de los contadores).
#   PYTHON       intérprete a usar. Por defecto: .venv/bin/python si existe,
#                si no python3 del PATH. Debe tener msprime instalado.
#   RUNS=5       repeticiones de `perf stat -r` (media ± desvío de cada contador).
#   FREQ=999     frecuencia de muestreo (Hz) de `perf record`.
#   MEM=1        mide el pico de memoria (max RSS) en logs/perf/caseN.mem.log.
#                MEM=0 lo desactiva.
#
# Se exporta OPENBLAS_NUM_THREADS=1: numpy levanta hilos de OpenBLAS que quedan
# girando ociosos (blas_thread_server) y ensucian los perfiles.
#
# Nota: `perf record` puede requerir sudo o bajar
# /proc/sys/kernel/perf_event_paranoid (kernel.perf_event_paranoid=-1).
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Intérprete: respeta PYTHON si está definido; si no, usa el .venv/ del repo
# cuando existe (ahí está msprime); y si no, cae en python3 del PATH.
if [[ -z "${PYTHON:-}" && -x "$DIR/.venv/bin/python" ]]; then
    PYTHON="$DIR/.venv/bin/python"
fi
PYTHON="${PYTHON:-python3}"
PERF="${PERF:-perf}"
LOGS="${LOGS:-$DIR/logs/perf}"
EVENTS="cache-references,cache-misses,cycles,instructions,branches,faults,migrations"
REPORT="${REPORT:-1}"
RUNS="${RUNS:-5}"
FREQ="${FREQ:-999}"
MEM="${MEM:-1}"
export OPENBLAS_NUM_THREADS=1

# Casos: los argumentos, o 1..6 por defecto
CASES=("$@")
[[ ${#CASES[@]} -eq 0 ]] && CASES=(1 2 3 4 5 6)

# Comprobaciones
[[ -f "$DIR/ms_sim.py" ]] || { echo "Falta ms_sim.py en $DIR" >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "Falta $PYTHON" >&2; exit 1; }
command -v "$PERF"   >/dev/null || { echo "Falta $PERF" >&2; exit 1; }

# msprime es indispensable: se perfila ms_sim.py, que hace `import msprime`.
if ! "$PYTHON" -c "import msprime" >/dev/null 2>&1; then
    {
        echo "ERROR: msprime no está instalado para '$PYTHON'."
        echo "Este script perfila ms_sim.py, que necesita msprime. Instalalo con:"
        echo "    python3 -m venv \"$DIR/.venv\""
        echo "    \"$DIR/.venv/bin/pip\" install msprime numpy dendropy"
        echo "y volvé a correr: PYTHON=\"$DIR/.venv/bin/python\" $0"
    } >&2
    exit 1
fi

mkdir -p "$LOGS"
echo "Python : $("$PYTHON" --version 2>&1)"
echo "msprime: $("$PYTHON" -c 'import msprime; print(msprime.__version__)')"
echo "Casos: ${CASES[*]}  ->  $LOGS  (runs=$RUNS, freq=$FREQ, mem=$MEM)"

for c in "${CASES[@]}"; do
    out="$LOGS/case${c}.perf.log"
    echo "==> Caso $c -> $out"
    {
        echo "== PERF caso $c | $(date '+%F %T') | runs=$RUNS"
        "$PERF" stat -r "$RUNS" -e "$EVENTS" "$PYTHON" "$DIR/ms_sim.py" "$c"
    } >"$out" 2>&1 || echo "  (rc=$?, revisa $out)"

    if [[ "$MEM" == "1" ]]; then
        # Pico de memoria del proceso hijo (ru_maxrss, en KiB en Linux).
        mem="$LOGS/case${c}.mem.log"
        echo "  -> max RSS: $mem"
        {
            echo "== MEM caso $c | $(date '+%F %T')"
            "$PYTHON" - "$PYTHON" "$DIR/ms_sim.py" "$c" <<'EOF'
import resource, subprocess, sys
rc = subprocess.call(sys.argv[1:], stdout=subprocess.DEVNULL)
kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
print(f"max RSS: {kib} KiB ({kib / 1024:.1f} MiB)  rc={rc}")
EOF
        } >"$mem" 2>&1 || echo "  (mem rc=$?, revisa $mem)"
    fi

    if [[ "$REPORT" == "1" ]]; then
        data="$LOGS/case${c}.data"
        echo "  -> perf record: $data"
        PYTHONPERFSUPPORT=1 "$PERF" record -g -F "$FREQ" -o "$data" \
            -- "$PYTHON" "$DIR/ms_sim.py" "$c" >/dev/null 2>&1 \
            || { echo "  (record rc=$?)"; continue; }

        rep="$LOGS/case${c}.report.log"
        "$PERF" report --stdio -i "$data" > "$rep" 2>&1
        echo "  OK: $rep"
    fi
done

echo "Listo."
