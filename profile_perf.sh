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
#   REPORT=1     además de los contadores, genera logs/perf/caseN.report.log
#   PYTHON       intérprete (por defecto python3)
#
# Nota: `perf record` puede requerir sudo o bajar
# /proc/sys/kernel/perf_event_paranoid (kernel.perf_event_paranoid=-1).
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
PERF="${PERF:-perf}"
LOGS="$DIR/logs/perf"
EVENTS="cache-references,cache-misses,cycles,instructions,branches,faults,migrations"
REPORT="${REPORT:-0}"

# Casos: los argumentos, o 1..6 por defecto
CASES=("$@")
[[ ${#CASES[@]} -eq 0 ]] && CASES=(1 2 3 4 5 6)

# Comprobaciones
[[ -f "$DIR/ms_sim.py" ]] || { echo "Falta ms_sim.py en $DIR" >&2; exit 1; }
command -v "$PYTHON" >/dev/null || { echo "Falta $PYTHON" >&2; exit 1; }
command -v "$PERF"   >/dev/null || { echo "Falta $PERF" >&2; exit 1; }

mkdir -p "$LOGS"
echo "Casos: ${CASES[*]}  ->  $LOGS"

for c in "${CASES[@]}"; do
    out="$LOGS/case${c}.perf.log"
    echo "==> Caso $c -> $out"
    {
        echo "== PERF caso $c | $(date '+%F %T')"
        "$PERF" stat -e "$EVENTS" "$PYTHON" "$DIR/ms_sim.py" "$c"
    } >"$out" 2>&1 || echo "  (rc=$?, revisa $out)"

    if [[ "$REPORT" == "1" ]]; then
        data="$LOGS/case${c}.data"
        echo "  -> perf record: $data"
        PYTHONPERFSUPPORT=1 "$PERF" record -g -F 99 -o "$data" \
            -- "$PYTHON" "$DIR/ms_sim.py" "$c" >/dev/null 2>&1 \
            || { echo "  (record rc=$?)"; continue; }

        rep="$LOGS/case${c}.report.log"
        "$PERF" report --stdio -i "$data" > "$rep" 2>&1
        echo "  OK: $rep"
    fi
done

echo "Listo."
