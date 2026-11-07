#!/usr/bin/env python3
"""Mide las variantes de msprime: una simulación por vez, en rondas intercaladas.

Se intercalan para que una carga externa pasajera afecte a todas por igual.
Retoma donde quedó: saltea lo que ya está en results.jsonl y hashes.jsonl.
"""
import csv
import json
import os
import subprocess

ROOT = os.path.expanduser("~/msprime-opt")
B = f"{ROOT}/build"
REPO = os.path.expanduser("~/msprime-benchmarks")
PY = f"{B}/venv/bin/python"
# wheel_default: el wheel sin tocar malloc, para ver lo que obtiene un usuario normal
VARIANTS = ["base", "if", "block4k", "block4k_if"]
EVENTS = "cycles,instructions,instructions:u,cache-references,cache-misses,branch-misses,page-faults"
# Con el umbral dinámico de malloc, el heap se devuelve al sistema o no según detalles del
# binario, y eso mezcla ~320 fallos de página por réplica en la comparación. Se fija para todas.
MALLOC = ["MALLOC_TRIM_THRESHOLD_=134217728", "MALLOC_MMAP_THRESHOLD_=67108864"]
ROUNDS = 1
CASES = [1, 2, 3, 4, 5, 6]
OUT = f"{ROOT}/results_block4k.jsonl"
HASHES = f"{ROOT}/hashes_block4k.jsonl"
# El if no cambia resultados (sumar 0 no cambia un double): el hash compara solo block_size
HASH_VARIANTS = ["base", "block4k"]
HASH_CASES = ((1, 100_000), (2, 20_000), (3, 100_000), (4, 100_000), (5, 100_000), (6, 50))
STAT = f"{ROOT}/stat.csv"


def run_once(variant, case, rnd):
    malloc = [] if variant == "wheel_default" else MALLOC
    path = "wheel" if variant == "wheel_default" else variant
    cmd = ["sudo", "-n", "env", "OPENBLAS_NUM_THREADS=1", "PYTHONDONTWRITEBYTECODE=1",
           *malloc, f"PYTHONPATH={B}/v_{path}",
           "perf", "stat", "-x,", "-e", EVENTS, "-o", STAT,
           "--", PY, "ms_sim.py", str(case)]
    r = subprocess.run(cmd, cwd=REPO, stdout=subprocess.PIPE, text=True, check=True)
    subprocess.run(["sudo", "-n", "chown", f"{os.getuid()}:{os.getgid()}", STAT], check=True)
    row = {"variant": variant, "case": case, "round": rnd}
    for line in csv.reader(l for l in open(STAT) if l.strip() and not l.startswith("#")):
        if line[2] in EVENTS.split(","):
            row[line[2]] = float(line[0])
            row[line[2] + "_pct"] = float(line[4])
    # ms_sim imprime el tiempo del caso en la línea FIN
    fin = [l for l in r.stdout.splitlines() if l.startswith("== FIN")][-1]
    row["seconds"] = float(fin.split("|")[2].split()[0])
    row["stats"] = [l.strip() for l in r.stdout.splitlines() if "media" in l]
    return row


HASH_CODE = """
import hashlib, itertools, sys
import numpy as np
import msprime.ancestry as A
cap = {}
orig = A._wrap_replicates
def wrap(sim, *a, **k):
    cap["sim"] = sim
    return orig(sim, *a, **k)
A._wrap_replicates = wrap
sys.path.insert(0, ".")
import ms_sim
case, n = int(sys.argv[1]), int(sys.argv[2])
rows = []
for ts in itertools.islice(ms_sim.CASES[case](), n):
    s = ts.samples()
    rows.append((ts.first().tmrca(s[0], s[1]), ts.num_trees, ts.num_nodes, ts.num_edges, ts.max_root_time))
print(hashlib.sha256(np.asarray(rows, dtype=float).tobytes()).hexdigest()[:16],
      cap["sim"].num_fenwick_rebuilds, cap["sim"].num_segment_blocks)
"""


def hash_results(variant, case, n):
    path = "wheel" if variant == "wheel_default" else variant
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", PYTHONPATH=f"{B}/v_{path}",
               PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY, "-c", HASH_CODE, str(case), str(n)], cwd=REPO, env=env,
                       stdout=subprocess.PIPE, text=True, check=True)
    h, rebuilds, blocks = r.stdout.split()
    return h, int(rebuilds), int(blocks)


def load(path, key):
    if not os.path.exists(path):
        return set()
    return {tuple(json.loads(l)[k] for k in key) for l in open(path) if l.strip()}


def main():
    done = load(OUT, ("variant", "case", "round"))
    with open(OUT, "a") as fh:
        for rnd in range(ROUNDS):
            for case in CASES:
                for v in VARIANTS:
                    if (v, case, rnd) in done:
                        continue
                    row = run_once(v, case, rnd)
                    fh.write(json.dumps(row) + "\n")
                    fh.flush()
                    print(v, case, rnd, row["seconds"], flush=True)
    done = load(HASHES, ("variant", "case"))
    with open(HASHES, "a") as fh:
        for v in HASH_VARIANTS:
            for case, n in HASH_CASES:
                if (v, case) in done:
                    continue
                h, rebuilds, blocks = hash_results(v, case, n)
                fh.write(json.dumps({"variant": v, "case": case, "n": n,
                                     "hash": h, "rebuilds": rebuilds,
                                     "segment_blocks": blocks}) + "\n")
                fh.flush()
                print("hash", v, case, h, rebuilds, blocks, flush=True)
    print("listo", flush=True)


if __name__ == "__main__":
    main()
