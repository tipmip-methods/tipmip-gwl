#!/bin/bash
#SBATCH --account=bm1448
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --job-name=preprocess_gmstmon
#SBATCH --output=/work/bm1448/analysis/harteg/preprocess_gmstmon_%j.log

# Build gmstmon files on Levante from the bundled tas_chunks.tsv manifest.
# Set TIPMIP_GWL to your clone, e.g. /work/bm1448/analysis/harteg/tipmip-gwl

set -euo pipefail
TIPMIP_GWL="${TIPMIP_GWL:-/work/bm1448/analysis/harteg/tipmip-gwl}"
OUT_BASE="${OUT_BASE:-/work/bm1448/analysis/harteg/merged/tas}"
MANIFEST="${MANIFEST:-${TIPMIP_GWL}/src/tipmip_gwl/data/tas_chunks.tsv}"

module load cdo 2>/dev/null || true

for exp in esm-up2p0 esm-piControl; do
  echo "############ ${exp} ############"
  tipmip-gwl-preprocess \
    --manifest "${MANIFEST}" \
    --exp "${exp}" \
    --outdir "${OUT_BASE}/${exp}/gmstmon" \
    --backend auto
done

echo "Done. Output:"
find "${OUT_BASE}" -path '*/gmstmon/*.nc' -exec ls -lh {} +
