#!/bin/bash
# Pull merged gmstmon tas files from Levante to a local tipmip tree.
#
# Usage:
#   export TIPMIP_EXP=esm-up2p0-gwl2p0-50y-dn2p0
#   export LOCAL_DEST=~/Desktop/tipmip/tas
#   bash scripts/pull_gmstmon_local.sh

set -euo pipefail

TIPMIP_EXP="${TIPMIP_EXP:?set TIPMIP_EXP}"
DKRZ_USER="${DKRZ_USER:-b383937}"
LOCAL_DEST="${LOCAL_DEST:-$HOME/Desktop/tipmip/tas}"

LEVANTE_SRC="/work/bm1448/analysis/harteg/merged/tas/${TIPMIP_EXP}/gmstmon"
DEST="${LOCAL_DEST}/${TIPMIP_EXP}/gmstmon"
mkdir -p "${DEST}"

echo "Pulling ${LEVANTE_SRC} -> ${DEST}"
rsync -avP \
  "${DKRZ_USER}@levante.dkrz.de:${LEVANTE_SRC}/" \
  "${DEST}/"

echo "Done. Files:"
ls -lh "${DEST}"
