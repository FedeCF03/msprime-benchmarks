#!/usr/bin/env bash
#
# run_cases.sh
#
# Ejecuta el script ms_sim.py (traducción ms -> msprime).
#
# Uso:
#   ./run_cases.sh              # corre todos los casos (1-6) en secuencia
#   ./run_cases.sh 1 3 5        # corre solo los casos indicados
#   ./run_cases.sh --help
#
# Nota: los casos se ejecutan de forma SECUENCIAL, uno a uno.
#
# Variables de entorno opcionales:
#   PYTHON        intérprete a usar (por defecto: python3)
#   LOG_DIR       carpeta de logs (por defecto: ./logs)
#   VENV          ruta a un virtualenv a activar (opcional)
#   TIME_LIMIT    límite de tiempo por caso, formato `timeout` (ej: 30m)
#   SPLIT_LOGS    si vale "1", además del log acumulativo se guarda
#                 un log por corrida con timestamp (por defecto: 0)
#

set -euo pipefail

# ------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="${SCRIPT_DIR}/ms_sim.py"
PYTHON="${PYTHON:-python3}"
LOG_DIR="${LOG_DIR:-${SCRIPT_DIR}/logs}"
VENV="${VENV:-}"
TIME_LIMIT="${TIME_LIMIT:-}"
SPLIT_LOGS="${SPLIT_LOGS:-0}"

# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------
log()  { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
warn() { printf '\033[1;33m[WARN]\033[0m %s\n' "$*" >&2; }
err()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

usage() {
    sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 0
}

die() { err "$*"; exit 1; }

# ------------------------------------------------------------------
# Parseo de argumentos
# ------------------------------------------------------------------
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
fi

CASES=("$@")
if [[ ${#CASES[@]} -eq 0 ]]; then
    CASES=(1 2 3 4 5 6)
fi

# ------------------------------------------------------------------
# Validaciones previas
# ------------------------------------------------------------------
[[ -f "${RUN_SCRIPT}" ]] || die "No se encontró ms_sim.py en ${SCRIPT_DIR}"

if [[ -n "${VENV}" ]]; then
    if [[ -f "${VENV}/bin/activate" ]]; then
        log "Activando virtualenv: ${VENV}"
        # shellcheck disable=SC1091
        source "${VENV}/bin/activate"
    else
        die "VENV='${VENV}' no contiene bin/activate"
    fi
fi

command -v "${PYTHON}" >/dev/null 2>&1 \
    || die "Intérprete '${PYTHON}' no encontrado en PATH"

if ! "${PYTHON}" -c "import msprime" >/dev/null 2>&1; then
    die "msprime no está instalado para '${PYTHON}'. Prueba: ${PYTHON} -m pip install msprime"
fi

MS_VERSION="$("${PYTHON}" -c "import msprime; print(msprime.__version__)")"
log "Python : $("${PYTHON}" --version 2>&1)"
log "msprime: ${MS_VERSION}"
log "Casos  : ${CASES[*]}"
log "Logs   : ${LOG_DIR}"

mkdir -p "${LOG_DIR}"

# Marca de tiempo única para toda la corrida del script
RUN_TS="$(date +%Y%m%d_%H%M%S)"

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------
FAILED=()
START_ALL=$(date +%s)

run_case() {
    local c="$1"

    # Log acumulativo: SIEMPRE se hace append (>>), nunca se trunca.
    local logfile="${LOG_DIR}/case${c}.log"

    # Log por corrida (opcional): case1_20260923_141530.log
    local runlog=""
    if [[ "${SPLIT_LOGS}" == "1" ]]; then
        runlog="${LOG_DIR}/case${c}_${RUN_TS}.log"
    fi

    log "==> Ejecutando caso ${c}  (log acumulativo: ${logfile})"

    # Encabezado al log acumulativo y (opcional) al log por corrida
    {
        echo
        echo "==================================================================="
        echo "== INICIO caso ${c}  |  $(date '+%Y-%m-%d %H:%M:%S')  |  run ${RUN_TS}"
        echo "==================================================================="
    } >>"${logfile}"
    if [[ -n "${runlog}" ]]; then
        {
            echo "==================================================================="
            echo "== INICIO caso ${c}  |  $(date '+%Y-%m-%d %H:%M:%S')  |  run ${RUN_TS}"
            echo "==================================================================="
        } >"${runlog}"
    fi

    # Comando a ejecutar (con timeout opcional)
    local runcmd=("${PYTHON}" "${RUN_SCRIPT}" "${c}")
    if [[ -n "${TIME_LIMIT}" ]]; then
        runcmd=(timeout "${TIME_LIMIT}" "${PYTHON}" "${RUN_SCRIPT}" "${c}")
    fi

    # Ejecución en primer plano (secuencial)
    if "${runcmd[@]}" >>"${logfile}" 2>&1; then
        log "OK  caso ${c}"
        # Sello de fin en el log acumulativo
        {
            echo "== FIN caso ${c}  |  $(date '+%Y-%m-%d %H:%M:%S')  |  OK"
            echo "==================================================================="
        } >>"${logfile}"
    else
        rc=$?
        warn "FALLO caso ${c}  (rc=${rc})  -> ver ${logfile}"
        FAILED+=("${c}")
        {
            echo "== FIN caso ${c}  |  $(date '+%Y-%m-%d %H:%M:%S')  |  FALLO rc=${rc}"
            echo "==================================================================="
        } >>"${logfile}"
    fi
}

# Ejecutar los casos de forma secuencial
for c in "${CASES[@]}"; do
    run_case "${c}"
done

END_ALL=$(date +%s)
ELAPSED=$((END_ALL - START_ALL))

# ------------------------------------------------------------------
# Resumen
# ------------------------------------------------------------------
echo
log "===== Resumen ====="
printf '  Run              : %s\n' "${RUN_TS}"
printf '  Casos ejecutados : %s\n' "${CASES[*]}"
printf '  Tiempo total     : %ss\n' "${ELAPSED}"
printf '  Logs             : %s\n' "${LOG_DIR}"

if [[ ${#FAILED[@]} -eq 0 ]]; then
    log "Todos los casos terminaron correctamente ✔"
    exit 0
else
    err "Fallaron los casos: ${FAILED[*]}"
    exit 1
fi