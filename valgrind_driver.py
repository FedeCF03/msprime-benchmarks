#!/usr/bin/env python3
"""
valgrind_driver.py - corre UN caso de ms_sim.py con pocas réplicas.

Los casos de ms_sim.py usan entre 20.000 y 100.000 réplicas, pensadas para
mediciones con perf. Valgrind es ~20-50x más lento, así que este driver
recorta `num_replicates` (sin tocar ms_sim.py) para que el caso entre en
segundos. El resto de la simulación (muestras, demografía, rho, semilla) queda
igual: los caminos de código que se perfilan son los mismos.

Además, con --toggle apaga la instrumentación de Callgrind durante el arranque
de Python y los imports, y la prende sólo alrededor del bucle de simulación.
Eso evita que `import numpy`/`import msprime` ensucien el perfil y acelera
mucho la corrida. Se controla con `callgrind_control` (viene con Valgrind).

Uso (normalmente lo invoca profile_valgrind.sh, no hace falta a mano):
    python valgrind_driver.py 1 --reps 100 --toggle
    python valgrind_driver.py 6 --reps 3

Salida: la de ms_sim.py, más una línea de resumen por stderr.
"""

import argparse
import os
import subprocess
import sys
import time

DEFAULT_REPS = 100


def callgrind_instr(action, pid):
    """Prende/apaga la instrumentación de Callgrind en este proceso.

    Devuelve True si pudo. Si no estamos bajo Callgrind (o falta
    callgrind_control), devuelve False y main() aborta con código 3 para que
    profile_valgrind.sh reintente instrumentando todo el proceso.
    """
    try:
        r = subprocess.run(
            ["callgrind_control", f"--instr={action}", str(pid)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return False
    # callgrind_control devuelve rc=0 incluso cuando no encuentra el proceso;
    # la señal de éxito es el "OK." de stdout.
    if r.returncode != 0 or "OK." not in r.stdout:
        detail = (r.stdout + r.stderr).strip().replace("\n", " ")
        print(f"[valgrind_driver] aviso: callgrind_control --instr={action} "
              f"falló: {detail}", file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Corre un caso de ms_sim.py "
                                             "con pocas réplicas (para valgrind)")
    ap.add_argument("case", type=int, help="número de caso (1-6)")
    ap.add_argument("--reps", type=int, default=None,
                    help=f"máximo de réplicas por caso (defecto: {DEFAULT_REPS})")
    ap.add_argument("--stats", action="store_true",
                    help="también calcula T_MRCA y nº de árboles (por defecto no)")
    ap.add_argument("--toggle", action="store_true",
                    help="prender Callgrind sólo durante la simulación")
    args = ap.parse_args()

    reps = args.reps
    if reps is None:
        reps = int(os.environ.get("VALGRIND_REPS", DEFAULT_REPS))
    if reps < 1:
        ap.error("--reps debe ser >= 1")

    repo = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, repo)

    # Imports fuera de la zona instrumentada.
    import msprime          # noqa: F401  (se usa vía monkeypatch)
    import ms_sim

    if args.case not in ms_sim.CASES:
        ap.error(f"caso {args.case} inexistente (válidos: "
                 f"{sorted(ms_sim.CASES)})")

    # Recortar num_replicates sin editar ms_sim.py.
    sim_ancestry = msprime.sim_ancestry

    def sim_ancestry_capped(*a, **kw):
        n = kw.get("num_replicates")
        if n is not None:
            kw["num_replicates"] = min(int(n), reps)
        return sim_ancestry(*a, **kw)

    msprime.sim_ancestry = sim_ancestry_capped

    pid = os.getpid()
    active = False
    if args.toggle:
        active = callgrind_instr("on", pid)
        if not active:
            print("[valgrind_driver] no se pudo activar Callgrind; se aborta "
                  "para reintentar sin toggle", file=sys.stderr)
            sys.exit(3)

    def counted(it):
        nonlocal n
        for ts in it:
            n += 1
            yield ts

    t0 = time.perf_counter()
    n = 0
    gen = counted(ms_sim.CASES[args.case]())
    if args.stats:
        ms_sim.stats(gen, label=f"caso {args.case}")
    else:
        for _ in gen:
            pass
    t1 = time.perf_counter()

    if active:
        callgrind_instr("off", pid)

    print(f"[valgrind_driver] caso {args.case}: reps={reps} "
          f"simuladas={n} ({'con' if args.stats else 'sin'} stats) "
          f"tiempo={t1 - t0:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
