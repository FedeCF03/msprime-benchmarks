#!/usr/bin/env python3
"""
Ejecuta en msprime los 6 casos traducidos desde ms.

Uso:
    python run_cases.py                  # corre todos
    python run_cases.py 1 3 5            # solo los casos 1, 3 y 5

Convenciones:
    - NE = 1 (escala base, equivale a N=1 en ms)
    - Tiempos de ms (en unidades de 4N gen.) -> generaciones * SCALE
    - Tasas de mut/recomb -> se dividen por SCALE * seqlen
    - Tasas de migración (4Nm) -> se dividen por SCALE
"""
import argparse
import sys
import msprime

NE    = 1
SCALE = 4 * NE          # ms mide tiempos en unidades de 4N generaciones

def T(t):                # tiempo ms -> generaciones msprime
    return t * SCALE
def mu_rate(theta, L):   # theta = 4N*mu*L
    return theta / (SCALE * L)
def re_rate(rho, L):     # rho   = 4N*r*L
    return rho / (SCALE * L)
def mig_rate(M):         # M = 4N*m
    return M / SCALE
def size(N_ms):          # tamaño en unidades de N
    return N_ms * NE

SEED1 = 40328
SEED2 = 19150

def mutate(reps, theta, L):
    rate = mu_rate(theta, L)
    for ts in reps:
        yield msprime.sim_mutations(ts, rate=rate)
# ------------------------------------------------------------------
# Caso 6: modelo básico, sin estructura
#   ms: 20 50 -seeds 40328 19150 54118 -t 1000 -r 2000 100000
# ------------------------------------------------------------------
def case6():
    nsam, rep, L, rho, theta = 20, 50, 100_000, 2000, 1000
    reps = msprime.sim_ancestry(
        samples=nsam,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)

# ------------------------------------------------------------------
# Caso 5: 2 poblaciones, migración asimétrica (-ma)
#   ms: 4 100000 ... -I 2 2 2 -ma x 10 5 x
# ------------------------------------------------------------------
def case5():
    nsam, rep, L, rho, theta = 4, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=NE)
    dem.add_population(name="p1", initial_size=NE)
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(10.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.sort_events()

    reps = msprime.sim_ancestry(
        samples={"p0": 2, "p1": 2},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)

# ------------------------------------------------------------------
# Caso 4: 2 poblaciones, migración unidireccional (-I ... 5.0)
#   ms: 4 100000 ... -I 2 2 2 5.0
# ------------------------------------------------------------------
def case4():
    nsam, rep, L, rho, theta = 4, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=NE)
    dem.add_population(name="p1", initial_size=NE)
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.sort_events()

    reps = msprime.sim_ancestry(
        samples={"p0": 2, "p1": 2},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)

# ------------------------------------------------------------------
# Caso 3: 3 poblaciones, -ma, -eN x2, -ej x2
#   ms: 15 100000 ... -I 3 10 4 1
#       -ma x 1 2 3 x 4 5 6 x  -eN 1 .1 -eN 3 10
#       -ej .7 2 1  -ej 4 3 1
# ------------------------------------------------------------------
def case3():
    nsam, rep, L, rho, theta = 15, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    
    dem.add_population(name="p0", initial_size=NE, initially_active=True)
    dem.add_population(name="p1", initial_size=NE)
    dem.add_population(name="p2", initial_size=NE)

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

    reps = msprime.sim_ancestry(
        samples={"p0": 10, "p1": 4, "p2": 1}, 
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)
# ------------------------------------------------------------------
# Caso 2:
#   ms: 15 20000 ... -I 3 10 4 1 -ma x 5 5 5 x 5 5 5 x
#       -eN 0.8 15 -ej .7 2 1 -ej 1 3 1
# ------------------------------------------------------------------
def case2():
    nsam, rep, L, rho, theta = 15, 20_000, 100_000, 10, 10
    dem = msprime.Demography()
    
    # p0 es la población troncal (ancestral en ambos splits)
    # Necesita initially_active=True para poder muestrear de ella en t=0
    dem.add_population(name="p0", initial_size=NE, initially_active=True)
    dem.add_population(name="p1", initial_size=NE)
    dem.add_population(name="p2", initial_size=NE)

    # Migraciones SOLO entre p0 y las que estarán activas
    # p1 y p2 tienen migración con p0 mientras están activas
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p0", dest="p2", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p1", dest="p2", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p1", rate=mig_rate(5.0))

    # Cambios de tamaño (solo p0 y p2, porque p1 será inactiva pronto)
    for p in ("p0", "p2"):
        dem.add_population_parameters_change(
            time=T(0.8), population=p, initial_size=size(15.0)
        )

    # Splits: p1 se vuelve inactiva primero, luego p2
    # NO agregar ningún add_migration_rate_change después de estos
    dem.add_population_split(time=T(0.7), derived=["p1"], ancestral="p0")
    dem.add_population_split(time=T(1.0), derived=["p2"], ancestral="p0")
    
    dem.sort_events()
    reps = msprime.sim_ancestry(
        samples={"p0": 10, "p1": 4, "p2": 1},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)
# ------------------------------------------------------------------
# Caso 1: 2 poblaciones, -eN/-en/-ej
#   ms: 10 100000 ... -I 2 2 8 -eN 0.4 10.01 -eN 1 0.01
#       -en 0.25 2 0.2 -ej 3 2 1
# ------------------------------------------------------------------
def case1():
    nsam, rep, L, rho, theta = 10, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=NE)
    dem.add_population(name="p1", initial_size=NE)

    for p in ("p0", "p1"):
        dem.add_population_parameters_change(time=T(0.4),
                                             population=p,
                                             initial_size=size(10.01))
        dem.add_population_parameters_change(time=T(1.0),
                                             population=p,
                                             initial_size=size(0.01))

    dem.add_population_parameters_change(time=T(0.25),
                                         population="p1",
                                         initial_size=size(0.2))

    dem.add_population_split(time=T(3.0), derived=["p1"], ancestral="p0")
    dem.sort_events()

    reps = msprime.sim_ancestry(
        samples={"p0": 2, "p1": 8},
        demography=dem,
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)

# ------------------------------------------------------------------
# Registro de casos
# ------------------------------------------------------------------
CASES = {
    1: case1, 2: case2, 3: case3,
    4: case4, 5: case5, 6: case6,
}
import numpy as np
import time
def stats(gen, label="", n_max=10):
    tmrcas = []
    for i, ts in enumerate(gen):
        s = ts.samples()
        tmrcas.append(ts.first().tmrca(s[0], s[1]))
    print(f"{label}: T_MRCA media = {np.mean(tmrcas):.4f} (n={len(tmrcas)})")

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
        stats(CASES[c](), label=f"caso {c}")   # ✅ generador
        t1 = time.perf_counter()
        print(f"== FIN caso {c}  |  {time.strftime('%Y-%m-%d %H:%M:%S')}  |  {t1-t0:.2f} s  |  OK")
if __name__ == "__main__":
    main()