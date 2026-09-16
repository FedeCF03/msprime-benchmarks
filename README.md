# Prueba corrida con : 
time python3 ms_sim.py --nsam 10 --reps 1000 --seqlen 100000 \
    --theta 10 --rho 10 --seed 40328 --N0 10000
Falta implemtar conexiones de poblaciones el script no configura migración ni eventos
# ms → msprime

Simulaciones de coalescencia equivalentes a comandos de `ms`, corridas con
[`msprime`](https://tskit.dev/msprime/docs/stable/intro.html) y exportadas a CSV.

## Contenido

| Archivo                 | Descripción                                                        |
|--------------------------|---------------------------------------------------------------------|
| `ms_sim.py`  | Script principal: arma la demografía y corre la simulación         |
| `run_cases.sh`          | Corre un set de testcases predefinidos              |

## Uso rápido

```bash
python3 ms_simp.py --nsam 20 --reps 1000 \
    --theta 10 --rho 5 --seqlen 100000 \
```

Esto corre el equivalente a:

```
ms 20 1000 -t 10 -r 5 100000
```


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
| `--theta`   | `-t`               | `4·N0·mu·L`  Es el parámetro poblacional de mutación escalado|
| `--rho`     | `-r`               | `4·N0·c` Es el parámetro poblacional de recombinación escalado|
| `--seed`    | —                  | semilla (ms usa 3, msprime solo necesita una)          |
| `--N0`      | —                  | tamaño efectivo de referencia                           |


## Definiciones 

### Parámetros del Motor de Simulación (`msprime.sim_ancestry`)

| Parámetro | Definición |
| :--- | :--- |
| **`samples`** | **Muestras a rastrear:** Lista de linajes iniciales en el presente. Define cuántos cromosomas (`ploidy=1`) se muestrean de cada población para reconstruir su genealogía hacia el pasado. |
| **`sequence_length`** | **Longitud del locus ($L$):** Largo total de la secuencia cromosómica simulada. |
| **`recombination_rate`** | **Tasa de recombinación ($r$):** Probabilidad de entrecruzamiento. |
| **`num_replicates`** | **Número de réplicas:** Cantidad de repeticiones independientes de la genealogía que se simulan bajo las mismas condiciones. |
| **`random_seed`** | **Semilla aleatoria:** Entero que inicializa el generador de números. |