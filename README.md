# Traducción de `ms` a `msprime`

Benchmarks y validación de la equivalencia entre el simulador de coalescencia
clásico **`ms`** (Hudson, 2002) y la librería Python **`msprime`**.

El repositorio contiene 6 casos de prueba traducidos de `ms` a `msprime`,
un runner en bash para ejecutarlos en paralelo con logging, y un script de
referencia que corre los mismos casos con `mspms` (el clon de `ms` incluido
en `msprime`) para comparar los resultados de forma **estadística**.
---

## Estructura del repositorio

```
msprime-benchmarks/
├── ms_sim.py         # Los 6 casos traducidos a msprime (sim_ancestry)
├── mspms_cases.py    # Corre los mismos 6 casos con `mspms` (referencia)
├── run_cases.sh      # Runner bash: ejecuta ms_sim.py en paralelo y loguea
├── mspms_ref.txt     # Referencia/notas de mspms
├── logs/             # Salidas acumulativas de cada corrida
└── venv/             # Entorno virtual con msprime, numpy y dendropy
```

### 2. Casos en `msprime` (directo)

```bash
python ms_sim.py            # corre todos
python ms_sim.py 1 3 5      # solo los casos indicados
```

### 3. Referencia con `mspms`

```bash
python mspms_cases.py           # corre todos los casos con mspms
python mspms_cases.py 1 3       # solo los indicados
```


## Los 6 casos

| Caso | Comando `ms` (resumen) |
|------|------------------------|
| 1 | `ms 10 100000 -t 10 -r 10 100000 -I 2 2 8 -en 0.25 2 0.2 -eN 0.4 10.01 -eN 1 0.01 -ej 3 2 1` | 
| 2 | `ms 15 20000 -t 10 -r 10 100000 -I 3 10 4 1 -ma x 5 5 5 x 5 5 5 x -ej .7 2 1 -eN 0.8 15 -ej 1 3 1` | 
| 3 | `ms 15 100000 ... -I 3 10 4 1 -ma x 1 2 3 x 4 5 6 x -eN 1 .1 -eN 3 10 -ej .7 2 1 -ej 4 3 1` | 
| 4 | `ms 4 100000 -t 10 -r 10 100000 -I 2 2 2 5.0` | 
| 5 | `ms 4 100000 -t 10 -r 10 100000 -I 2 2 2 -ma x 10 5 x` |
| 6 | `ms 20 50 -t 1000 -r 2000 100000` |

Todos usan las semillas `-seeds 40328 19150 54118`. En `msprime` las tres
semillas de `ms` se combinan en una sola mediante MD5
(`get_single_seed` en `ms_sim.py`).

### Parámetros del motor de simulación (`msprime.sim_ancestry`)

| Parámetro | Definición |
| :--- | :--- |
| **`samples`** | **Muestras a rastrear:** linajes iniciales en el presente. Define cuántos cromosomas (`ploidy=1`) se muestrean de cada población. |
| **`sequence_length`** | **Longitud del locus ($L$):** largo total de la secuencia cromosómica simulada. |
| **`recombination_rate`** | **Tasa de recombinación ($r$):** probabilidad de entrecruzamiento por par de bases por generación. |
| **`random_seed`** | **Semilla aleatoria:** entero que inicializa el generador de números. |

## Validación

Cada corrida reporta, por caso, dos estadísticos comparables entre ambos
simuladores:

| Estadístico |  Cálculo |
|-------------|----------|
| **T_MRCA** |  `ts.first().tmrca(s[0], s[1])` (en `mspms`: altura del MRCA de las hojas 1 y 2 del primer árbol Newick, × `SCALE`) |
| **Nº de árboles** | `ts.num_trees` (en `mspms`: cantidad de árboles Newick por réplica) |

> **Nota:** 
> La comparación es estadística: las medias y desvíos sobre muchas réplicas

## Referencias

- [msprime: switch from other simulators](https://tskit.dev/msprime/docs/stable/switch_from_other_simulators.html)
- Hudson, R. R. (2002). *Generating samples under a Wright–Fisher neutral model of genetic variation.* Bioinformatics, 18(2), 337–338.
