#!/usr/bin/env python3
"""Compila variantes de msprime 1.4.4 fuera del repo (retoma si se corta).

Todas usan los flags del wheel de PyPI (-O3 -DNDEBUG -fno-strict-overflow -fPIC,
sin -Bsymbolic-functions), para que "base" sea comparable con lo que se instala
normalmente. Cada variante queda en build/v_<nombre>; se usa con PYTHONPATH.
"""
import glob
import os
import re
import shutil
import subprocess

ROOT = os.path.expanduser("~/msprime-opt")
B = f"{ROOT}/build"
SRC = f"{B}/sdist/msprime-1.4.4"
GSL = f"{B}/gsl/usr"
LIB = f"{GSL}/lib/x86_64-linux-gnu"
PY = f"{B}/venv/bin/python"
PIP = f"{B}/venv/bin/pip"
REPO = os.path.expanduser("~/msprime-benchmarks")
FLAGS = "-DNDEBUG -g -O3 -fno-strict-overflow -Wall"
NOSI = "-fno-semantic-interposition"


def sh(*cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


def prepare():
    os.makedirs(f"{B}/debs", exist_ok=True)
    os.makedirs(f"{B}/gsl", exist_ok=True)
    os.makedirs(f"{B}/sdist", exist_ok=True)
    if not os.path.exists(f"{GSL}/include/gsl/gsl_rng.h"):
        sh("apt-get", "download", "libgsl-dev", "libgsl28", "libgslcblas0", cwd=f"{B}/debs")
        for deb in glob.glob(f"{B}/debs/*.deb"):
            sh("dpkg", "-x", deb, f"{B}/gsl")
    if not os.path.exists(PY):
        sh("python3.13", "-m", "venv", f"{B}/venv")
        sh(PIP, "install", "-q", "numpy==2.5.4", "tskit==1.0.3", "demes==0.2.3",
           "newick==1.11.0", "setuptools", "setuptools_scm", "wheel")
    if not os.path.isdir(SRC):
        sh(PIP, "download", "-q", "--no-deps", "--no-binary", "msprime",
           "msprime==1.4.4", "-d", f"{B}/sdist")
        sh("tar", "xzf", f"{B}/sdist/msprime-1.4.4.tar.gz", "-C", f"{B}/sdist")


def sub_once(path, old, new):
    s = open(path).read()
    assert s.count(old) == 1, f"{path}: no encontré una única vez:\n{old}"
    open(path, "w").write(s.replace(old, new))


# ---------------------------------------------------------------- parches
def patch_if(d):
    """Saltear las posiciones en 0 antes de llamar a fenwick_increment."""
    sub_once(f"{d}/lib/fenwick.c",
             "        value = self->values[j];\n"
             "        self->values[j] = 0;\n"
             "        fenwick_increment(self, j, value);",
             "        value = self->values[j];\n"
             "        if (value != 0) {\n"
             "            self->values[j] = 0;\n"
             "            fenwick_increment(self, j, value);\n"
             "        }")


def patch_block4k(d):
    """Bloques de 4K en vez de 64K: achica el árbol de Fenwick que se crea en cada réplica."""
    sub_once(f"{d}/msprime/ancestry.py",
             "        block_size = 64 * 1024\n",
             "        block_size = 4 * 1024\n")


def patch_force(d):
    """Inlining forzado: copia always_inline de fenwick_increment para rebuild."""
    p = f"{d}/lib/fenwick.c"
    s = open(p).read()
    total = re.search(r"static void\nfenwick_increment_total\(.*?\n}\n", s, re.S).group(0)
    inc = re.search(r"void\nfenwick_increment\(fenwick_t \*self.*?\n}\n", s, re.S).group(0)
    attr = "static inline __attribute__((always_inline)) void\n"
    copy = (total.replace("static void\nfenwick_increment_total", attr + "fenwick_total_inl")
            + "\n"
            + inc.replace("void\nfenwick_increment", attr + "fenwick_increment_inl")
                 .replace("fenwick_increment_total", "fenwick_total_inl"))
    marker = "/* Rebuild the Fenwick tree index"
    assert s.count(marker) == 1
    s = s.replace(marker, copy + "\n" + marker)
    old = "        fenwick_increment(self, j, value);"
    assert s.count(old) == 1
    open(p, "w").write(s.replace(old, "        fenwick_increment_inl(self, j, value);"))


def compile_ext(d, name, cflags="", ldflags="", ldshared="gcc -shared", force=False):
    env = dict(os.environ,
               CFLAGS=f"{FLAGS} -I{GSL}/include {cflags}",
               LDFLAGS=f"-L{LIB} -Wl,-rpath,{LIB} {ldflags}",
               LDSHARED=ldshared)
    cmd = [PY, "setup.py", "build_ext", "--inplace"] + (["--force"] if force else [])
    with open(f"{B}/build_{name}.log", "a") as log:
        subprocess.run(cmd, cwd=d, env=env, stdout=log, stderr=log, check=True)


def done_marker(d):
    return f"{d}/.ok"


def variant(name, patches=(), cflags="", ldflags="", compile_c=True):
    d = f"{B}/v_{name}"
    if os.path.exists(done_marker(d)):
        return
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC if compile_c else f"{B}/v_base", d,
                    ignore=shutil.ignore_patterns("__pycache__", ".ok"))
    for p in patches:
        p(d)
    if compile_c:
        compile_ext(d, name, cflags, ldflags)
    open(done_marker(d), "w").close()
    print("ok", name, flush=True)


def wheel():
    d = f"{B}/v_wheel"
    if os.path.exists(done_marker(d)):
        return
    shutil.rmtree(d, ignore_errors=True)
    sh(PIP, "install", "-q", "--no-deps", "--target", d, "msprime==1.4.4")
    open(done_marker(d), "w").close()
    print("ok wheel", flush=True)


TRAIN = """
import itertools, sys
sys.path.insert(0, ".")
import ms_sim
for case, n in ((2, 1000), (5, 5000)):
    for ts in itertools.islice(ms_sim.CASES[case](), n):
        s = ts.samples(); ts.first().tmrca(s[0], s[1]); ts.num_trees
"""


def pgo():
    """PGO: se entrena con los casos 2 y 5, y se mide en los casos 1 y 6."""
    d = f"{B}/v_pgo"
    if os.path.exists(done_marker(d)):
        return
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, d, ignore=shutil.ignore_patterns("__pycache__", ".ok"))
    compile_ext(d, "pgo", "-fprofile-generate -fprofile-update=single", "-fprofile-generate")
    sh(PY, "-c", TRAIN, cwd=REPO,
       env=dict(os.environ, PYTHONPATH=d, OPENBLAS_NUM_THREADS="1",
                PYTHONDONTWRITEBYTECODE="1"))
    compile_ext(d, "pgo", "-fprofile-use -fprofile-correction -Wno-missing-profile", "",
                force=True)
    open(done_marker(d), "w").close()
    print("ok pgo", flush=True)


def main():
    prepare()
    wheel()
    variant("base")
    variant("inline", cflags=NOSI)
    variant("symbolic", ldflags="-Wl,-Bsymbolic-functions")
    variant("lto", cflags=f"-flto {NOSI}", ldflags="-flto -O3")
    variant("if", [patch_if])
    variant("force", [patch_force])
    variant("native", cflags="-march=native")
    variant("block4k", [patch_block4k], compile_c=False)
    variant("block4k_if", [patch_if, patch_block4k])
    pgo()
    print("listo", flush=True)


if __name__ == "__main__":
    main()
