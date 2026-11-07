#!/usr/bin/env python3
"""Mide una simulación grande (una sola réplica) en cada variante, una por vez.

Sirve para ver qué pasa cuando el heap de segmentos tiene que crecer: con bloques
de 4K crece de a 4096 segmentos, con el valor de msprime de a 65 536.
Uso: measure_big.py <muestras> <largo> <semillas separadas por coma> [variantes...]
"""
import csv
import json
import os
import subprocess
import sys

from measure import B, EVENTS, MALLOC, PY, ROOT, STAT

OUT = f"{ROOT}/results_big.jsonl"

BIG_CODE = """
import hashlib, json, sys, time
import msprime
import msprime.ancestry as A
cap = {}
orig = A._wrap_replicates
def wrap(sim, *a, **k):
    cap["sim"] = sim
    return orig(sim, *a, **k)
A._wrap_replicates = wrap
samples, length, seed = int(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3])
t0 = time.perf_counter()
ts = msprime.sim_ancestry(samples=samples, population_size=10_000, sequence_length=length,
                          recombination_rate=1e-8, random_seed=seed)
seconds = time.perf_counter() - t0
t = ts.tables
h = hashlib.sha256()
for col in (t.nodes.time, t.nodes.flags, t.edges.left, t.edges.right, t.edges.parent,
            t.edges.child):
    h.update(col.tobytes())
sim = cap["sim"]
print(json.dumps({"sim_seconds": seconds, "num_trees": ts.num_trees, "num_edges": ts.num_edges,
                  "hash": h.hexdigest()[:16], "segment_block_size": sim.segment_block_size,
                  "segment_blocks": sim.num_segment_blocks,
                  "avl_node_blocks": sim.num_avl_node_blocks,
                  "node_mapping_blocks": sim.num_node_mapping_blocks,
                  "rebuilds": sim.num_fenwick_rebuilds}))
"""


def run_big(variant, samples, length, seed):
    cmd = ["sudo", "-n", "env", "OPENBLAS_NUM_THREADS=1", "PYTHONDONTWRITEBYTECODE=1",
           *MALLOC, f"PYTHONPATH={B}/v_{variant}",
           "perf", "stat", "-x,", "-e", EVENTS, "-o", STAT,
           "--", PY, "-c", BIG_CODE, str(samples), str(length), str(seed)]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    subprocess.run(["sudo", "-n", "chown", f"{os.getuid()}:{os.getgid()}", STAT], check=True)
    row = {"variant": variant, "samples": samples, "length": length, "seed": seed,
           **json.loads(r.stdout.splitlines()[-1])}
    for line in csv.reader(l for l in open(STAT) if l.strip() and not l.startswith("#")):
        if line[2] in EVENTS.split(","):
            row[line[2]] = float(line[0])
    return row


def main():
    samples, length = int(sys.argv[1]), float(sys.argv[2])
    seeds = [int(x) for x in sys.argv[3].split(",")]
    variants = sys.argv[4:] or ["base", "block4k"]
    with open(OUT, "a") as fh:
        for seed in seeds:
            for v in variants:
                row = run_big(v, samples, length, seed)
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(v, samples, length, seed, f"{row['sim_seconds']:.1f}s",
                      f"{row['instructions:u'] / 1e9:.1f}G", row["hash"],
                      "bloques", row["segment_blocks"], "x", row["segment_block_size"], flush=True)


if __name__ == "__main__":
    main()
