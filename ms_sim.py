#!/usr/bin/env python3
"""
https://raw.githubusercontent.com/tskit-dev/msprime/0.2.0/docs/api.rst#1
Ejecuta en msprime los 6 casos traducidos desde ms.

Uso:
    python run_cases.py                  # corre todos
    python run_cases.py 1 3 5            # solo los casos 1, 3 y 5
    python run_cases.py 2 --stats        # caso 2 + resumen por réplica

Convenciones (ver comentarios abajo para detalles):
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
def mu_rate(theta, L):   # theta = 4N*mu*L  ->  mu por base/gen
    return theta / (SCALE * L)
def re_rate(rho, L):     # rho   = 4N*r*L   ->  r  por base/gen
    return rho / (SCALE * L)
def mig_rate(M):         # M = 4N*m        ->  m  por generación
    return M / SCALE
def size(N_ms):          # tamaño en unidades de N  ->  individuos
    return N_ms * NE

SEED1, SEED2 = 40328, 19150

def mutate(reps, theta, seqlen): ## para hacer n mutaciones y no sobrecargar la ram genera arboles 1 por vez 
    return msprime.sim_mutations(reps, rate=mu_rate(theta, seqlen),
                                 random_seed=SEED2)

# ------------------------------------------------------------------
# Caso 6: modelo básico, sin estructura
#   ms: 20 50 -seeds 40328 19150 54118 -t 1000 -r 2000 100000
# ------------------------------------------------------------------
def case6():
    nsam, rep, L, rho, theta = 20, 50, 100_000, 2000, 1000
    reps = msprime.sim_ancestry(
        samples=nsam, ##  total de cromosomas muestreados ( el numero total de copias de un cromosoma o locus específico que se extraen de la población para un estudio)
        sequence_length=L,
        recombination_rate=re_rate(rho, L),
        random_seed=SEED1,
        num_replicates=rep,
    )
    return mutate(reps, theta, L)

# ------------------------------------------------------------------
# Caso 5: 2 poblaciones, migración asimétrica  (-ma)
#   ms: 4 100000 ... -I 2 2 2 -ma x 10 5 x
# ------------------------------------------------------------------
def case5():
    nsam, rep, L, rho, theta = 4, 100_000, 100_000, 10, 10
    dem = msprime.Demography()
    dem.add_population(name="p0", initial_size=NE)
    dem.add_population(name="p1", initial_size=NE)
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(10.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(5.0))

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
    for p in ("p0", "p1", "p2"):
        dem.add_population(name=p, initial_size=NE)

    # matriz 3x3:
    #      p0  p1  p2
    # p0 [  x   1   2 ]
    # p1 [  3   x   4 ]
    # p2 [  5   6   x ]
    dem.set_migration_rate(source="p0", dest="p1", rate=mig_rate(1.0))
    dem.set_migration_rate(source="p0", dest="p2", rate=mig_rate(2.0))
    dem.set_migration_rate(source="p1", dest="p0", rate=mig_rate(3.0))
    dem.set_migration_rate(source="p1", dest="p2", rate=mig_rate(4.0))
    dem.set_migration_rate(source="p2", dest="p0", rate=mig_rate(5.0))
    dem.set_migration_rate(source="p2", dest="p1", rate=mig_rate(6.0))

    # -eN 1 .1  y  -eN 3 10  (aplican a TODAS las poblaciones)
    for p in ("p0", "p1", "p2"):
        dem.add_population_parameters_change(time=T(1.0),
                                             population=p,
                                             initial_size=size(0.1))
        dem.add_population_parameters_change(time=T(3.0),
                                             population=p,
                                             initial_size=size(10.0))

    # -ej .7 2 1  =>  p1 se fusiona en p0 a t=0.7
    # -ej 4  3 1  =>  p2 se fusiona en p0 a t=4
    dem.add_population_split(time=T(0.7), derived=["p1"], ancestral="p0")
    dem.add_population_split(time=T(4.0), derived=["p2"], ancestral="p0")

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
# Caso 2: 3 poblaciones, migración simétrica, -eN, -ej (rep reducido)
#   ms: 15 20000 ... -I 3 10 4 1 -ma x 5 5 5 x 5 5 5 x
#       -eN 0.8 15 -ej .7 2 1 -ej 1 3 1
# ------------------------------------------------------------------
def case2():
    nsam, rep, L, rho, theta = 15, 20_000, 100_000, 10, 10
    dem = msprime.Demography()
    for p in ("p0", "p1", "p2"):
        dem.add_population(name=p, initial_size=NE)

    for src in ("p0", "p1", "p2"):
        for dst in ("p0", "p1", "p2"):
            if src != dst:
                dem.set_migration_rate(source=src, dest=dst, rate=mig_rate(5.0))

    # -eN 0.8 15 (todas)
    for p in ("p0", "p1", "p2"):
        dem.add_population_parameters_change(time=T(0.8),
                                             population=p,
                                             initial_size=size(15.0))

    dem.add_population_split(time=T(0.7), derived=["p1"], ancestral="p0")
    dem.add_population_split(time=T(1.0), derived=["p2"], ancestral="p0")

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

    # -eN 0.4 10.01 y -eN 1 0.01  (a TODAS)
    for p in ("p0", "p1"):
        dem.add_population_parameters_change(time=T(0.4),
                                             population=p,
                                             initial_size=size(10.01))
        dem.add_population_parameters_change(time=T(1.0),
                                             population=p,
                                             initial_size=size(0.01))

    # -en 0.25 2 0.2  =>  tamaño de la pop 2 (ms) = p1
    dem.add_population_parameters_change(time=T(0.25),
                                         population="p1",
                                         initial_size=size(0.2))

    # -ej 3 2 1  =>  pop2 (ms)=p1 se fusiona en pop1(ms)=p0
    dem.add_population_split(time=T(3.0), derived=["p1"], ancestral="p0")

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

# ------------------------------------------------------------------
# Runner
# ------------------------------------------------------------------
def summarize(name, reps, stats=True):
    """Cuenta réplicas y, opcionalmente, muestra estadísticos básicos."""
    n = 0
    tmrcas = []
    for ts in reps:
        n += 1
        if stats:
            tmrcas.append(ts.first().tmrca(0, ts.num_samples - 1))
    if stats and tmrcas:
        import statistics
        print(f"  [{name}] réplicas: {n}  "
              f"T_MRCA media: {statistics.mean(tmrcas):.3f}  "
              f"min: {min(tmrcas):.3f}  max: {max(tmrcas):.3f}")
    else:
        print(f"  [{name}] réplicas: {n}")

def main():
    ap = argparse.ArgumentParser(description="Corre casos ms->msprime")
    ap.add_argument("cases", nargs="*", type=int,
                    help="números de caso (1-6). Sin args = todos.")
    ap.add_argument("--stats", action="store_true",
                    help="muestra T_MRCA media en vez de solo contar")
    args = ap.parse_args()

    selected = args.cases or sorted(CASES.keys())
    for c in selected:
        if c not in CASES:
            print(f"!! Caso {c} no existe", file=sys.stderr)
            continue
        print(f"== Caso {c} ==")
        reps = CASES[c]()
        summarize(f"caso{c}", reps, stats=args.stats)
        print()

if __name__ == "__main__":
    main()