#!/bin/zsh
# Rebuild the whole DMR chain in one analysis root:
#   dmr_etl -> notebook 01 -> notebook 02 -> derive_additional -> derive_sender -> build_data
# Usage: tools/run_pipeline.sh [ROOT]   (default: the folder above tools/)
#        PY=/path/to/python tools/run_pipeline.sh ROOT   (default PY: ROOT/.venv/bin/python)
set -euo pipefail
ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
ROOT="$(cd "$ROOT" && pwd)"
PY="${PY:-$ROOT/.venv/bin/python}"
export PYTHONDONTWRITEBYTECODE=1
export MPLBACKEND=Agg
# use the kernel of $PY itself, not a "python3" kernelspec in ~/Library/Jupyter
export JUPYTER_DATA_DIR="$ROOT/.jupyter-data"
export JUPYTER_PATH=""

cd "$ROOT"
echo "== python: $("$PY" -c 'import sys,platform; print(sys.version.split()[0], platform.machine(), sys.executable)')"
echo "== dmr_etl"; "$PY" -B -m src.dmr_etl
cd "$ROOT/notebooks"
# executed copies go to outputs/notebooks/ (git-ignored); the committed notebooks stay without outputs
mkdir -p "$ROOT/outputs/notebooks"
for nb in 01_combine_data.ipynb 02_analysis_effectiveness.ipynb; do
  echo "== $nb"
  "$PY" -B -m nbconvert --to notebook --execute --output-dir "$ROOT/outputs/notebooks" \
      --ExecutePreprocessor.kernel_name=python3 \
      --ExecutePreprocessor.timeout=1800 "$nb"
done
echo "== derive_additional_tables"; "$PY" -B "$ROOT/tools/derive_additional_tables.py" --analysis-root "$ROOT"
echo "== derive_sender_tables";     "$PY" -B "$ROOT/tools/derive_sender_tables.py" --analysis-root "$ROOT"
echo "== build_data";               "$PY" -B "$ROOT/tools/build_data.py" --analysis-root "$ROOT"
echo "== done"
