# Traducción de `ms` a `msprime`

Este repositorio contiene la equivalencia y traducción directa entre comandos clásicos del simulador de coalescencia **`ms`** y la librería en Python **`msprime`**.

---

## 1. Convenciones y Escalado de Parámetros

`ms` formula todos sus parámetros en unidades coalescentes continuas dependientes del tamaño efectivo de referencia $N_0$ . `msprime` modela generaciones e individuos de forma explícita.

Para mantener una equivalencia sin alterar los resultados matemáticos, se fija mantiene la escala:

| Concepto | Comando `ms` | Fórmula / Escala | En `msprime` |
| :--- | :--- | :--- | :--- |
| **Tamaño efectivo base** | Implícito ($N_0$) | $N_e = 1$ | `initial_size = 1` |
| **Tiempo hacia el pasado** | $t$ (unidades de $4N_0$ gen.) | $T = t \times 4N_e$ | `T(t) = t * 4` |
| **Tasa de recombinación** | `-r rho L` | $\rho = 4N_e r L \implies r = \frac{\rho}{4N_e L}$ | `re_rate(rho, L)` |
| **Tasa de mutación** | `-t theta` | $\theta = 4N_e \mu L \implies \mu = \frac{\theta}{4N_e L}$ | `mu_rate(theta, L)` |
| **Tasa de migración** | `-I ... M` o `-ma` | $M = 4N_e m \implies m = \frac{M}{4N_e}$ | `mig_rate(M)` |
| **Cambios de tamaño** | `-eN t x` o `-en t i x` | $N(t) = x \cdot N_0$ | `initial_size = x * NE` |


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



### Parámetros del Motor de Simulación (`msprime.sim_ancestry`)

| Parámetro | Definición |
| :--- | :--- |
| **`samples`** | **Muestras a rastrear:** Lista de linajes iniciales en el presente. Define cuántos cromosomas (`ploidy=1`) se muestrean de cada población para reconstruir su genealogía hacia el pasado. |
| **`sequence_length`** | **Longitud del locus ($L$):** Largo total de la secuencia cromosómica simulada. |
| **`recombination_rate`** | **Tasa de recombinación ($r$):** Probabilidad de entrecruzamiento. |
| **`num_replicates`** | **Número de réplicas:** Cantidad de repeticiones independientes de la genealogía que se simulan bajo las mismas condiciones. |
| **`random_seed`** | **Semilla aleatoria:** Entero que inicializa el generador de números. |

[msprime switch from other simulators](https://tskit.dev/msprime/docs/stable/switch_from_other_simulators.html)