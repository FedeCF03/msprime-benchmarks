#!/usr/bin/env python3
"""
Simulacion en msprime equivalente a un comando ms, con parametros por terminal
y salida en CSV.

Ejemplo (equivale al params_case.01):

    python ms_sim.py \
        --nsam 10 --reps 100000 --seqlen 100000 --theta 10 --rho 10 \
        --seeds 40328 19150 54118 \
        --I 2 2 8 \
        --en 0.25 2 0.2 --eN 0.4 10.01 --eN 1 0.01 --ej 3 2 1 \
        -T -L --out results/case01.csv

Escalado ms -> msprime
----------------------
ms expresa todo en unidades de 4*N0:
    tiempo    t_ms       -> generaciones = t_ms * 4 * N0
    tamano    x_ms       -> N            = x_ms * N0
    theta = 4*N0*mu*L    -> mu = theta / (4*N0*L)
    rho   = 4*N0*c       -> r  = rho   / (4*N0*(L-1))
    M     = 4*N0*m       -> m  = M / (4*N0)

N0 es arbitrario (--N0, default 10000): reescala tiempos y tasas de forma
compensada, asi que las genealogias no cambian.
"""

import argparse
import csv
import math
import os

import msprime


# ---------------------------------------------------------------------------
# Parametros por terminal
# ---------------------------------------------------------------------------

def get_args():
    p = argparse.ArgumentParser(description="Simulacion ms -> msprime")

    # parametros basicos (los que estaban en params_case.NN)
    p.add_argument("--nsam", type=int, required=True,
                   help="numero de cromosomas muestreados")
    p.add_argument("--reps", type=int, required=True,
                   help="numero de replicas")
    p.add_argument("--seqlen", type=int, default=1,
                   help="largo del locus en sitios")
    p.add_argument("--theta", type=float, default=0.0,
                   help="-t : 4*N0*mu*L")
    p.add_argument("--rho", type=float, default=0.0,
                   help="-r : 4*N0*c entre los extremos del locus")
    p.add_argument("--seeds", type=int, nargs=3, default=[42, 0, 0],
                   help="3 semillas estilo ms (msprime usa solo la primera)")
    p.add_argument("--N0", type=float, default=10000,
                   help="tamano efectivo de referencia")

    # estructura poblacional
    p.add_argument("--I", type=float, nargs="+", default=None,
                   metavar="V",
                   help="-I npop n1 n2 ... [4*N0*m simetrica]")
    p.add_argument("--ma", type=str, nargs="+", default=None, metavar="V",
                   help="-ma : matriz de migracion npop*npop, 'x' en la diagonal")

    # eventos demograficos (repetibles)
    p.add_argument("--eN", type=float, nargs=2, action="append", default=[],
                   metavar=("T", "X"),
                   help="-eN t x : todas las poblaciones pasan a tamano x*N0")
    p.add_argument("--en", type=float, nargs=3, action="append", default=[],
                   metavar=("T", "POP", "X"),
                   help="-en t i x : la poblacion i pasa a tamano x*N0")
    p.add_argument("--ej", type=float, nargs=3, action="append", default=[],
                   metavar=("T", "SRC", "DST"),
                   help="-ej t i j : los linajes de i pasan a j")

    # salida
    p.add_argument("-T", dest="print_trees", action="store_true",
                   help="incluir los arboles en newick (una fila por arbol)")
    p.add_argument("-L", dest="print_lengths", action="store_true",
                   help="incluir TMRCA y largo total de ramas")
    p.add_argument("--out", default="resultados.csv",
                   help="archivo CSV de salida")
    p.add_argument("--label", default="",
                   help="etiqueta del caso, se agrega como columna")

    return p.parse_args()


# ---------------------------------------------------------------------------
# Construccion del modelo
# ---------------------------------------------------------------------------

def main():
    args = get_args()
    N0 = args.N0
    scale_t = 4.0 * N0          # tiempo ms -> generaciones
    scale_m = 1.0 / (4.0 * N0)  # M = 4*N0*m -> m por generacion

    # --- estructura poblacional (-I) ---------------------------------------
    if args.I:
        npop = int(args.I[0])
        sample_config = [int(v) for v in args.I[1:1 + npop]]
        # 4to valor opcional: tasa de migracion simetrica 4*N0*m
        sym_mig = args.I[1 + npop] if len(args.I) > 1 + npop else None
    else:
        npop = 1
        sample_config = [args.nsam]
        sym_mig = None

    if sum(sample_config) != args.nsam:
        raise SystemExit(
            f"error: las muestras de -I suman {sum(sample_config)} "
            f"pero --nsam es {args.nsam}")

    # --- tasas por sitio y por generacion ----------------------------------
    L = args.seqlen
    mu = args.theta / (4.0 * N0 * L) if args.theta else 0.0
    r = args.rho / (4.0 * N0 * (L - 1)) if (args.rho and L > 1) else 0.0

    # --- poblaciones --------------------------------------------------------
    dem = msprime.Demography()
    for i in range(npop):
        dem.add_population(name=f"pop{i + 1}", initial_size=N0)

    # --- migracion inicial --------------------------------------------------
    # ms: M[i][j] = fraccion de la subpoblacion i formada por migrantes de j
    # hacia adelante en el tiempo; hacia atras, los linajes van de i a j.
    # msprime: set_migration_rate(source=i, dest=j) mueve linajes i->j hacia
    # atras. Los indices se corresponden directamente.
    if sym_mig and npop > 1:
        off = sym_mig / (npop - 1)
        for a in range(npop):
            for b in range(npop):
                if a != b:
                    dem.set_migration_rate(f"pop{a + 1}", f"pop{b + 1}",
                                           off * scale_m)

    if args.ma:
        entries = args.ma[:npop * npop]
        for idx, tok in enumerate(entries):
            a, b = divmod(idx, npop)
            if a == b or tok.lower() == "x":
                continue
            dem.set_migration_rate(f"pop{a + 1}", f"pop{b + 1}",
                                   float(tok) * scale_m)

    # --- eventos demograficos ----------------------------------------------
    # Se juntan todos y se ordenan por tiempo: ms ordena internamente, asi que
    # el orden en la linea de comandos no importa.
    eventos = []
    for t, x in args.eN:
        eventos.append((t, "eN", (x,)))
    for t, pop, x in args.en:
        eventos.append((t, "en", (int(pop), x)))
    for t, src, dst in args.ej:
        eventos.append((t, "ej", (int(src), int(dst))))
    eventos.sort(key=lambda e: e[0])

    for t_ms, kind, payload in eventos:
        t = t_ms * scale_t

        if kind == "eN":
            # -eN t x : afecta a TODAS las poblaciones y anula el crecimiento
            (x,) = payload
            dem.add_population_parameters_change(
                time=t, population=None, initial_size=x * N0, growth_rate=0)

        elif kind == "en":
            # -en t i x : afecta solo a la poblacion i
            pop, x = payload
            dem.add_population_parameters_change(
                time=t, population=f"pop{pop}", initial_size=x * N0,
                growth_rate=0)

        elif kind == "ej":
            # -ej t i j : todos los linajes de i pasan a j.
            # Se usa mass migration y no add_population_split porque en ms la
            # poblacion destino ya existe y sigue existiendo despues: es una
            # fusion hacia una poblacion contemporanea, no un split.
            src, dst = payload
            dem.add_mass_migration(
                time=t, source=f"pop{src}", dest=f"pop{dst}", proportion=1.0)
            # ms ademas pone en cero la migracion desde y hacia la poblacion i
            for other in range(1, npop + 1):
                if other != src:
                    dem.add_migration_rate_change(
                        time=t, source=f"pop{src}", dest=f"pop{other}", rate=0)
                    dem.add_migration_rate_change(
                        time=t, source=f"pop{other}", dest=f"pop{src}", rate=0)

    dem.sort_events()

    # --- muestras -----------------------------------------------------------
    # ploidy=1 en el SampleSet => nsam cuenta cromosomas, como en ms.
    # ploidy=2 en el modelo => E[T2] = 2*N0 generaciones = 0.5 en unidades de
    # 4*N0, que es el escalado que asume ms.
    samples = [
        msprime.SampleSet(num_samples=n, population=f"pop{i + 1}", ploidy=1)
        for i, n in enumerate(sample_config) if n > 0
    ]

    # ---------------------------------------------------------------------
    # Simulacion
    # ---------------------------------------------------------------------
    semilla = args.seeds[0]

    replicas = msprime.sim_ancestry(
        samples=samples,
        demography=dem,
        sequence_length=L,
        recombination_rate=r,
        discrete_genome=True,
        ploidy=2,
        num_replicates=args.reps,
        random_seed=semilla,
    )

    # ---------------------------------------------------------------------
    # Salida CSV
    # ---------------------------------------------------------------------
    outdir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(outdir, exist_ok=True)

    # Con -T se escribe una fila por arbol local; sin -T, una fila por replica.
    if args.print_trees:
        campos = ["caso", "rep", "arbol", "inicio", "fin", "span",
                  "tmrca", "largo_ramas", "newick"]
    else:
        campos = ["caso", "rep", "num_arboles", "S", "pi", "tajimas_d",
                  "tmrca_medio", "tmrca_max", "largo_ramas_medio"]

    with open(args.out, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(campos)

        for rep, ts in enumerate(replicas):
            # mutaciones (-t)
            if mu > 0:
                ts = msprime.sim_mutations(
                    ts, rate=mu, random_seed=semilla + rep + 1,
                    discrete_genome=True)

            if args.print_trees:
                # una fila por arbol local, imitando el -T de ms
                for k, tree in enumerate(ts.trees()):
                    tmrca = (tree.time(tree.root) / scale_t
                             if tree.num_roots == 1 else math.nan)
                    blen = tree.total_branch_length / scale_t
                    writer.writerow([
                        args.label, rep, k,
                        int(tree.interval.left), int(tree.interval.right),
                        int(tree.span),
                        f"{tmrca:.6f}" if args.print_lengths else "",
                        f"{blen:.6f}" if args.print_lengths else "",
                        tree.newick(),
                    ])
            else:
                # resumen por replica: TMRCA y largo de rama promediados por el
                # span de cada arbol local
                suma_tmrca = 0.0
                suma_blen = 0.0
                tmrca_max = 0.0
                span_total = 0.0
                for tree in ts.trees():
                    span = tree.span
                    span_total += span
                    tmrca = (tree.time(tree.root)
                             if tree.num_roots == 1 else math.nan)
                    suma_tmrca += tmrca * span
                    suma_blen += tree.total_branch_length * span
                    tmrca_max = max(tmrca_max, tmrca)

                S = ts.num_sites
                pi = ts.diversity(span_normalise=False) if S else 0.0
                try:
                    tajd = ts.Tajimas_D() if S else math.nan
                except Exception:
                    tajd = math.nan

                writer.writerow([
                    args.label, rep, ts.num_trees, S,
                    f"{pi:.6f}", f"{tajd:.6f}",
                    f"{suma_tmrca / span_total / scale_t:.6f}",
                    f"{tmrca_max / scale_t:.6f}",
                    f"{suma_blen / span_total / scale_t:.6f}",
                ])

    print(f"[{args.label or 'caso'}] {args.reps} replicas -> {args.out}")
    print(f"    npop={npop} muestras={sample_config} "
          f"mu={mu:.3e} r={r:.3e} N0={N0:g}")


if __name__ == "__main__":
    main()
