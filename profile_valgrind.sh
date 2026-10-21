#!/usr/bin/env bash
#
# profile_valgrind.sh - Callgrind (+ KCachegrind) y Cachegrind sobre un caso chico.
#
# Para qué sirve:
#   * callgrind: cuenta INSTRUCCIONES y LLAMADAS exactas por función, y arma el
#     grafo de llamadas. Responde "¿cuántas veces se invoca fenwick_increment /
#     fenwick_rebuild?".
#   * cachegrind: simula L1/LL y ramas, y atribuye los fallos por línea de
#     código. Complementa el cache-misses de `perf stat`.
#
# Valgrind es ~20-50x más lento que la ejecución nativa, así que NO corre los
# casos completos (20.000-100.000 réplicas). valgrind_driver.py recorta
# `num_replicates` (por defecto a 100) sin tocar ms_sim.py; muestras, demografía,
# rho y semilla quedan iguales. Para callgrind además se apaga la
# instrumentación durante los imports y se prende sólo en el bucle de
# simulación: el perfil queda limpio y la corrida mucho más rápida.
#
# Uso:
#   ./profile_valgrind.sh                     # caso 1, 100 réplicas, ambas tools
#   ./profile_valgrind.sh 1 3 5               # varios casos
#   ./profile_valgrind.sh --tool callgrind 5  # sólo callgrind
#   ./profile_valgrind.sh --reps 200 1        # más réplicas (más lento)
#   ./profile_valgrind.sh --fetch-src 1       # baja el fuente de msprime para
#                                             # anotar línea por línea
#   ./profile_valgrind.sh --src ~/msprime-1.4.4 1
#   ./profile_valgrind.sh --open 1            # abre KCachegrind al terminar
#
# Variables de entorno equivalentes:
#   PYTHON   intérprete (por defecto: .venv/bin/python del repo)
#   TOOL     callgrind | cachegrind | both        (defecto: both)
#   REPS     máximo de réplicas por caso          (defecto: 100)
#   OUTDIR   carpeta de salida                    (defecto: ./logs/valgrind)
#   MS_SRC   árbol de fuentes de msprime (el que contiene lib/fenwick.c)
#   OPEN     1 para abrir KCachegrind             (defecto: 0)
#
# Salidas por caso y herramienta en logs/valgrind:
#   caseN.callgrind.out             datos crudos (KCachegrind)
#   caseN.callgrind.txt             anotación completa + grafo de llamadas
#   caseN.callgrind.fenwick.txt     sólo fenwick_*
#   caseN.callgrind.calls.txt       conteo exacto de llamadas (calls=)
#   caseN.callgrind.run.log         salida de valgrind + resumen del driver
#   caseN.cachegrind.out            datos crudos (cg_annotate)
#   caseN.cachegrind.txt            anotación por función y por línea
#   caseN.cachegrind.fenwick.txt    funciones y líneas de fenwick.c
#   caseN.cachegrind.run.log        salida de valgrind + resumen del driver
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-$DIR/.venv/bin/python}"
OUTDIR="${OUTDIR:-$DIR/logs/valgrind}"
DRIVER="$DIR/valgrind_driver.py"

TOOL="${TOOL:-both}"
REPS="${REPS:-100}"
OPEN="${OPEN:-0}"
MS_SRC="${MS_SRC:-}"
FETCH_SRC=0
STATS=0
CASES=()

log()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
    cat <<'EOF'
profile_valgrind.sh - Callgrind (+KCachegrind) y Cachegrind sobre un caso chico.

Uso:
  ./profile_valgrind.sh                        caso 1, 100 réplicas, ambas tools
  ./profile_valgrind.sh 1 3 5                  varios casos
  ./profile_valgrind.sh --tool callgrind 5     sólo callgrind
  ./profile_valgrind.sh --reps 200 1           más réplicas (más lento)
  ./profile_valgrind.sh --fetch-src 1          baja el fuente de msprime
  ./profile_valgrind.sh --src ~/msprime-1.4.4 1
  ./profile_valgrind.sh --open 1               abre KCachegrind al terminar

Opciones:
  --tool callgrind|cachegrind|both   (defecto: both)
  --reps N                           máximo de réplicas (defecto: 100)
  --src DIR                          fuentes de msprime (con lib/fenwick.c)
  --fetch-src                        descarga el sdist de la versión instalada
  --stats                            incluye T_MRCA y nº de árboles
  --open                             abre KCachegrind (si hay entorno gráfico)
  -h, --help

Variables: PYTHON, TOOL, REPS, OUTDIR, MS_SRC, OPEN.
Salidas en logs/valgrind (ver comentarios del script).
EOF
}

# ============================================================
# Argumentos
# ============================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tool)      [[ $# -ge 2 ]] || die "--tool necesita un valor"; TOOL="$2"; shift 2 ;;
        --tool=*)    TOOL="${1#*=}"; shift ;;
        --reps)      [[ $# -ge 2 ]] || die "--reps necesita un valor"; REPS="$2"; shift 2 ;;
        --reps=*)    REPS="${1#*=}"; shift ;;
        --src)       [[ $# -ge 2 ]] || die "--src necesita un valor"; MS_SRC="$2"; shift 2 ;;
        --src=*)     MS_SRC="${1#*=}"; shift ;;
        --fetch-src) FETCH_SRC=1; shift ;;
        --stats)     STATS=1; shift ;;
        --open)      OPEN=1; shift ;;
        -h|--help)   usage; exit 0 ;;
        --*)         die "opción desconocida: $1 (ver --help)" ;;
        *)           CASES+=("$1"); shift ;;
    esac
done

case "$TOOL" in
    callgrind|cachegrind|both) ;;
    *) die "--tool debe ser callgrind, cachegrind o both (recibí: $TOOL)" ;;
esac

[[ "$REPS" =~ ^[0-9]+$ ]] && (( REPS >= 1 )) || die "--reps debe ser un entero >= 1"
[[ "$OPEN" =~ ^[0-9]+$ ]] && (( OPEN <= 1 )) || die "OPEN debe ser 0 o 1"

if [[ ${#CASES[@]} -eq 0 ]]; then
    CASES=(1)
fi

for caso in "${CASES[@]}"; do
    [[ "$caso" =~ ^[0-9]+$ ]] || die "caso inválido: '$caso' (esperaba 1-6)"
    (( caso >= 1 && caso <= 6 )) || die "caso fuera de rango: $caso (válidos: 1-6)"
done

# ============================================================
# Verificaciones
# ============================================================
[[ -x "$PYTHON" ]] || die "no existe el intérprete $PYTHON"
[[ -f "$DRIVER" ]] || die "no existe $DRIVER"

command -v valgrind >/dev/null || die "falta valgrind (sudo apt install valgrind)"
if [[ "$TOOL" == "callgrind" || "$TOOL" == "both" ]]; then
    command -v callgrind_annotate >/dev/null || die "falta callgrind_annotate (paquete valgrind)"
    command -v callgrind_control  >/dev/null || warn "falta callgrind_control: se perfilará todo el proceso (más lento)"
fi
if [[ "$TOOL" == "cachegrind" || "$TOOL" == "both" ]]; then
    command -v cg_annotate >/dev/null || die "falta cg_annotate (paquete valgrind)"
fi

"$PYTHON" -c "import msprime" >/dev/null 2>&1 \
    || die "msprime no está instalado para '$PYTHON'"

mkdir -p "$OUTDIR"

# ============================================================
# Fuentes de msprime (opcional): permiten anotar línea por línea.
# El .so trae DWARF con rutas /project/lib/fenwick.c; reescribimos
# /project -> MS_SRC en los archivos de salida antes de anotar.
# ============================================================
fetch_source() {
    local dest="$1"
    "$PYTHON" - "$dest" <<'PY'
import json
import os
import sys
import tarfile
import tempfile
import urllib.request

import msprime

dest = sys.argv[1]
version = msprime.__version__
root = os.path.join(dest, f"msprime-{version}")

if os.path.exists(os.path.join(root, "lib", "fenwick.c")):
    print(root)
    raise SystemExit(0)

os.makedirs(dest, exist_ok=True)
meta_url = f"https://pypi.org/pypi/msprime/{version}/json"
with urllib.request.urlopen(meta_url, timeout=60) as fh:
    meta = json.load(fh)
url = next(u["url"] for u in meta["urls"] if u["packagetype"] == "sdist")

print(f"[fetch-src] descargando {url}", file=sys.stderr)
with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
    with urllib.request.urlopen(url, timeout=180) as fh:
        tmp.write(fh.read())
    tmp_path = tmp.name

try:
    with tarfile.open(tmp_path) as tf:
        tf.extractall(dest, filter="data")
finally:
    os.unlink(tmp_path)

if not os.path.exists(os.path.join(root, "lib", "fenwick.c")):
    raise SystemExit(f"no se encontró {root}/lib/fenwick.c")
print(root)
PY
}

if (( FETCH_SRC )); then
    log "buscando fuentes de msprime"
    MS_SRC="$(fetch_source "$OUTDIR/src")" || die "no se pudieron bajar las fuentes de msprime"
fi

# Si ya se bajaron antes con --fetch-src, reutilizarlas.
if [[ -z "$MS_SRC" ]]; then
    msprime_ver="$("$PYTHON" -c 'import msprime; print(msprime.__version__)')"
    cached="$OUTDIR/src/msprime-${msprime_ver}"
    if [[ -f "$cached/lib/fenwick.c" ]]; then
        MS_SRC="$cached"
    fi
fi

if [[ -n "$MS_SRC" ]]; then
    MS_SRC="$(cd "$MS_SRC" && pwd)" || die "no existe MS_SRC=$MS_SRC"
    [[ -f "$MS_SRC/lib/fenwick.c" ]] \
        || die "MS_SRC debe ser el árbol de fuentes que contiene lib/fenwick.c ($MS_SRC)"
else
    warn "sin fuentes de msprime: se anotan funciones y costos, pero no el detalle línea por línea."
    warn "para anotar línea por línea: ./profile_valgrind.sh --fetch-src ..."
fi

# Copia del .out con /project -> MS_SRC (o el original si no hay fuentes).
src_out() {
    local in="$1" out="$2"
    if [[ -n "$MS_SRC" ]]; then
        "$PYTHON" - "$in" "$out" "$MS_SRC" <<'PY'
import sys
src, dst, ms_src = sys.argv[1:4]
with open(src, "r", encoding="utf-8", errors="replace") as fh, \
     open(dst, "w", encoding="utf-8") as out:
    for line in fh:
        out.write(line.replace("/project", ms_src))
PY
    else
        cp "$in" "$out"
    fi
}

run_valgrind() {
    local case="$1"
    local tool="$2"
    local out="$OUTDIR/case${case}.${tool}.out"
    local runlog="$OUTDIR/case${case}.${tool}.run.log"
    local -a vg=(valgrind "--tool=$tool")

    if [[ "$tool" == "callgrind" ]]; then
        vg+=(--instr-atstart=no --callgrind-out-file="$out")
    else
        vg+=(--cache-sim=yes --branch-sim=yes --cachegrind-out-file="$out")
    fi

    local -a drv=("$PYTHON" "$DRIVER" "$case" --reps "$REPS")
    [[ "$tool" == "callgrind" ]] && drv+=(--toggle)
    (( STATS )) && drv+=(--stats)

    log "caso ${case}: ${tool} (reps <= ${REPS})"
    # OpenBLAS suele levantar hilos que giran en vacío y ensucian el perfil.
    if ! OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
         "${vg[@]}" "${drv[@]}" >"$runlog" 2>&1; then
        # Si falló el toggle de callgrind, reintentamos instrumentando todo.
        if [[ "$tool" == "callgrind" ]] && grep -q "no se pudo activar" "$runlog"; then
            warn "callgrind_control falló; reintento instrumentando todo el proceso"
            vg=(valgrind "--tool=callgrind" --callgrind-out-file="$out")
            drv=("$PYTHON" "$DRIVER" "$case" --reps "$REPS")
            (( STATS )) && drv+=(--stats)
            OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
                "${vg[@]}" "${drv[@]}" >"$runlog" 2>&1 \
                || die "valgrind falló; ver $runlog"
        else
            die "valgrind falló; ver $runlog"
        fi
    fi

    [[ -s "$out" ]] || die "valgrind no generó $out; ver $runlog"
}

# ============================================================
# Callgrind: anotación, grafo de llamadas y conteo exacto de calls=
# ============================================================
annotate_callgrind() {
    local case="$1"
    local out="$OUTDIR/case${case}.callgrind.out"
    local src="$OUTDIR/case${case}.callgrind.src.out"
    local txt="$OUTDIR/case${case}.callgrind.txt"
    local fen="$OUTDIR/case${case}.callgrind.fenwick.txt"
    local calls="$OUTDIR/case${case}.callgrind.calls.txt"
    local runlog="$OUTDIR/case${case}.callgrind.run.log"
    local reps_sim
    reps_sim="$(sed -n 's/.*simuladas=\([0-9][0-9]*\).*/\1/p' "$runlog" | tail -1)"
    reps_sim="${reps_sim:-$REPS}"

    log "caso ${case}: anotando callgrind"
    src_out "$out" "$src"

    callgrind_annotate --threshold=99 --tree=both "$src" >"$txt" 2>/dev/null

    {
        echo "=== CASO ${case} - CALLGRIND (self + grafo de llamadas) ==="
        echo "Réplicas simuladas: ${reps_sim}"
        echo
        grep -i 'fenwick' "$txt" || echo "(sin símbolos fenwick)"
    } >"$fen"

    "$PYTHON" - "$src" "$calls" "$case" "$reps_sim" <<'PY'
import collections
import re
import sys

src, dst, case, reps = sys.argv[1:5]
reps = int(reps)

# El formato de callgrind comprime nombres: "fn=(123) nombre" la primera vez,
# "fn=(123)" después. Hay que resolver los IDs antes de sumar.
name_re = re.compile(r"^(c?fn)=(?:\((\d+)\)\s*(.*)|(.*))$")
names = {}
calls = collections.Counter()
cur_cfn = None

with open(src, "r", encoding="utf-8", errors="replace") as fh:
    for raw in fh:
        line = raw.rstrip("\n")
        m = name_re.match(line)
        if m:
            kind, fid, name, plain = m.groups()
            if fid:
                if name:
                    names[fid] = name.strip()
                if kind == "cfn":
                    cur_cfn = fid
            elif plain:
                if kind == "cfn":
                    cur_cfn = plain.strip()
                else:
                    cur_cfn = None
            continue
        if line.startswith("calls=") and cur_cfn is not None:
            calls[cur_cfn] += int(line[6:].split()[0])

def label(key):
    return names.get(key, key)

def fmt(n):
    return f"{n:,}".replace(",", ".")

rows = sorted(((label(k), v) for k, v in calls.items()),
              key=lambda kv: (-kv[1], kv[0]))

with open(dst, "w", encoding="utf-8") as out:
    out.write(f"=== CASO {case} - CALLGRIND: llamadas exactas (calls=) ===\n")
    out.write(f"Región instrumentada: bucle de simulación, {reps} réplicas\n\n")
    out.write(f"{'llamadas':>14}  {'por réplica':>12}  función\n")
    out.write("-" * 72 + "\n")
    for fn, n in rows:
        if n and fn:
            out.write(f"{fmt(n):>14}  {n / reps:>12.1f}  {fn}\n")

    out.write("\n--- sólo fenwick ---\n")
    for fn, n in rows:
        if n and "fenwick" in fn:
            out.write(f"{fmt(n):>14}  {n / reps:>12.1f}  {fn}\n")

# Resumen corto por consola.
fenwick = [(fn, n) for fn, n in rows if n and "fenwick" in fn]
print(f"    llamadas instrumentadas en {reps} réplicas:")
for fn, n in fenwick:
    print(f"      {fmt(n):>12}  {fn}")
PY
}

# ============================================================
# Cachegrind: anotación por función y por línea
# ============================================================
annotate_cachegrind() {
    local case="$1"
    local out="$OUTDIR/case${case}.cachegrind.out"
    local src="$OUTDIR/case${case}.cachegrind.src.out"
    local txt="$OUTDIR/case${case}.cachegrind.txt"
    local fen="$OUTDIR/case${case}.cachegrind.fenwick.txt"

    log "caso ${case}: anotando cachegrind"
    src_out "$out" "$src"

    cg_annotate --show=Ir,Dr,Dw,D1mr,D1mw,DLmr,DLmw,Bc,Bcm,Bi,Bim \
        --sort=Ir --threshold=0.1 --context=3 "$src" >"$txt" 2>/dev/null

    {
        echo "=== CASO ${case} - CACHEGRIND: resumen por función (fenwick) ==="
        echo
        sed -n '1,/^-- Annotated source file:/p' "$txt" | grep -i 'fenwick' \
            || echo "(sin símbolos fenwick)"
        echo
        echo "=== CASO ${case} - CACHEGRIND: líneas de fenwick.c ==="
        echo
        awk '
            /^-- Annotated source file: / {
                p = ($0 ~ /fenwick\.c$/)
            }
            p { print }
        ' "$txt" || true
    } >"$fen"

    {
        echo "=== CASO ${case} - CACHEGRIND: totales simulados ==="
        echo
        sed -n 's/^==[0-9]*== //p' "$OUTDIR/case${case}.cachegrind.run.log" \
            | grep -E '^(I refs|I1  misses|LLi misses|I1  miss rate|LLi miss rate|D refs|D1  misses|LLd misses|D1  miss rate|LLd miss rate|LL refs|LL misses|LL miss rate|Branches|Mispredicts|Mispred rate):' \
            || true
    } >"$OUTDIR/case${case}.cachegrind.summary.txt"

    echo "    totales (simulación + imports):"
    sed -n 's/^==[0-9]*== //p' "$OUTDIR/case${case}.cachegrind.run.log" \
        | grep -E '^(I refs|D refs|D1  misses|D1  miss rate|LLd misses|Branches|Mispredicts|Mispred rate):' \
        | sed 's/^/      /' || true
}

# ============================================================
# Main
# ============================================================
echo "============================================================"
echo "  Perfilado con Valgrind"
echo "  Herramienta   : ${TOOL}"
echo "  Casos         : ${CASES[*]}"
echo "  Réplicas      : <= ${REPS} por caso"
echo "  Fuentes       : ${MS_SRC:-(no configuradas)}"
echo "  Salida en     : ${OUTDIR}"
echo "============================================================"

for caso in "${CASES[@]}"; do
    if [[ "$caso" == "6" ]] && (( REPS > 3 )); then
        warn "el caso 6 tarda ~0.2 s por réplica nativa; con --reps ${REPS} valgrind puede tardar muchos minutos (probá --reps 2)"
    fi
    if [[ "$TOOL" == "callgrind" || "$TOOL" == "both" ]]; then
        run_valgrind "$caso" callgrind
        annotate_callgrind "$caso"
    fi
    if [[ "$TOOL" == "cachegrind" || "$TOOL" == "both" ]]; then
        run_valgrind "$caso" cachegrind
        annotate_cachegrind "$caso"
    fi
done

# ============================================================
# KCachegrind
# ============================================================
if [[ "$TOOL" == "callgrind" || "$TOOL" == "both" ]]; then
    primer="${CASES[0]}"
    out="$OUTDIR/case${primer}.callgrind.out"
    if (( OPEN )); then
        if command -v kcachegrind >/dev/null && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
            log "abriendo KCachegrind con $out"
            kcachegrind "$out" &
        else
            warn "KCachegrind no disponible o sin entorno gráfico."
            warn "instalalo con: sudo apt install kcachegrind"
            warn "o abrilo a mano: kcachegrind $out"
        fi
    else
        echo
        echo "Para ver el grafo de llamadas en KCachegrind:"
        echo "  kcachegrind $out"
    fi
fi

echo
echo "============================================================"
echo "  Listo. Resultados en ${OUTDIR}"
echo "============================================================"
