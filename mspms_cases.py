#!/usr/bin/env python3
"""
Corre los 6 test cases originales de ms en `mspms'

Uso:
    python mspms_cases.py                  # corre todos los casos
    python mspms_cases.py 1 3 5            # solo los casos indicados

"""
import argparse
import os
import subprocess
import sys
import time

import dendropy
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from ms_sim import SCALE  # unidades de ms -> generaciones (4 * NE)

MSPMS = os.path.join(SCRIPT_DIR, "venv", "bin", "mspms")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
SEEDS = ["40328", "19150", "54118"]

CASES = {
    1: dict(nsam=10, L=100_000, reps=100000, args=[
        "-t", "10", "-r", "10", "100000",
        "-I", "2", "2", "8",
        "-en", "0.25", "2", "0.2",
        "-eN", "0.4", "10.01", "-eN", "1", "0.01",
        "-ej", "3", "2", "1",
    ]),
    2: dict(nsam=15, L=100_000, reps=20000, args=[
        "-t", "10", "-r", "10", "100000",
        "-I", "3", "10", "4", "1",
        "-ma", "x", "5", "5", "5", "x", "5", "5", "5", "x",
        "-ej", ".7", "2", "1",
        "-eN", "0.8", "15",
        "-ej", "1", "3", "1",
    ]),
    3: dict(nsam=15, L=100_000, reps=100000, args=[
        "-t", "10", "-r", "10", "100000",
        "-I", "3", "10", "4", "1",
        "-ma", "x", "1", "2", "3", "x", "4", "5", "6", "x",
        "-ej", ".7", "2", "1",
        "-eN", "1", ".1", "-eN", "3", "10",
        "-ej", "4", "3", "1",
    ]),
    4: dict(nsam=4, L=100_000, reps=100000, args=[
        "-t", "10", "-r", "10", "100000",
        "-I", "2", "2", "2", "5.0",
    ]),
    5: dict(nsam=4, L=100_000, reps=100000, args=[
        "-t", "10", "-r", "10", "100000",
        "-I", "2", "2", "2",
        "-ma", "x", "10", "5", "x",
    ]),
    6: dict(nsam=20, L=100_000, reps=50, args=[
        "-t", "1000", "-r", "2000", "100000",
    ]),
}


# ------------------------------------------------------------------
# Árboles con DendroPy
# ------------------------------------------------------------------
def parse_newick(s):
    """Parsea un Newick con DendroPy"""
    s = s.strip()
    if s.startswith("["):                 # prefijo [longitud] del segmento
        s = s[s.index("]") + 1:].strip()
    tree = dendropy.Tree.get(data=s, schema="newick")
    tree.is_rooted = True
    return tree


def newick_tmrca(tree, la, lb):
    node = tree.mrca(taxon_labels=[la, lb])
    return float("nan") if node is None else node.distance_from_tip()


# ------------------------------------------------------------------
# Lector en streaming de la salida de mspms
# ------------------------------------------------------------------
def iter_mspms_replicates(cmd):

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    newicks = []
    segsites = None
    state = "header"        # header -> trees -> segsites -> positions -> haps

    def flush():
        if segsites is None:
            return None
        tmrca = float("nan")
        if newicks:
            tree = parse_newick(newicks[0])
            tmrca = newick_tmrca(tree, "1", "2")
        return {
            "n_trees": len(newicks),
            "tmrca_ms": tmrca,
        }

    for line in proc.stdout:
        stripped = line.strip()
        if stripped == "//":
            rep = flush()
            if rep is not None:
                yield rep
            newicks, segsites = [], None
            state = "trees"
        elif stripped.startswith("segsites:"):
            segsites = int(stripped.split(":")[1])
            state = "positions" if segsites > 0 else "trees"
        elif stripped.startswith("positions:"):
            state = "haps"
        elif state == "trees" and (stripped.startswith("[")
                                   or stripped.startswith("(")):
            newicks.append(stripped)

    rep = flush()
    if rep is not None:
        yield rep
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"mspms falló (rc={proc.returncode}): "
                           f"{proc.stderr.read().strip()}")


# ------------------------------------------------------------------
# Runner por caso
# ------------------------------------------------------------------
def run_case(case):
    cfg = CASES[case]
    nsam, reps = cfg["nsam"], cfg["reps"]

    cmd = [MSPMS, str(nsam), str(reps), "-seeds", *SEEDS, *cfg["args"],
           "-T", "-p", "6"]
    cmd_str = " ".join(cmd)

    os.makedirs(LOG_DIR, exist_ok=True)
    logfile = os.path.join(LOG_DIR, f"mspms_case{case}.log")

    t0 = time.perf_counter()
    print(f"== INICIO caso {case} (mspms)  |  "
          f"{time.strftime('%Y-%m-%d %H:%M:%S')}")

    rows = []
    for rep in iter_mspms_replicates(cmd):
        rows.append((rep["tmrca_ms"] * SCALE,   # 4N0 -> generaciones
                     rep["n_trees"]))

    t1 = time.perf_counter()

    arr = np.asarray(rows, dtype=float)
    n   = arr.shape[0]
    mu  = arr.mean(axis=0)
    sd  = arr.std(axis=0)

    lines = [
        f"--- caso {case} (mspms)  (n={n} réplicas) ---",
        f"  T_MRCA                        : media = {mu[0]:.4f} gen  "
        f"desvio = {sd[0]:.4f}   [escala de coalescencia]",
        f"  Nº de árboles                 : media = {mu[1]:.2f}  "
        f"desvio = {sd[1]:.2f}   [recombinación (rho)]",
        f"  cmd: {cmd_str}",
    ]
    block = "\n".join(lines)
    print(block)

    with open(logfile, "a") as fh:
        fh.write("\n" + "=" * 67 + "\n")
        fh.write(f"== INICIO caso {case} (mspms)  |  "
                 f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"== cmd: {cmd_str}\n")
        fh.write("=" * 67 + "\n")
        fh.write(block + "\n")
        fh.write(f"== FIN caso {case} (mspms)  |  "
                 f"{time.strftime('%Y-%m-%d %H:%M:%S')}  |  "
                 f"{t1 - t0:.2f} s  | OK\n")
        fh.write("=" * 67 + "\n")
    print(f"== FIN caso {case} (mspms)  |  {time.strftime('%Y-%m-%d %H:%M:%S')}"
          f"  |  {t1 - t0:.2f} s  | OK  |  log: {logfile}")


def main():
    ap = argparse.ArgumentParser(
        description="Corre los test cases de ms en mspms y loguea "
                    "T_MRCA y nº de árboles")
    ap.add_argument("cases", nargs="*", type=int)
    args = ap.parse_args()

    if not os.path.exists(MSPMS):
        sys.exit(f"No se encuentra {MSPMS} (activá el virtualenv)")

    selected = args.cases or sorted(CASES.keys())
    for c in selected:
        if c not in CASES:
            print(f"!! Caso {c} no existe", file=sys.stderr)
            continue
        run_case(c)


if __name__ == "__main__":
    main()
