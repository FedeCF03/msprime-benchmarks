#!/usr/bin/env python3
"""
Ejecuta en msprime los 6 casos traducidos desde ms.

Uso:
    python run_cases.py                  # corre todos
    python run_cases.py 1 3 5            # solo los casos 1, 3 y 5

"""
import argparse
import hashlib
import sys
import time

import msprime
import numpy as np

NE    = 1
SCALE = 4 * NE


def get_single_seed(seeds):
    assert len(seeds) == 3
    m = hashlib.md5()
    for s in seeds:
        m.update(f"{s}:".encode())
    return int(m.hexdigest(), 16) % (2 ** 32)


seeds = [40328, 19150, 54118]
seed_int = get_single_seed(seeds)


def T(t):                    return t * SCALE
def mu_rate(theta, L):       return theta / (SCALE * L)
def re_rate(rho, L):         return rho / (SCALE * L)
def mig_rate(M):             return M / SCALE
def size(N_ms):              return N_ms * 2 * NE


# ------------------------------------------------------------------
# Caso 6: modelo básico, sin estructura
#   ms: 20 50 -seeds 40328 19150 54118 -t 1000 -r 2000 100000
# ------------------------------------------------------------------
def case6():
    nsam, rep, L, rho, theta = 20, 50, 100_000, 2000, 1000
    return msprime.sim_ancestry(
        samples=nsam,
        population_size=size(1.0),
        ploidy=1,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
    )


# ------------------------------------------------------------------
# Caso 5: 2 poblaciones, migración asimétrica (-ma)
#   ms: 4 100000 ... -I 2 2 2 -ma x 10 5 x
# ------------------------------------------------------------------
def case5():
    nsam, rep, L, rho, theta = 4, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=size(1.0))
    dem.add_population(name="p1", initial_size=size(1.0))
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(10.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.sort_events()

    return msprime.sim_ancestry(
        samples={"p0": 2, "p1": 2},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
        ploidy=1,
    )


# ------------------------------------------------------------------
# Caso 4: 2 poblaciones, migración simétrica (-I ... 5.0)
#   ms: 4 100000 ... -I 2 2 2 5.0
# ------------------------------------------------------------------
def case4():
    nsam, rep, L, rho, theta = 4, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=size(1.0))
    dem.add_population(name="p1", initial_size=size(1.0))
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.sort_events()

    return msprime.sim_ancestry(
        samples={"p0": 2, "p1": 2},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
        ploidy=1,
    )


# ------------------------------------------------------------------
# Caso 3: 3 poblaciones, -ma, -eN x2, -ej x2
#   ms: 15 100000 ... -I 3 10 4 1
#       -ma x 1 2 3 x 4 5 6 x  -eN 1 .1 -eN 3 10
#       -ej .7 2 1  -ej 4 3 1
# ------------------------------------------------------------------
def case3():
    nsam, rep, L, rho, theta = 15, 100_000, 100_000, 10, 10
    dem = msprime.Demography()

    dem.add_population(name="p0", initial_size=size(1.0), initially_active=True)
    dem.add_population(name="p1", initial_size=size(1.0))
    dem.add_population(name="p2", initial_size=size(1.0))

    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(1.0))
    dem.set_migration_rate(source="p0", dest="p2", rate=mig_rate(2.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(3.0))
    dem.set_migration_rate(source="p1", dest="p2", rate=mig_rate(4.0))
    dem.set_migration_rate(source="p2", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p1", rate=mig_rate(6.0))

    dem.add_population_split(time=T(0.7), derived=["p1"], ancestral="p0")

    for p in ("p0", "p2"):
        dem.add_population_parameters_change(
            time=T(1.0), population=p, initial_size=size(0.1)
        )
        dem.add_population_parameters_change(
            time=T(3.0), population=p, initial_size=size(10.0)
        )

    dem.add_population_split(time=T(4.0), derived=["p2"], ancestral="p0")
    dem.sort_events()

    return msprime.sim_ancestry(
        samples={"p0": 10, "p1": 4, "p2": 1},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
        ploidy=1,
    )


# ------------------------------------------------------------------
# Caso 2:
#   ms: 15 20000 ... -I 3 10 4 1 -ma x 5 5 5 x 5 5 5 x
#       -eN 0.8 15 -ej .7 2 1 -ej 1 3 1
# ------------------------------------------------------------------
def case2():
    nsam, rep, L, rho, theta = 15, 20_000, 100_000, 10, 10
    dem = msprime.Demography()

    dem.add_population(name="p0", initial_size=size(1.0), initially_active=True)
    dem.add_population(name="p1", initial_size=size(1.0))
    dem.add_population(name="p2", initial_size=size(1.0))

    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p0", dest="p2", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p1", dest="p2", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p1", rate=mig_rate(5.0))

    for p in ("p0", "p2"):
        dem.add_population_parameters_change(
            time=T(0.8), population=p, initial_size=size(15.0)
        )

    dem.add_population_split(time=T(0.7), derived=["p1"], ancestral="p0")
    dem.add_population_split(time=T(1.0), derived=["p2"], ancestral="p0")
    dem.sort_events()

    return msprime.sim_ancestry(
        samples={"p0": 10, "p1": 4, "p2": 1},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
        ploidy=1,
    )


# ------------------------------------------------------------------
# Caso 1: 2 poblaciones, -eN/-en/-ej
#   ms: 10 100000 ... -I 2 2 8 -eN 0.4 10.01 -eN 1 0.01
#       -en 0.25 2 0.2 -ej 3 2 1
# ------------------------------------------------------------------
def case1():
    nsam, rep, L, rho, theta = 10, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=size(1.0), initially_active=True)
    dem.add_population(name="p1", initial_size=size(1.0))

    for p in ("p0", "p1"):
        dem.add_population_parameters_change(
            time=T(0.4), population=p, initial_size=size(10.01)
        )
        dem.add_population_parameters_change(
            time=T(1.0), population=p, initial_size=size(0.01)
        )

    dem.add_population_parameters_change(
        time=T(0.25), population="p1", initial_size=size(0.2)
    )
    dem.add_population_split(time=T(3.0), derived=["p1"], ancestral="p0")
    dem.sort_events()

    return msprime.sim_ancestry(
        samples={"p0": 2, "p1": 8},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=seed_int,
        num_replicates=rep,
        ploidy=1,
    )


# ------------------------------------------------------------------
# Registro de casos
# ------------------------------------------------------------------
CASES = {1: case1, 2: case2, 3: case3, 4: case4, 5: case5, 6: case6}


# ------------------------------------------------------------------
# Estadísticas
# ------------------------------------------------------------------
def stats(gen, label=""):
    """Estadísticas por réplica.

    | Estadístico   | Qué valida             | Cálculo                      |
    |---------------|------------------------|------------------------------|
    | T_MRCA        | escala de coalescencia | ts.first().tmrca(s[0], s[1]) |
    | Nº de árboles | recombinación (rho)    | ts.num_trees                 |
    """
    rows = []
    for ts in gen:
        s = ts.samples()
        rows.append((
            ts.first().tmrca(s[0], s[1]),
            ts.num_trees,
        ))

    arr = np.asarray(rows, dtype=float)
    n   = arr.shape[0]
    mu  = arr.mean(axis=0)
    sd  = arr.std(axis=0)

    print(f"--- {label}  (n={n} réplicas) ---")
    print(f"  T_MRCA                        : media = {mu[0]:.4f} gen  "
          f"desvio = {sd[0]:.4f}   [escala de coalescencia]")
    print(f"  Nº de árboles                 : media = {mu[1]:.2f}  "
          f"desvio = {sd[1]:.2f}   [recombinación (rho)]")


def main():
    ap = argparse.ArgumentParser(description="Corre casos ms->msprime")
    ap.add_argument("cases", nargs="*", type=int)
    args = ap.parse_args()

    selected = args.cases or sorted(CASES.keys())
    for c in selected:
        if c not in CASES:
            print(f"!! Caso {c} no existe", file=sys.stderr)
            continue
        t0 = time.perf_counter()
        print(f"== INICIO caso {c}  |  {time.strftime('%Y-%m-%d %H:%M:%S')}")
        stats(CASES[c](), label=f"caso {c}")
        t1 = time.perf_counter()
        print(f"== FIN caso {c}  |  {time.strftime('%Y-%m-%d %H:%M:%S')}  |  "
              f"{t1 - t0:.2f} s  | OK")


if __name__ == "__main__":
    main()
