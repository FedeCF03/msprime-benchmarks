# Optimización del árbol de Fenwick

Prueba de la sugerencia de aplicar inlining en las funciones de Fenwick de
msprime 1.4.4. El perfil del caso 1 mostraba `fenwick_increment` (17.7 %) y
`fenwick_rebuild` (6.0 %) entre los hotspots: `fenwick_rebuild` recorre las
65 536 posiciones del árbol en cada réplica y llama a `fenwick_increment`
aunque casi todas valgan 0.

Se probaron dos cosas, por separado y juntas:

- **`if`** (`fenwick_if.patch`): un `if` de 3 líneas en `fenwick_rebuild` que
  no llama a la función cuando el valor es 0.
- **LTO**: compilar con `-flto -fno-semantic-interposition`, sin tocar código.
  Deja que el compilador meta `fenwick_increment` (y otras funciones) adentro
  de quien las llama, aunque estén en otro archivo.

---

## Estructura

```
optimizacion/
├── fenwick_if.patch          # El if, sobre lib/fenwick.c de msprime 1.4.4
├── scripts/
│   ├── setup_variants.py     # Compila las variantes de msprime fuera del repo
│   ├── profile_perf_opt.sh   # profile_perf.sh con una variante: logs/perf/optimizacion/
│   ├── measure.py            # Corre los casos con perf stat, una simulación por vez
│   └── run_ctests.sh         # Compila y corre los tests C de msprime (CUnit)
└── resultados/               # Mediciones en JSON Lines (una corrida por línea)
```

Los scripts trabajan en `~/msprime-opt`: ahí descargan msprime y GSL,
compilan cada variante en `build/v_<variante>` y escriben los resultados. No
modifican el msprime del `.venv` del repo.

## Resultados

### Perfilado de los 6 casos con `if`, `lto` e `if_lto`

Las mismas corridas de `profile_perf.sh` (mismo Python del `.venv`, mismos
eventos, `perf record -g -F 99` alrededor de `perf stat`, solo
`OPENBLAS_NUM_THREADS=1`), con `PYTHONPATH` apuntando a cada variante. Una
corrida por caso, en orden: casos 1 a 6 con `if`, después con `lto` y después
con `if_lto` (11/11/2026). Salida en `logs/perf/optimizacion/caseN_<variante>.{txt,data,report.log}`.
Se comparan contra `logs/perf/caseN.txt` (msprime 1.4.4 de PyPI, 25/10/2026).

Instrucciones ejecutadas (evento `instructions`, incluye las del kernel):

| Caso | Original | `if` | `lto` | `if_lto` |
|------|----------|------|-------|----------|
| 1 | 246.3 G | 194.2 G (−21.2 %) | 290.1 G (+17.8 %) * | 246.3 G (0.0 %) * |
| 2 | 196.8 G | 177.7 G (−9.7 %) | 163.6 G (−16.9 %) | 161.3 G (−18.1 %) |
| 3 | 301.2 G | 248.1 G (−17.6 %) | 236.4 G (−21.5 %) | 229.9 G (−23.7 %) |
| 4 | 252.2 G | 197.5 G (−21.7 %) | 189.3 G (−24.9 %) | 182.5 G (−27.6 %) |
| 5 | 247.0 G | 192.6 G (−22.0 %) | 185.4 G (−24.9 %) | 178.0 G (−27.9 %) |
| 6 | 33.3 G | 33.4 G (+0.2 %) | 31.3 G (−6.0 %) | 31.3 G (−6.2 %) |

Tiempo y aceleración contra el original:

| Caso | Original | `if` | `lto` | `if_lto` |
|------|----------|------|-------|----------|
| 1 | 67.91 s | 51.20 s (1.33x) | 100.12 s (0.68x) * | 101.23 s (0.67x) * |
| 2 | 51.49 s | 39.14 s (1.32x) | 36.43 s (1.41x) | 37.79 s (1.36x) |
| 3 | 84.23 s | 59.31 s (1.42x) | 56.94 s (1.48x) | 52.67 s (1.60x) |
| 4 | 68.69 s | 47.84 s (1.44x) | 45.32 s (1.52x) | 40.91 s (1.68x) |
| 5 | 67.50 s | 47.18 s (1.43x) | 53.62 s (1.26x) | 39.57 s (1.71x) |
| 6 | 8.89 s | 7.53 s (1.18x) | 8.52 s (1.04x) | 6.99 s (1.27x) |

\* En el caso 1, `lto` e `if_lto` tuvieron 24.3 y 17.1 millones de fallos de
página, y pasaron 50.2 y 37.1 s en el kernel. En esa corrida, `malloc`
devolvía memoria al sistema en cada réplica y la volvía a pedir. El resto de
las corridas tuvo entre 10 000 y 20 000 fallos de página, como el original.
El tiempo de usuario de `lto` en el caso 1 (49.9 s) es casi igual al de `if`
(50.1 s). Con el msprime de PyPI no pasa, y no está claro por qué pasa con
algunos de los binarios compilados acá.

- **Los tiempos mezclan el cambio con el estado de la máquina.** En el caso 6,
  `if` ejecuta las mismas instrucciones que el original y tardó 18 % menos: es
  el día, no el cambio. Para tiempos confiables hace falta una máquina
  dedicada y correr el original el mismo día.
- **LTO solo baja más instrucciones que el `if`** en los casos 2 a 5, porque
  además del Fenwick resuelve otras llamadas entre archivos. `if_lto` suma
  un poco más.
- **Resultados de la simulación:** `if`, `lto` e `if_lto` dan el mismo hash
  que el original (2000 réplicas del caso 1 y 5 del caso 6).

### Instrucciones de usuario, `base` → `if`

Con `measure.py` (`instructions:u`, sin el kernel; umbrales de `malloc`
fijos para todas las variantes):

| Caso | Instrucciones | Diferencia |
|------|---------------|------------|
| 1 | 245.8 → 193.5 G | −21.3 % |
| 2 | 197.8 → 177.6 G | −10.2 % |
| 3 | 301.7 → 247.7 G | −17.9 % |
| 4 | 252.9 → 197.2 G | −22.0 % |
| 5 | 247.4 → 192.7 G | −22.1 % |
| 6 | 33.6 → 33.5 G | −0.2 % |

- Tiempo del caso 1 con la máquina libre (mediana de 3 rondas): 58.71 → 47.23 s (−19.6 %).
- Las medias y desvíos de T_MRCA y nº de árboles dan iguales que `base` en los 6 casos.
- Pasan los tests de msprime: los 8 de C (con `assert` y sanitizers) y 2354 de Python.

## Cómo reproducir

### 1. Compilar las variantes

```bash
python3 optimizacion/scripts/setup_variants.py
```

Descarga el sdist de msprime 1.4.4 y los paquetes de GSL (se extraen con
`dpkg -x`, sin instalarlos), crea un entorno en `~/msprime-opt/build/venv` y
compila `base`, `inline`, `symbolic`, `lto`, `if_lto`, `if`, `force`,
`native` y `pgo`. Si se corta, retoma donde quedó.

### 2. Perfilar como `profile_perf.sh`

```bash
optimizacion/scripts/profile_perf_opt.sh if          # casos 1 a 6 con el if
optimizacion/scripts/profile_perf_opt.sh lto 1 6     # solo los casos 1 y 6
REPS=3 optimizacion/scripts/profile_perf_opt.sh if_lto
```

Necesita `sudo` para `perf`. Escribe `logs/perf/optimizacion/caseN_<variante>.txt`,
`.data` y `.report.log`.

### 3. Medir con `perf stat`

```bash
python3 optimizacion/scripts/measure.py
```

Necesita `sudo` sin contraseña para `perf`. Las variantes, los casos, las
rondas y los casos con hash se eligen editando las constantes del principio
(`VARIANTS`, `CASES`, `ROUNDS`, `HASH_VARIANTS`, `HASH_CASES`).

### 4. Tests de msprime

Los tests C necesitan CUnit en `~/msprime-opt/build/cunit`:

```bash
cd ~/msprime-opt/build && mkdir -p debs_cunit cunit && cd debs_cunit && apt-get download libcunit1-dev libcunit1 && for d in *.deb; do dpkg -x "$d" ../cunit; done
```

```bash
bash optimizacion/scripts/run_ctests.sh if
```

Los tests de Python se corren desde la copia de la variante, con un entorno
aparte que tenga `pytest`, `pytest-xdist`, `scipy`, `bintrees`, `daiquiri`,
`kastore`, `python_jsonschema_objects`, `demes` y `newick`:

```bash
cd ~/msprime-opt/build/v_if && PYTHONPATH=$PWD ../testvenv/bin/python -m pytest tests -n 0 -q -p no:cacheprovider --ignore=tests/test_dict_encoding.py
```

## Archivos de resultados

| Archivo | Contenido |
|---------|-----------|
| `results.jsonl` | Casos 1 y 6, 3 rondas, máquina libre. Contadores de `perf stat`, tiempo y medias impresas |
| `hashes.jsonl` | Hash de los estadísticos de cada réplica (5000 del caso 1, 50 del caso 6) |
| `hashes2.jsonl` | Hash y cantidad de rebuilds de Fenwick por caso, sobre parte de las réplicas |
| `results_if_maquina_cargada.jsonl` | `base` e `if` en los 6 casos, una corrida, máquina cargada |
| `results_if.jsonl` | `base` e `if` en los 6 casos, segunda corrida |

`results.jsonl`, `hashes.jsonl` y `hashes2.jsonl` incluyen también variantes
que se probaron y se descartaron. Las de Fenwick son `base`, `inline`, `force`
e `if`.
