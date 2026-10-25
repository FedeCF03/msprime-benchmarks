#!/usr/bin/env bash
#
# profile_pyspy.sh - Perfila casos con `py-spy` (flamegraph) y guarda la salida.
#
# py-spy es un profiler por MUESTREO: casi no distorsiona el tiempo (a diferencia
# de cProfile) y con --native incluye los frames de C (msprime/tskit).
#
# Uso:
#   ./profile_pyspy.sh              # todos los casos (1-6)
#   ./profile_pyspy.sh 1 3 5        # solo esos casos
#   ./profile_pyspy.sh --help
#
# Variables de entorno:
#   PYTHON   intérprete a usar (por defecto: .venv/bin/python si existe, si no python3)
#   FORMAT   salida: svg (defecto), raw, speedscope o chrometrace
#   NATIVE   1 incluye frames nativos de C (por defecto: 1)
#   RATE     muestras por segundo (por defecto: 100)
#   LOGS     carpeta de salida (por defecto: ./logs/pyspy)
#
# Nota: si no puede leer el proceso, probá con sudo o revisá
#   /proc/sys/kernel/yama/ptrace_scope
#
set -euo pipefail

# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------
log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

usage() {
    sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
fi

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEBUG="${DEBUG:-0}"
if [[ -n "${PYTHON:-}" ]]; then
    PY="${PYTHON}"
elif [[ -x "$DIR/.venv/bin/python" ]]; then
    PY="$DIR/.venv/bin/python"
else
    PY="python3"
fi

FORMAT="${FORMAT:-svg}"
NATIVE="${NATIVE:-1}"
RATE="${RATE:-100}"
LOGS="${LOGS:-$DIR/logs/pyspy}"

# Casos: los argumentos, o 1..6 por defecto
CASES=("$@")
[[ ${#CASES[@]} -eq 0 ]] && CASES=(1 2 3 4 5 6)

# ------------------------------------------------------------------
# Validaciones
# ------------------------------------------------------------------
[[ -f "$DIR/ms_sim.py" ]] || die "Falta ms_sim.py en $DIR"

PYSPY="$("$PY" -c 'import shutil,sys; p=shutil.which("py-spy"); print(p or "")')"
if [[ -z "$PYSPY" ]]; then
    # py-spy puede estar instalado como script del venv
    [[ -x "$DIR/.venv/bin/py-spy" ]] && PYSPY="$DIR/.venv/bin/py-spy"
fi
[[ -n "$PYSPY" && -x "$PYSPY" ]] || die "py-spy no encontrado. Instalalo con: $PY -m pip install py-spy"

"$PY" -c "import msprime" >/dev/null 2>&1 \
    || die "msprime no está instalado para '$PY'. Prueba: $PY -m pip install msprime"

# Mapear formato amigable -> formato de py-spy + extensión de archivo
case "$FORMAT" in
    svg|flamegraph) PS_FORMAT="flamegraph"; EXT="svg" ;;
    speedscope)     PS_FORMAT="speedscope"; EXT="json" ;;
    raw|txt)        PS_FORMAT="raw";        EXT="txt" ;;
    chrometrace)    PS_FORMAT="chrometrace"; EXT="json" ;;
    *) die "FORMAT='$FORMAT' inválido (usá: svg, speedscope, raw, chrometrace)" ;;
esac

# Argumentos extra para py-spy record
REC_ARGS=(--format "$PS_FORMAT" --rate "$RATE")
if [[ "$NATIVE" == "1" ]]; then
    REC_ARGS+=(--native)
fi
if [[ "$DEBUG" == "1" ]]; then
    REC_ARGS+=(--nonblocking)
fi

mkdir -p "$LOGS"
log "intérprete : $PY"
log "msprime    : $("$PY" -c 'import msprime; print(msprime.__version__)')"
log "py-spy     : $("$PYSPY" --version)"
log "casos      : ${CASES[*]}  ->  $LOGS  (formato=$FORMAT, native=$NATIVE, rate=$RATE)"

# ------------------------------------------------------------------
# Perfilado
# ------------------------------------------------------------------
for c in "${CASES[@]}"; do
    out="$LOGS/case${c}.${EXT}"
    log "==> Perfilando caso ${c} -> $out"
    if "$PYSPY" record "${REC_ARGS[@]}" \
            -o "$out" -- "$PY" "$DIR/ms_sim.py" "$c" >/dev/null 2>"$LOGS/case${c}.err"; then
        log "OK -> $out"
    else
        err "Fallo el caso ${c}  (ver $LOGS/case${c}.err)"
    fi
done

log "Listo. Archivos en $LOGS/"
if [[ "$EXT" == "svg" ]]; then
    log "  Abrí el flamegraph: firefox $LOGS/case${CASES[0]}.svg"
fi
exit 0
