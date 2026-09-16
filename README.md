# ms → msprime

Simulaciones de coalescencia equivalentes a comandos de `ms`, corridas con
[`msprime`](https://tskit.dev/msprime/docs/stable/intro.html) y exportadas a CSV.

## Contenido

| Archivo                 | Descripción                                                        |
|--------------------------|---------------------------------------------------------------------|
| `ms_msprime_simple.py`  | Script principal: arma la demografía y corre la simulación         |
| `run_cases.sh`          | Corre un set de testcases predefinidos, uno por CSV                |

## Requisitos

```bash
pip install msprime
```

Python 3.8+.

## Uso rápido

```bash
python3 ms_msprime_simple.py --nsam 20 --reps 1000 \
    --theta 10 --rho 5 --seqlen 100000 \
    --out resultados.csv
```

Esto corre el equivalente a:

```
ms 20 1000 -t 10 -r 5 100000
```

y guarda un resumen por réplica (número de árboles, S, π, D de Tajima,
TMRCA medio) en `resultados.csv`.

## Escalado ms → msprime

`ms` expresa todo en unidades de `4·N0`. El script traduce automáticamente
usando `--N0` (tamaño efectivo de referencia, `10000` por defecto):

`N0` es arbitrario: reescala tiempos y tasas de forma compensada, así que
las genealogías resultantes no cambian.

## Opciones

| Flag        | Equivalente en ms | Descripción                                          |
|-------------|--------------------|--------------------------------------------------------|
| `--nsam`    | primer argumento  | cromosomas muestreados                                 |
| `--reps`    | segundo argumento | número de réplicas                                      |
| `--seqlen`  | último arg. de `-r`| largo del locus (posición física y fija que ocupa un gen o un marcador genético en un cromosoma)                         |
| `--theta`   | `-t`               | `4·N0·mu·L`                                             |
| `--rho`     | `-r`               | `4·N0·c`                                                |
| `--seed`    | —                  | semilla (ms usa 3, msprime solo necesita una)          |
| `--N0`      | —                  | tamaño efectivo de referencia                           |
| `--I`       | `-I`               | `npop n1 n2  ` Define la subdivisión de la población en el tiempo presente           |
| `--eN`      | `-eN t x`          | todas las poblaciones pasan a tamaño `x·N0`             |
| `--en`      | `-en t i x`        | la población `i` pasa a tamaño `x·N0`                   |
| `--ej`      | `-ej t i j`        | Simula la **fusión de dos poblaciones** al viajar hacia el pasado`                          |
| `--out`     | —                  | archivo CSV de salida                                   |
| `--label`   | —                  | etiqueta de caso, se agrega como columna                |
