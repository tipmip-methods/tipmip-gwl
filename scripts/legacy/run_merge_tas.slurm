#!/bin/bash
#SBATCH --account=bm1448
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --job-name=merge_tas
#SBATCH --output=/work/bm1448/analysis/harteg/merge_tas_%j.log

# Merge + monthly area-weighted global mean for both legs. The days-in-month
# weighted ANNUAL mean (GMSAT) is computed later in Python (calendar-aware).
export VAR=tas
export REDUCE="${REDUCE:-gmstmon}"

for exp in esm-up2p0 esm-piControl; do
  echo "############ ${VAR} ${exp} ############"
  TIPMIP_EXP="${exp}" bash /work/bm1448/analysis/harteg/merge_var.sh
done
