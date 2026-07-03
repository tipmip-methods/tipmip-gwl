#!/bin/bash
# Generic merge + reduce on Levante. Reads merge_lists/<VAR>/<EXP>/manifest.tsv,
# merges time chunks per model, then applies the reduction recorded in the
# manifest (or overridden by REDUCE) so only small files leave Levante.
#
# Usage (on Levante):
#   export VAR=tas
#   export TIPMIP_EXP=esm-up2p0          # or esm-piControl
#   # optional: export REDUCE=gmst       # gmst | yearmax | none (else manifest)
#   bash merge_var.sh

set -euo pipefail

VAR="${VAR:?set VAR, e.g. export VAR=tas}"
TIPMIP_EXP="${TIPMIP_EXP:?set TIPMIP_EXP, e.g. export TIPMIP_EXP=esm-up2p0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LIST_DIR="${SCRIPT_DIR}/merge_lists/${VAR}/${TIPMIP_EXP}"
OUT_BASE="/work/bm1448/analysis/harteg/merged/${VAR}/${TIPMIP_EXP}"
MANIFEST="${LIST_DIR}/manifest.tsv"

module load cdo 2>/dev/null || true
command -v cdo >/dev/null 2>&1 || { echo "ERROR: cdo not found (module load cdo)" >&2; exit 1; }
[[ -f "${MANIFEST}" ]] || { echo "ERROR: manifest not found: ${MANIFEST}" >&2; exit 1; }

reduce_dir() {  # echo subdir name for a reduction
  case "$1" in
    gmstmon) echo "gmstmon" ;;
    gmst) echo "gmst" ;;
    yearmax) echo "annualmax" ;;
    *) echo "" ;;
  esac
}

reduce_cmd() {  # echo cdo operator chain for a reduction (empty for none)
  case "$1" in
    # gmstmon: monthly, area-weighted global mean only. The days-in-month
    # weighted ANNUAL mean is done in Python (calendar-aware), not here, so the
    # protocol baseline is not biased by cdo's unweighted yearmean/yearmonmean.
    gmstmon) echo "-fldmean" ;;
    # gmst: legacy annual (cdo unweighted yearmean) — kept for back-compat only.
    gmst) echo "-yearmean -fldmean" ;;
    yearmax) echo "yearmax" ;;
    *) echo "" ;;
  esac
}

while IFS=$'\t' read -r model exp member table grid n_files filelist merged_outfile mreduce reduced_outfile; do
  REDUCE_EFF="${REDUCE:-${mreduce}}"
  subdir="$(reduce_dir "${REDUCE_EFF}")"
  if [[ -n "${subdir}" ]]; then
    out_dir="${OUT_BASE}/${subdir}"
    out_name="${reduced_outfile}"
  else
    out_dir="${OUT_BASE}"
    out_name="${merged_outfile}"
  fi
  mkdir -p "${out_dir}"
  out_path="${out_dir}/${out_name}"

  if [[ -f "${out_path}" ]]; then
    echo "SKIP ${model}: exists (${out_path})"
    continue
  fi

  mapfile -t files < "${LIST_DIR}/${filelist}"
  [[ ${#files[@]} -gt 0 ]] || { echo "ERROR: empty list for ${model}" >&2; exit 1; }
  echo "MERGE ${model}: ${n_files} chunks (table=${table}, reduce=${REDUCE_EFF})"

  tmp="$(mktemp "${TMPDIR:-/tmp}/${VAR}_${model}_XXXXXX.nc")"
  if [[ ${#files[@]} -eq 1 ]]; then
    cp "${files[0]}" "${tmp}"
  else
    cdo -O mergetime "${files[@]}" "${tmp}"
  fi

  cmd="$(reduce_cmd "${REDUCE_EFF}")"
  if [[ -n "${cmd}" ]]; then
    echo "REDUCE ${model}: cdo ${cmd} -> ${out_name}"
    cdo -O ${cmd} "${tmp}" "${out_path}"
  else
    cp "${tmp}" "${out_path}"
  fi
  rm -f "${tmp}"
  echo "DONE ${model}: $(ls -lh "${out_path}" | awk '{print $5}')"
done < <(tail -n +2 "${MANIFEST}")

echo "Output in: ${OUT_BASE}"
find "${OUT_BASE}" -name '*.nc' -exec ls -lh {} +
