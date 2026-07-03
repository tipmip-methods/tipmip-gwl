#!/bin/bash
#SBATCH --partition=io
#SBATCH --qos=io
#SBATCH --account=tipmip
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=1
#SBATCH --output=pull-gmstmon-%j.out
#SBATCH --chdir=/p/tmp/jakobha

export DKRZ_USER="${DKRZ_USER:-b383937}"

# Where pull_gmstmon_pik.sh lives on PIK. Override with: sbatch --export=ALL,TIPMIP_GWL=...
TIPMIP_GWL="${TIPMIP_GWL:-/p/tmp/${USER}/tipmip-gwl}"

for exp in esm-up2p0 esm-piControl; do
  TIPMIP_EXP="${exp}" bash "${TIPMIP_GWL}/scripts/pull_gmstmon_pik.sh"
done
