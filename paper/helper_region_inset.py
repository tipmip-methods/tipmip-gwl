"""Small orthographic map insets highlighting regional averaging domains."""

from __future__ import annotations

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.patches as mpatches
import numpy as np
from cartopy.mpl.geoaxes import GeoAxes
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from helper_regional_diagnostics import (
    ANTARCTIC_LAT_MAX,
    ARCTIC_LAT_MIN,
    SPG_LAT_MAX,
    SPG_LAT_MIN,
    SPG_LON_MAX,
    SPG_LON_MIN,
)

_DEFAULT_OUTLINE = "#666666"
_COAST = "#9a9a9a"
_LAND = "#f2f2f2"
_OCEAN = "#fafafa"
_GLOBE_EDGE = "#d0d0d0"


def _make_inset(ax_parent, *, central_longitude: float, central_latitude: float) -> GeoAxes:
    return inset_axes(
        ax_parent,
        width="34%",
        height="34%",
        loc="upper right",
        borderpad=0.35,
        axes_class=GeoAxes,
        axes_kwargs={
            "projection": ccrs.Orthographic(
                central_longitude=central_longitude,
                central_latitude=central_latitude,
            )
        },
    )


def _style_globe(ax: GeoAxes) -> None:
    ax.set_global()
    ax.set_facecolor(_OCEAN)
    ax.add_feature(cfeature.OCEAN, facecolor=_OCEAN, edgecolor="none", zorder=0)
    ax.add_feature(cfeature.LAND, facecolor=_LAND, edgecolor="none", zorder=1)
    ax.coastlines(resolution="110m", linewidth=0.45, color=_COAST, zorder=2)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["geo"].set_edgecolor(_GLOBE_EDGE)
    ax.spines["geo"].set_linewidth(0.8)


def _outline_lon_lat_polygon(
    ax: GeoAxes,
    lons: np.ndarray,
    lats: np.ndarray,
    *,
    color: str,
) -> None:
    ax.plot(
        lons,
        lats,
        transform=ccrs.PlateCarree(),
        color=color,
        linewidth=1.35,
        solid_capstyle="round",
        solid_joinstyle="round",
        zorder=4,
    )


def _polar_cap_radius(ax: GeoAxes, lat_boundary: float) -> float:
    """Radius in projection coordinates of a zonal parallel on a pole-centred globe."""
    x, y = ax.projection.transform_point(0.0, lat_boundary, ccrs.PlateCarree())
    return float(np.hypot(x, y))


def _add_polar_cap(ax: GeoAxes, lat_boundary: float, *, color: str) -> None:
    """Outline a latitude cap on a pole-centred orthographic inset."""
    radius = _polar_cap_radius(ax, lat_boundary)
    ax.add_patch(
        mpatches.Circle(
            (0.0, 0.0),
            radius,
            transform=ax.projection,
            fill=False,
            edgecolor=color,
            linewidth=1.35,
            zorder=4,
        )
    )


def _lon_lat_box_polygon(
    lon_min: float,
    lon_max: float,
    lat_min: float,
    lat_max: float,
    *,
    edge_points: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Lon/lat box traced along meridians and parallels (curved on the globe)."""
    south_lons = np.linspace(lon_min, lon_max, edge_points)
    east_lats = np.linspace(lat_min, lat_max, edge_points)
    north_lons = np.linspace(lon_max, lon_min, edge_points)
    west_lats = np.linspace(lat_max, lat_min, edge_points)

    lons = np.concatenate(
        [south_lons, np.full(edge_points, lon_max), north_lons, np.full(edge_points, lon_min), [south_lons[0]]]
    )
    lats = np.concatenate(
        [np.full(edge_points, lat_min), east_lats, np.full(edge_points, lat_max), west_lats, [lat_min]]
    )
    return lons, lats


def add_spg_inset(ax_parent, *, outline_color: str = _DEFAULT_OUTLINE) -> None:
    """North Atlantic orthographic view with the SPG averaging box."""
    ax = _make_inset(ax_parent, central_longitude=-40.0, central_latitude=52.0)
    _style_globe(ax)
    lons, lats = _lon_lat_box_polygon(
        SPG_LON_MIN,
        SPG_LON_MAX,
        SPG_LAT_MIN,
        SPG_LAT_MAX,
    )
    _outline_lon_lat_polygon(ax, lons, lats, color=outline_color)


def add_arctic_inset(ax_parent, *, outline_color: str = _DEFAULT_OUTLINE) -> None:
    """North-pole orthographic view with the Arctic cap (≥60°N)."""
    ax = _make_inset(ax_parent, central_longitude=0.0, central_latitude=90.0)
    _style_globe(ax)
    _add_polar_cap(ax, ARCTIC_LAT_MIN, color=outline_color)


def add_antarctic_inset(ax_parent, *, outline_color: str = _DEFAULT_OUTLINE) -> None:
    """South-pole orthographic view with the Antarctic cap (≤50°S)."""
    ax = _make_inset(ax_parent, central_longitude=0.0, central_latitude=-90.0)
    _style_globe(ax)
    _add_polar_cap(ax, ANTARCTIC_LAT_MAX, color=outline_color)
