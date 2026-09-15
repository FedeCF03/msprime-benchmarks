#!/usr/bin/env bash
#
# Corre los 6 testcases en msprime y deja un CSV por caso.
#
# Uso:
#   ./run_cases.sh                  # corre todos con las replicas del caso
#   ./run_cases.sh 01 04            # corre solo los casos 01 y 04
#   REPS=500 ./run_cases.sh         # override de replicas (test rapido)
#   OUTDIR=res_test ./run_cases.sh  # cambiar directorio de salida
#   N0=25000 ./run_cases.sh         # cambiar el N0 de referencia
#
set -euo pipefail

PY=${PY:-python3}
SCRIPT=${SCRIPT:-ms_sim.py}
OUTDIR=${OUTDIR:-results}
N0=${N0:-10000}
REPS=${REPS:-}          # si esta vacio se usan las replicas de cada caso
SEEDS="40328 19150 54118"

mkdir -p "$OUTDIR"

# Si se define REPS, pisa el --reps de cada caso
reps_de() {
    if [[ -n "$REPS" ]]; then echo "$REPS"; else echo "$1"; fi
}

# Los casos a correr: los pasados por argumento, o todos
CASOS=("$@")
if [[ ${#CASOS[@]} -eq 0 ]]; then
    CASOS=(01 02 03 04 05 06)
fi

quiere() {
    local c
    for c in "${CASOS[@]}"; do
        [[ "$c" == "$1" ]] && return 0
    done
    return 1
}

# ---------------------------------------------------------------------------
# case 01
#   ms 10 100000 -t 10 -r 10 100000 -I 2 2 8
#      -eN 0.4 10.01 -eN 1 0.01 -en 0.25 2 0.2 -ej 3 2 1 -T -L
# ---------------------------------------------------------------------------
if quiere 01; then
    $PY "$SCRIPT" \
        --label case01 \
        --nsam 10 --reps "$(reps_de 100000)" --seqlen 100000 \
        --theta 10 --rho 10 --seeds $SEEDS --N0 "$N0" \
        --I 2 2 8 \
        --en 0.25 2 0.2 \
        --eN 0.4 10.01 \
        --eN 1 0.01 \
        --ej 3 2 1 \
        -L \
        --out "$OUTDIR/case01.csv"
fi

# ---------------------------------------------------------------------------
# case 02
#   ms 15 20000 -t 10 -r 10 100000 -I 3 10 4 1
#      -ma x 5.0 5.0 5.0 x 5.0 5.0 5.0 x -eN 0.8 15 -ej .7 2 1 -ej 1 3 1 -T -L
# ---------------------------------------------------------------------------
if quiere 02; then
    $PY "$SCRIPT" \
        --label case02 \
        --nsam 15 --reps "$(reps_de 20000)" --seqlen 100000 \
        --theta 10 --rho 10 --seeds $SEEDS --N0 "$N0" \
        --I 3 10 4 1 \
        --ma x 5.0 5.0 5.0 x 5.0 5.0 5.0 x \
        --ej 0.7 2 1 \
        --eN 0.8 15 \
        --ej 1 3 1 \
        -L \
        --out "$OUTDIR/case02.csv"
fi

# ---------------------------------------------------------------------------
# case 03
#   ms 15 100000 -t 10 -r 10 100000 -I 3 10 4 1
#      -ma x 1.0 2.0 3.0 x 4.0 5.0 6.0 x
#      -eN 1 .1 -eN 3 10 -ej .7 2 1 -ej 4 3 1 -T -L
# ---------------------------------------------------------------------------
if quiere 03; then
    $PY "$SCRIPT" \
        --label case03 \
        --nsam 15 --reps "$(reps_de 100000)" --seqlen 100000 \
        --theta 10 --rho 10 --seeds $SEEDS --N0 "$N0" \
        --I 3 10 4 1 \
        --ma x 1.0 2.0 3.0 x 4.0 5.0 6.0 x \
        --ej 0.7 2 1 \
        --eN 1 0.1 \
        --eN 3 10 \
        --ej 4 3 1 \
        -L \
        --out "$OUTDIR/case03.csv"
fi

# ---------------------------------------------------------------------------
# case 04
#   ms 4 100000 -t 10 -r 10 100000 -I 2 2 2 5.0 -T
#   (el 5.0 final de -I es la tasa de migracion simetrica 4*N0*m)
# ---------------------------------------------------------------------------
if quiere 04; then
    $PY "$SCRIPT" \
        --label case04 \
        --nsam 4 --reps "$(reps_de 100000)" --seqlen 100000 \
        --theta 10 --rho 10 --seeds $SEEDS --N0 "$N0" \
        --I 2 2 2 5.0 \
        --out "$OUTDIR/case04.csv"
fi

# ---------------------------------------------------------------------------
# case 05
#   ms 4 100000 -t 10 -r 10 100000 -I 2 2 2 -ma x 10.0 5.0 x -T
#   (matriz asimetrica: 10 en un sentido, 5 en el otro)
# ---------------------------------------------------------------------------
if quiere 05; then
    $PY "$SCRIPT" \
        --label case05 \
        --nsam 4 --reps "$(reps_de 100000)" --seqlen 100000 \
        --theta 10 --rho 10 --seeds $SEEDS --N0 "$N0" \
        --I 2 2 2 \
        --ma x 10.0 5.0 x \
        --out "$OUTDIR/case05.csv"
fi

# ---------------------------------------------------------------------------
# case 06
#   ms 20 50 -t 1000 -r 2000 100000
#   (poblacion unica, sin estructura ni eventos)
# ---------------------------------------------------------------------------
if quiere 06; then
    $PY "$SCRIPT" \
        --label case06 \
        --nsam 20 --reps "$(reps_de 50)" --seqlen 100000 \
        --theta 1000 --rho 2000 --seeds $SEEDS --N0 "$N0" \
        --out "$OUTDIR/case06.csv"
fi

echo
echo "Listo. CSVs en $OUTDIR/"
ls -la "$OUTDIR"/*.csv 2>/dev/null || true
