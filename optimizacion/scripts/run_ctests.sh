#!/bin/bash
# Compila y corre los tests C de msprime (lib/tests, CUnit) para una variante.
# Sin NDEBUG: los assert quedan activos. Con ASan y UBSan para detectar errores de memoria.
# Uso: run_ctests.sh <variante>
set -u
V=$1
B=~/msprime-opt/build
D=$B/v_$V
OUT=$B/ctests_$V
GSL=$B/gsl/usr
CUNIT=$B/cunit/usr
LIBDIR=lib/x86_64-linux-gnu
TSK=$D/git-submodules/tskit/c
KAS=$TSK/subprojects/kastore
mkdir -p "$OUT"
CFLAGS="-std=gnu99 -g -O1 -fsanitize=address,undefined -fno-omit-frame-pointer -I$D/lib -I$TSK -I$KAS -I$GSL/include -I$CUNIT/include"
LDFLAGS="-L$GSL/$LIBDIR -L$CUNIT/$LIBDIR -Wl,-rpath,$GSL/$LIBDIR -Wl,-rpath,$CUNIT/$LIBDIR -lgsl -lgslcblas -lcunit -lm"
SRCS=("$D"/lib/{msprime,fenwick,util,mutgen,object_heap,likelihood,rate_map,avl}.c "$TSK"/tskit/*.c "$KAS"/kastore.c)

objs=()
for s in "${SRCS[@]}" "$D/lib/tests/testlib.c"; do
    o="$OUT/$(basename "${s%.c}").o"
    gcc $CFLAGS -c "$s" -o "$o" || { echo "COMPILA MAL: $s"; exit 2; }
    objs+=("$o")
done

cd "$D/lib"
status=0
for t in core ancestry pedigrees mutations likelihood fenwick rate_map sweeps; do
    gcc $CFLAGS "tests/test_$t.c" "${objs[@]}" -o "$OUT/test_$t" $LDFLAGS || { echo "COMPILA MAL: test_$t"; status=2; continue; }
    ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 "$OUT/test_$t" > "$OUT/test_$t.log" 2>&1
    rc=$?
    printf "%-10s rc=%d  %s\n" "$t" "$rc" "$(grep -E '^ +asserts' "$OUT/test_$t.log" | tr -s ' ')"
    grep -E "^ +tests " "$OUT/test_$t.log" | tr -s ' '
    grep -cE "runtime error|AddressSanitizer" "$OUT/test_$t.log" | sed 's/^/  sanitizer: /'
    [ $rc -ne 0 ] && status=1
done
echo "FIN $V status=$status"
exit $status
