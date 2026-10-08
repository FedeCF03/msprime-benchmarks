#!/usr/bin/env bash
#
# Si no le pasas casos, por defecto perfila del 1 al 6.

set -e

# Casos a perfilar (si no pasas argumentos, usa del 1 al 6)
CASES=("$@")
[[ ${#CASES[@]} -eq 0 ]] && CASES=(1 2 3 4 5 6)

# Crear directorio de logs si no existe
mkdir -p logs/cprofile

for c in "${CASES[@]}"; do
    prof="logs/cprofile/case${c}.prof"
    txt="logs/cprofile/case${c}.log"

    echo "==> Perfilando caso ${c}..."

    # 1. Ejecutar cProfile y guardar el archivo binario
    python3 -m cProfile -o "${prof}" ms_sim.py "${c}"

    # 2. Generar el resumen en texto ordenado por tiempo acumulado (cumtime)
    python3 -c "
import pstats
p = pstats.Stats('${prof}')
p.sort_stats('cumtime')
with open('${txt}', 'w') as f:
    f.write('=== CPROFILE CASO ${c} ===\n')
    p.stream = f
    p.print_stats(30)
"
    echo "OK -> ${txt}"
done

echo "¡Listo! Archivos guardados en logs/cprofile/"
