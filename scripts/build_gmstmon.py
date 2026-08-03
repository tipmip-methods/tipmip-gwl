#!/usr/bin/env python3
"""
Build ``gmstmon`` files (monthly area-weighted global-mean ``tas``) from raw CMIP
chunks listed in a hand-maintained path manifest.

Maintainer script — not part of the installed ``tipmip_gwl`` package. The
days-in-month weighted **annual** mean is applied later by
:func:`tipmip_gwl.io.load_gmsat_nc` when you read the file.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import xarray as xr

TAS_TABLES = ("Amon", "APmon")
TIMERANGE_RE = re.compile(r"^(?P<tstart>\d+)-(?P<tend>\d+)$")

# Manifest ``experiment_id`` may use canonical gwl* names while NorESM tas paths
# retain swl* in filenames (see maintainer ``levante_tas_manifest.tsv``).
EXPERIMENT_ALIASES: dict[str, tuple[str, ...]] = {
    "esm-up2p0-gwl2p0-50y-dn2p0": ("esm-up2p0-swl2p0-50y-dn2p0",),
    "esm-up2p0-gwl4p0-50y-dn2p0": ("esm-up2p0-swl4p0-50y-dn2p0",),
}


def _experiment_ids_for_build(exp: str) -> frozenset[str]:
    return frozenset((exp, *EXPERIMENT_ALIASES.get(exp, ())))


def parse_tas_chunk(path: Path | str) -> dict | None:
    """Parse CMIP-style ``tas_*`` chunk filename; return metadata or ``None``."""
    path = Path(path)
    parts = path.stem.split("_")
    if len(parts) < 7 or parts[0] != "tas" or parts[1] not in TAS_TABLES:
        return None
    m = TIMERANGE_RE.match(parts[-1])
    if m is None:
        return None
    return {
        "path": path,
        "table": parts[1],
        "model": "_".join(parts[2:-4]),
        "exp": parts[-4],
        "member": parts[-3],
        "grid": parts[-2],
        "tstart": m.group("tstart"),
        "tend": m.group("tend"),
    }


def gmstmon_filename(meta: dict) -> str:
    return (
        f"tas_{meta['table']}_{meta['model']}_{meta['exp']}_"
        f"{meta['member']}_{meta['grid']}_gmstmon.nc"
    )


def load_tas_chunks(
    manifest: Path | str,
    exp: str,
    *,
    models: list[str] | None = None,
) -> dict[str, list[Path]]:
    """Load chunk paths from a TSV manifest: ``model``, ``experiment_id``, ``path``."""
    manifest = Path(manifest)
    selected = set(models) if models else None
    grouped: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    exp_ids = _experiment_ids_for_build(exp)

    with manifest.open(newline="") as f:
        lines = [
            line
            for line in f
            if line.strip() and not line.lstrip().startswith("#")
        ]
        reader = csv.DictReader(lines, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"empty manifest: {manifest}")
        for row in reader:
            if not row or row.get("model", "").startswith("#"):
                continue
            model = row["model"].strip()
            row_exp = row["experiment_id"].strip()
            path = Path(row["path"].strip())
            if row_exp not in exp_ids:
                continue
            if selected is not None and model not in selected:
                continue
            meta = parse_tas_chunk(path)
            if meta is None:
                raise ValueError(f"cannot parse tas chunk filename: {path.name}")
            grouped[model].append((meta["tstart"], path))

    out: dict[str, list[Path]] = {}
    for model, items in grouped.items():
        items.sort(key=lambda x: x[0])
        out[model] = [p for _, p in items]
    return out


def _spatial_dims(da: xr.DataArray) -> list[str]:
    return [d for d in da.dims if d not in ("time", "bnds")]


def _area_weights(da: xr.DataArray, areacella: xr.DataArray | None) -> xr.DataArray:
    dims = _spatial_dims(da)
    if areacella is not None:
        w = areacella.astype("float64")
        for dim in dims:
            if dim not in w.dims:
                w = w.squeeze(dim=dim, drop=True)
        w = w.broadcast_like(da.isel(time=0, drop=False))
    elif "lat" in dims and "lon" in dims:
        cos_lat = np.cos(np.deg2rad(da["lat"].astype("float64")))
        w = cos_lat * xr.ones_like(da["lon"])
    else:
        raise ValueError(
            f"cannot infer area weights for dims {dims}; pass areacella or use a lat/lon grid"
        )
    w = w.where(np.isfinite(w) & (w >= 0))
    w = w / w.sum(dim=dims, skipna=True)
    return w


def monthly_global_mean(
    da: xr.DataArray,
    areacella: xr.DataArray | None = None,
) -> xr.DataArray:
    """Area-weighted global mean, preserving monthly ``time``."""
    dims = _spatial_dims(da)
    w = _area_weights(da, areacella)
    return (da * w).sum(dim=dims, skipna=True)


def _open_time_coder():
    try:
        return xr.coders.CFDatetimeCoder(use_cftime=True)
    except AttributeError:
        return True  # type: ignore[return-value]


def _monthly_keep_indices(da: xr.DataArray) -> tuple[list[int], list[str]]:
    """Return indices of the first occurrence of each calendar (year, month)."""
    warns: list[str] = []
    if da.sizes.get("time", 0) == 0:
        return [], warns

    years = da["time"].dt.year.values
    months = da["time"].dt.month.values
    keep: list[int] = []
    seen: set[tuple[int, int]] = set()
    buckets: dict[tuple[int, int], list[float]] = defaultdict(list)

    flat = np.asarray(da.values, dtype=float).reshape(da.sizes["time"], -1)[:, 0]
    for i, (y, m) in enumerate(zip(years, months)):
        key = (int(y), int(m))
        buckets[key].append(float(flat[i]))
        if key in seen:
            continue
        seen.add(key)
        keep.append(i)

    dropped = da.sizes["time"] - len(keep)
    if dropped:
        conflicts = sum(
            1
            for vals in buckets.values()
            if len(vals) > 1 and (max(vals) - min(vals)) > 1e-6
        )
        if conflicts:
            warns.append(
                f"deduplicated {dropped} overlapping monthly timesteps "
                f"({conflicts} month(s) with differing values)"
            )
        else:
            warns.append(
                f"deduplicated {dropped} overlapping monthly timesteps (values identical)"
            )
    return keep, warns


def _dedupe_monthly_time(da: xr.DataArray) -> tuple[xr.DataArray, list[str]]:
    """Keep the first timestep for each calendar (year, month) after a merge."""
    keep, warns = _monthly_keep_indices(da)
    if not keep or len(keep) == da.sizes["time"]:
        return da, warns
    return da.isel(time=keep), warns


def _dedupe_monthly_dataset(ds: xr.Dataset, var: str = "tas") -> tuple[xr.Dataset, list[str]]:
    """Drop duplicate calendar months on ``var``'s time axis."""
    if var not in ds:
        return ds, []
    keep, warns = _monthly_keep_indices(ds[var])
    if not keep or len(keep) == ds.sizes.get("time", 0):
        return ds, warns
    out = ds.isel(time=keep)
    extra_vars = [name for name in out.data_vars if name != var]
    if extra_vars:
        out = out.drop_vars(extra_vars)
    bnds = [name for name in out.coords if name.endswith("_bnds")]
    if bnds:
        out = out.drop_vars(bnds)
    return out, warns


def _write_gmstmon_dataset(out: xr.Dataset, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_netcdf(out_path)


def build_gmstmon_xarray(
    chunks: list[Path | str],
    out_path: Path | str,
    *,
    areacella_path: Path | str | None = None,
    overwrite: bool = False,
) -> Path:
    """Merge ``tas`` chunks and write a monthly ``gmstmon`` NetCDF."""
    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(out_path)

    chunk_paths = [Path(p) for p in chunks]
    meta = parse_tas_chunk(chunk_paths[0])
    if meta is None:
        raise ValueError(f"not a tas chunk filename: {chunk_paths[0].name}")

    coder = _open_time_coder()
    areacella = None
    if areacella_path is not None:
        with xr.open_dataset(areacella_path, decode_times=False) as ac:
            areacella = ac["areacella"].load()

    ds = xr.open_mfdataset(
        [str(p) for p in chunk_paths],
        combine="by_coords",
        decode_times=coder,
        data_vars="minimal",
        coords="minimal",
        compat="override",
    )
    try:
        gm = monthly_global_mean(ds["tas"], areacella)
        gm = gm.expand_dims(
            {"lat": [float(ds["lat"].values[0])], "lon": [float(ds["lon"].values[0])]}
        )
        gm.name = "tas"
        gm.attrs.update({k: v for k, v in ds["tas"].attrs.items() if k not in gm.attrs})

        out = xr.Dataset({"tas": gm})
        out.attrs.update(dict(ds.attrs))
        out.attrs["title"] = (
            f"Monthly area-weighted global mean tas for {meta['model']} {meta['exp']}"
        )
        out, dedupe_warns = _dedupe_monthly_dataset(out)
        for w in dedupe_warns:
            print(f"  WARN {out_path.name}: {w}")
        _write_gmstmon_dataset(out, out_path)
    finally:
        ds.close()
    return out_path


def build_gmstmon_cdo(
    chunks: list[Path | str],
    out_path: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """Merge and reduce with CDO (``mergetime`` + ``fldmean``) when available."""
    cdo = shutil.which("cdo")
    if cdo is None:
        raise RuntimeError("cdo not found on PATH")

    out_path = Path(out_path)
    if out_path.exists() and not overwrite:
        raise FileExistsError(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_paths = [str(p) for p in chunks]
    with tempfile.TemporaryDirectory() as tmp:
        merged = Path(tmp) / "merged.nc"
        if len(chunk_paths) == 1:
            shutil.copy2(chunk_paths[0], merged)
        else:
            subprocess.run(
                [cdo, "-O", "mergetime", *chunk_paths, str(merged)],
                check=True,
            )
        subprocess.run(
            [cdo, "-O", "fldmean", str(merged), str(out_path)],
            check=True,
        )

    coder = _open_time_coder()
    ds = xr.open_dataset(out_path, decode_times=coder)
    try:
        out, dedupe_warns = _dedupe_monthly_dataset(ds)
        for w in dedupe_warns:
            print(f"  WARN {out_path.name}: {w}")
        if out.sizes.get("time", 0) != ds.sizes.get("time", 0):
            tmp = out_path.with_suffix(".dedupe_tmp.nc")
            out.to_netcdf(tmp)
            tmp.replace(out_path)
    finally:
        ds.close()
    return out_path


def build_gmstmon(
    chunks: list[Path | str],
    out_path: Path | str,
    *,
    areacella_path: Path | str | None = None,
    backend: str = "auto",
    overwrite: bool = False,
) -> Path:
    """Build one ``gmstmon`` file from raw ``tas`` chunks."""
    if backend == "cdo":
        return build_gmstmon_cdo(chunks, out_path, overwrite=overwrite)
    if backend == "xarray":
        return build_gmstmon_xarray(
            chunks, out_path, areacella_path=areacella_path, overwrite=overwrite
        )
    if shutil.which("cdo"):
        return build_gmstmon_cdo(chunks, out_path, overwrite=overwrite)
    return build_gmstmon_xarray(
        chunks, out_path, areacella_path=areacella_path, overwrite=overwrite
    )


def build_batch(
    manifest: Path | str,
    exp: str,
    outdir: Path | str,
    *,
    models: list[str] | None = None,
    backend: str = "auto",
    overwrite: bool = False,
) -> list[Path]:
    """Build ``gmstmon`` for all models listed in the manifest for one experiment."""
    outdir = Path(outdir)
    chunk_map = load_tas_chunks(manifest, exp, models=models)
    if not chunk_map:
        raise ValueError(f"no rows for experiment {exp!r} in {manifest}")

    written: list[Path] = []
    for model in sorted(chunk_map):
        chunks = chunk_map[model]
        meta = parse_tas_chunk(chunks[0])
        assert meta is not None
        out_path = outdir / gmstmon_filename(meta)
        if out_path.exists() and not overwrite:
            print(f"SKIP {model}: exists ({out_path})")
            written.append(out_path)
            continue

        print(f"BUILD {model}: {len(chunks)} chunk(s) -> {out_path.name}")
        build_gmstmon(chunks, out_path, backend=backend, overwrite=True)
        written.append(out_path)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build gmstmon (monthly global-mean tas) from CMIP chunks."
    )
    parser.add_argument(
        "--chunks",
        nargs="+",
        help="raw tas chunk file(s); writes one gmstmon file",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="output gmstmon .nc (with --chunks; inferred if --outdir is set)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="TSV with columns model, experiment_id, path (required for batch mode)",
    )
    parser.add_argument(
        "--exp",
        help="experiment id for batch mode, e.g. esm-up2p0 or esm-piControl",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        help="output directory for batch mode (or with --chunks)",
    )
    parser.add_argument(
        "--models",
        help="comma-separated subset of models for batch mode",
    )
    parser.add_argument(
        "--areacella",
        type=Path,
        help="optional areacella file (xarray backend only)",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "cdo", "xarray"),
        default="auto",
        help="auto prefers cdo when installed, else xarray",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    if args.chunks:
        chunks = [Path(c) for c in args.chunks]
        if args.out is not None:
            out = args.out
        elif args.outdir is not None:
            meta = parse_tas_chunk(chunks[0])
            if meta is None:
                parser.error(f"cannot parse chunk filename: {chunks[0]}")
            out = args.outdir / gmstmon_filename(meta)
        else:
            meta = parse_tas_chunk(chunks[0])
            if meta is None:
                parser.error(f"cannot parse chunk filename: {chunks[0]}")
            out = Path(gmstmon_filename(meta))

        build_gmstmon(
            chunks,
            out,
            areacella_path=args.areacella,
            backend=args.backend,
            overwrite=args.overwrite,
        )
        print(f"Wrote {out}")
        return

    if not args.exp or not args.outdir:
        parser.error("batch mode requires --exp and --outdir")

    if not args.manifest:
        parser.error("batch mode requires --manifest (path to tas chunk TSV)")

    manifest = args.manifest
    if not manifest.is_file():
        parser.error(f"manifest not found: {manifest}")

    models = None
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]

    written = build_batch(
        manifest,
        args.exp,
        args.outdir,
        models=models,
        backend=args.backend,
        overwrite=args.overwrite,
    )
    print(f"\n{len(written)} gmstmon file(s) in {args.outdir}")


if __name__ == "__main__":
    main(sys.argv[1:])
