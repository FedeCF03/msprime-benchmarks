#!/usr/bin/env python3
"""
Simulacion tipo ms usando msprime (sin salida a disco ni terminal).

Escalado ms -> msprime (todo en unidades de 4*N0 como en ms):
    tiempo t_ms  -> generaciones = t_ms * 4*N0
    tamano x_ms  -> N            = x_ms * N0
    theta = 4*N0*mu*L -> mu = theta / (4*N0*L)
    rho   = 4*N0*c     -> r  = rho   / (4*N0*(L-1))
    M     = 4*N0*m     -> m  = M / (4*N0)
"""

import argparse
import msprime


def get_args():
    p = argparse.ArgumentParser(description="Simulacion ms -> msprime")
    p.add_argument("--nsam", type=int, required=True, help="cromosomas muestreados")
    p.add_argument("--reps", type=int, required=True, help="numero de replicas")
    p.add_argument("--seqlen", type=int, default=1, help="largo del locus")
    p.add_argument("--theta", type=float, default=0.0, help="-t : 4*N0*mu*L")
    p.add_argument("--rho", type=float, default=0.0, help="-r : 4*N0*c")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--N0", type=float, default=10000, help="tamano efectivo de referencia")

    # estructura poblacional simple: -I npop n1 n2 ... [migracion simetrica 4*N0*m]
    p.add_argument("--I", type=float, nargs="+", default=None, metavar="V")

    return p.parse_args()

# modelo y construye el objeto Demography que modela historia genealogica
def build_demography(args, npop, N0):
    dem = msprime.Demography() ##
    for i in range(npop): 
        dem.add_population(name=f"pop{i + 1}", initial_size=N0)
    return dem


def main():
    args = get_args()
    N0 = args.N0
    L = args.seqlen

    if args.I:
        npop = int(args.I[0])
        sample_config = [int(v) for v in args.I[1:1 + npop]]
    else:
        npop = 1
        sample_config = [args.nsam]
    if sum(sample_config) != args.nsam:
        raise SystemExit(f"error: -I suma {sum(sample_config)} muestras pero --nsam es {args.nsam}")

    mu = args.theta / (4.0 * N0 * L) if args.theta else 0.0
    r = args.rho / (4.0 * N0 * (L - 1)) if (args.rho and L > 1) else 0.0

    dem = build_demography(args, npop, N0)

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

    for rep, ts in enumerate(replicas):
        if mu > 0:
            ts = msprime.sim_mutations(ts, rate=mu, random_seed=args.seed + rep + 1,
                                       discrete_genome=True)


if __name__ == "__main__":
    main()