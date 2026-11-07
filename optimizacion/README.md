# Optimización del árbol de Fenwick

Prueba de la sugerencia de aplicar inlining en las funciones de Fenwick de
msprime 1.4.4. El perfil del caso 1 mostraba `fenwick_increment` (17.7 %) y
`fenwick_rebuild` (6.0 %) entre los hotspots: `fenwick_rebuild` recorre las
65 536 posiciones del árbol en cada réplica y llama a `fenwick_increment`
aunque casi todas valgan 0.

El cambio elegido es un `if` de 3 líneas en `fenwick_rebuild`
(`fenwick_if.patch`) que no llama a la función cuando el valor es 0.

El segundo cambio ataca la causa: el árbol tiene 65 536 posiciones porque
`ancestry.py` reserva los segmentos en bloques de 64K, y msprime lo vuelve a
crear en cada réplica (`fenwick_alloc` y `fenwick_rebuild` ponen en cero
~1.5 MB por réplica, el 9 % del caso 1 en `memset`). `block4k.patch` baja el
bloque a 4K, una línea.

---

## Estructura

```
optimizacion/
├── fenwick_if.patch        # El if, sobre lib/fenwick.c de msprime 1.4.4
├── block4k.patch           # Bloques de 4K, sobre msprime/ancestry.py de msprime 1.4.4
├── scripts/
│   ├── setup_variants.py   # Compila las variantes de msprime fuera del repo
│   ├── measure.py          # Corre los casos con perf stat, una simulación por vez
│   ├── measure_big.py      # Una simulación grande (una réplica) con perf stat
│   └── run_ctests.sh       # Compila y corre los tests C de msprime (CUnit)
└── resultados/             # Mediciones en JSON Lines (una corrida por línea)
```

Los scripts trabajan en `~/msprime-opt`: ahí descargan msprime y GSL,
compilan cada variante en `build/v_<variante>` y escriben los resultados. No
modifican el msprime del `.venv` del repo.

## Resultados

Instrucciones ejecutadas (`instructions:u`), `base` → `if`:

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
- Los tiempos de los casos 2 a 5 todavía no son confiables: se midieron con la máquina cargada.

### Bloques de 4K

Diferencia con `base` en instrucciones (`instructions:u`) y, entre paréntesis,
en tiempo. Una corrida por variante y caso, intercaladas, con la máquina algo
cargada (load average ~2):

| Caso | `if` | `block4k` | `block4k` + `if` |
|------|------|-----------|------------------|
| 1 | −21.4 % (−20.9 %) | −43.5 % (−43.3 %) | −44.7 % (−43.9 %) |
| 2 | −10.2 % (−7.3 %) | −20.7 % (−19.2 %) | −21.4 % (−19.6 %) |
| 3 | −18.1 % (−13.7 %) | −36.5 % (−34.1 %) | −37.7 % (−36.4 %) |
| 4 | −22.0 % (−17.8 %) | −44.6 % (−41.3 %) | −46.0 % (−41.9 %) |
| 5 | −22.3 % (−16.4 %) | −45.0 % (−41.1 %) | −46.5 % (−42.3 %) |
| 6 | 0.0 % (+0.9 %) | −1.1 % (−3.2 %) | −1.0 % (−2.3 %) |

- El hash de `block4k` es igual al de `base` en todas las réplicas de los 6
  casos. En ninguno el heap de segmentos pasó del primer bloque de 4096: las
  posiciones de más del árbol son ceros y sumar 0 no cambia el resultado.
- Pasan los 2354 tests de Python en `block4k` y `block4k_if`. Los de C no
  cambian: el bloque se fija en Python y el C de `block4k_if` es el de `if`.

Simulación grande, una réplica (`measure_big.py`, población 10 000,
recombinación 1e-8):

| Simulación | Semillas | Mismo hash | Instrucciones (media, rango) | Tiempo (media, rango) |
|------------|----------|------------|------------------------------|-----------------------|
| 500 muestras, 5e7 pb (hasta ~32K segmentos) | 6 | 0 de 6 | +0.2 % (−1.3 a +1.9) | +2.9 % (−5.9 a +10.7) |
| 2000 muestras, 1e8 pb (~64K segmentos o más) | 3 | 0 de 3 | +0.8 % (−0.7 a +2.2) | +3.3 % (+2.0 a +4.4) |

- No hay costo medible en instrucciones: las diferencias van para los dos
  lados porque cada variante simula otra realización.
- Cuando el heap pasa de 4096 segmentos, `block4k` da otra tree sequence con
  la misma semilla: los segmentos nuevos toman otros ids, que son su posición
  en el árbol de Fenwick, y el mismo número aleatorio elige otro segmento.
- No se midieron simulaciones con millones de segmentos, donde el heap
  crecería de a 4096 y copiaría el árbol entero en cada expansión.

## Cómo reproducir

### 1. Compilar las variantes

```bash
python3 optimizacion/scripts/setup_variants.py
```

Descarga el sdist de msprime 1.4.4 y los paquetes de GSL (se extraen con
`dpkg -x`, sin instalarlos), crea un entorno en `~/msprime-opt/build/venv` y
compila `base`, `inline`, `symbolic`, `lto`, `if`, `force`, `native`,
`block4k`, `block4k_if` y `pgo`. `block4k` copia `base` y cambia solo
`ancestry.py`. Si se corta, retoma donde quedó.

### 2. Medir

```bash
python3 optimizacion/scripts/measure.py
```

Necesita `sudo` sin contraseña para `perf`. Las variantes, los casos, las
rondas y los casos con hash se eligen editando las constantes del principio
(`VARIANTS`, `CASES`, `ROUNDS`, `HASH_VARIANTS`, `HASH_CASES`).

La simulación grande recibe muestras, largo y semillas:

```bash
cd optimizacion/scripts && ~/msprime-opt/build/venv/bin/python measure_big.py 500 5e7 1,2,3,4,5 base block4k
```

### 3. Tests de msprime

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
| `results_block4k.jsonl` | `base`, `if`, `block4k` y `block4k_if` en los 6 casos, una corrida |
| `hashes_block4k.jsonl` | Hash de todas las réplicas de los 6 casos y bloques de segmentos usados, en `base` y `block4k` |
| `results_big.jsonl` | Simulaciones grandes: contadores, hash de las tablas y bloques usados, por semilla |

`results.jsonl`, `hashes.jsonl` y `hashes2.jsonl` incluyen también variantes
que se probaron y se descartaron. Las de Fenwick son `base`, `inline`, `force`
e `if`.
