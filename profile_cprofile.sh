#!/usr/bin/env bash
#
# profile_cprofile.sh - Perfila los casos de ms_sim.py con cProfile.
#
# Genera en logs/cprofile por cada caso:
#   caseN.prof    datos crudos (se pueden abrir con pstats)
#   caseN.log     top por tiempo propio (hotspots) y por tiempo acumulado
#   caseN.run.log salida de ms_sim.py
#
# El perfil empieza despues de importar msprime/numpy/tskit, para no mezclar
# el tiempo de importacion (que en los casos cortos pesa mucho).
#
# Uso:
#   ./profile_cprofile.sh          # casos 1-6
#   ./profile_cprofile.sh 1 6      # solo esos casos
#
# Variables de entorno:
#   PYTHON      interprete (por defecto: el virtualenv del repo, o python3)
#   VENV        virtualenv a usar (por defecto: ./venv o ./.venv si existen)
#   LOG_DIR     carpeta de salida (por defecto: ./logs/cprofile)
#   TOP         filas por tabla (por defecto: 25)
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-$DIR/logs/cprofile}"
TOP="${TOP:-25}"

if [[ -z "${PYTHON:-}" ]]; then
    for venv_dir in "${VENV:-}" "$DIR/venv" "$DIR/.venv"; do
        if [[ -n "$venv_dir" && -x "$venv_dir/bin/python" ]]; then
            PYTHON="$venv_dir/bin/python"
            break
        fi
    done
    PYTHON="${PYTHON:-python3}"
fi

CASES=("$@")
[[ ${#CASES[@]} -eq 0 ]] && CASES=(1 2 3 4 5 6)

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

command -v "$PYTHON" >/dev/null || die "no se encontró '$PYTHON' en el PATH"
"$PYTHON" -c "import msprime" >/dev/null 2>&1 \
    || die "msprime no está instalado para '$PYTHON' (probá: $PYTHON -m pip install msprime)"
mkdir -p "$LOG_DIR"

for caso in "${CASES[@]}"; do
    prof="$LOG_DIR/case${caso}.prof"
    txt="$LOG_DIR/case${caso}.log"
    log "caso ${caso}: cProfile"

    # Importar primero y perfilar solo main(), para excluir los imports.
    "$PYTHON" - "$DIR" "$caso" "$prof" >"$LOG_DIR/case${caso}.run.log" 2>&1 <<'PY'
import cProfile
import sys

repo, caso, prof = sys.argv[1], int(sys.argv[2]), sys.argv[3]
sys.path.insert(0, repo)
import ms_sim

sys.argv = ["ms_sim.py", str(caso)]
cProfile.runctx("ms_sim.main()", globals(), locals(), prof)
PY

    # Dos vistas: tottime (hotspots) y cumtime (flujo de llamadas).
    "$PYTHON" - "$prof" "$txt" "$caso" "$TOP" <<'PY'
import pstats
import sys

prof, txt, caso, top = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
stats = pstats.Stats(prof)

with open(txt, "w") as fh:
    fh.write(f"=== CPROFILE CASO {caso} ===\n\n")
    fh.write(f"Tiempo medido : {stats.total_tt:.2f} s\n")
    fh.write(f"Llamadas      : {stats.total_calls}\n\n")

    fh.write(f"## Hotspots: top {top} por tiempo propio (tottime)\n\n")
    stats.stream = fh
    stats.sort_stats("tottime").print_stats(top)

    fh.write(f"\n## Flujo: top {top} por tiempo acumulado (cumtime)\n\n")
    stats.sort_stats("cumtime").print_stats(top)
PY

    log "caso ${caso}: $txt"
done

log "listo"
