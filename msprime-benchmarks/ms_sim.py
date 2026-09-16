#!/usr/bin/env python3
"""
simulacion tipo ms usando msprime, con salida en CSV.

Escalado ms -> msprime (todo en unidades de 4*N0 como en ms):
    tiempo t_ms  -> generaciones = t_ms * 4*N0
    tamano x_ms  -> N            = x_ms * N0
    theta = 4*N0*mu*L -> mu = theta / (4*N0*L)
    rho   = 4*N0*c     -> r  = rho   / (4*N0*(L-1))
    M     = 4*N0*m     -> m  = M / (4*N0)
"""

import argparse
import csv
import msprime


def get_args():
    p = argparse.ArgumentParser(description="Simulacion ms -> msprime (simple)")
    p.add_argument("--nsam", type=int, required=True, help="cromosomas muestreados")
    p.add_argument("--reps", type=int, required=True, help="numero de replicas")
    p.add_argument("--seqlen", type=int, default=1, help="largo del locus")
    p.add_argument("--theta", type=float, default=0.0, help="-t : 4*N0*mu*L")
    p.add_argument("--rho", type=float, default=0.0, help="-r : 4*N0*c")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--N0", type=float, default=10000, help="tamano efectivo de referencia")

    # estructura poblacional simple: -I npop n1 n2 ... [migracion simetrica 4*N0*m]
    p.add_argument("--I", type=float, nargs="+", default=None, metavar="V")

    # eventos demograficos (repetibles)
    p.add_argument("--eN", type=float, nargs=2, action="append", default=[],
                    metavar=("T", "X"), help="-eN t x : todas las poblaciones a tamano x*N0")
    p.add_argument("--en", type=float, nargs=3, action="append", default=[],
                    metavar=("T", "POP", "X"), help="-en t i x : poblacion i a tamano x*N0")
    p.add_argument("--ej", type=float, nargs=3, action="append", default=[],
                    metavar=("T", "SRC", "DST"), help="-ej t i j : linajes de i pasan a j")

    p.add_argument("--out", default="resultados.csv")
    p.add_argument("--label", default="")
    return p.parse_args()


def build_demography(args, npop, N0, scale_t, scale_m, sym_mig):
    dem = msprime.Demography()
    for i in range(npop):
        dem.add_population(name=f"pop{i + 1}", initial_size=N0)

    if sym_mig and npop > 1:
        rate = (sym_mig / (npop - 1)) * scale_m
        for a in range(npop):
            for b in range(npop):
                if a != b:
                    dem.set_migration_rate(f"pop{a + 1}", f"pop{b + 1}", rate)

    eventos = (
        [(t, "eN", (x,)) for t, x in args.eN]
        + [(t, "en", (int(i), x)) for t, i, x in args.en]
        + [(t, "ej", (int(i), int(j))) for t, i, j in args.ej]
    )
    eventos.sort(key=lambda e: e[0])

    for t_ms, kind, payload in eventos:
        t = t_ms * scale_t
        if kind == "eN":
            dem.add_population_parameters_change(time=t, population=None,
                                                   initial_size=payload[0] * N0, growth_rate=0)
        elif kind == "en":
            pop, x = payload
            dem.add_population_parameters_change(time=t, population=f"pop{pop}",
                                                   initial_size=x * N0, growth_rate=0)
        elif kind == "ej":
            src, dst = payload
            dem.add_mass_migration(time=t, source=f"pop{src}", dest=f"pop{dst}", proportion=1.0)

    dem.sort_events()
    return dem


def main():
    args = get_args()
    N0 = args.N0
    scale_t = 4.0 * N0
    scale_m = 1.0 / (4.0 * N0)
    L = args.seqlen

    if args.I:
        npop = int(args.I[0])
        sample_config = [int(v) for v in args.I[1:1 + npop]]
        sym_mig = args.I[1 + npop] if len(args.I) > 1 + npop else None
    else:
        npop = 1
        sample_config = [args.nsam]
        sym_mig = None

    if sum(sample_config) != args.nsam:
        raise SystemExit(f"error: -I suma {sum(sample_config)} muestras pero --nsam es {args.nsam}")

    mu = args.theta / (4.0 * N0 * L) if args.theta else 0.0
    r = args.rho / (4.0 * N0 * (L - 1)) if (args.rho and L > 1) else 0.0

    dem = build_demography(args, npop, N0, scale_t, scale_m, sym_mig)

    samples = [
        msprime.SampleSet(num_samples=n, population=f"pop{i + 1}", ploidy=1)
        for i, n in enumerate(sample_config) if n > 0
    ]

    replicas = msprime.sim_ancestry(
        samples=samples,
        demography=dem,
        sequence_length=L,
        recombination_rate=r,
        discrete_genome=True,
        ploidy=2,
        num_replicates=args.reps,
        random_seed=args.seed,
    )

    with open(args.out, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["caso", "rep", "num_arboles", "S", "pi", "tajimas_d", "tmrca_medio"])

        for rep, ts in enumerate(replicas):
            if mu > 0:
                ts = msprime.sim_mutations(ts, rate=mu, random_seed=args.seed + rep + 1,
                                            discrete_genome=True)

            tmrca_medio = sum(
                (t.time(t.root) if t.num_roots == 1 else 0.0) * t.span for t in ts.trees()
            ) / ts.sequence_length / scale_t

            S = ts.num_sites
            pi = ts.diversity(span_normalise=False) if S else 0.0
            try:
                tajd = ts.Tajimas_D() if S else float("nan")
            except Exception:
                tajd = float("nan")

            writer.writerow([args.label, rep, ts.num_trees, S,
                              f"{pi:.6f}", f"{tajd:.6f}", f"{tmrca_medio:.6f}"])

    print(f"[{args.label or 'caso'}] {args.reps} replicas -> {args.out}")
    print(f"    npop={npop} muestras={sample_config} mu={mu:.3e} r={r:.3e} N0={N0:g}")


if __name__ == "__main__":
    main()