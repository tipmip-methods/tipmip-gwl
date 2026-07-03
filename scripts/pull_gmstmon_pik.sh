#!/bin/bash
# Pull merged gmstmon tas files from Levante to PIK scratch.
#
# Setup:
#   export DKRZ_USER=b383937
#   export LEVENTE_KEY=$HOME/.ssh/id_ed25519_levante   # optional SSH key
#
# Usage (on a PIK login node):
#   export TIPMIP_EXP=esm-up2p0          # or esm-piControl
#   bash pull_gmstmon_pik.sh

set -euo pipefail

TIPMIP_EXP="${TIPMIP_EXP:?set TIPMIP_EXP}"
DKRZ_USER="${DKRZ_USER:-b383937}"
SSH_KEY="${LEVANTE_KEY:-${HOME}/.ssh/id_ed25519_levante}"

LEVANTE_SRC="/work/bm1448/analysis/harteg/merged/tas/${TIPMIP_EXP}/gmstmon"
PIK_DEST="/p/tmp/${USER}/data/tipmip/tas/${TIPMIP_EXP}/gmstmon"
mkdir -p "${PIK_DEST}"

RSYNC_SSH=()
if [[ -f "${SSH_KEY}" ]]; then
  RSYNC_SSH=(-e "ssh -i ${SSH_KEY} -o IdentitiesOnly=yes -o BatchMode=yes")
fi

echo "Pulling ${LEVANTE_SRC} -> ${PIK_DEST}"
rsync -avP "${RSYNC_SSH[@]}" \
  "${DKRZ_USER}@levante.dkrz.de:${LEVANTE_SRC}/" \
  "${PIK_DEST}/"

echo "Done. Files on PIK:"
ls -lh "${PIK_DEST}"
