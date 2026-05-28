# xamrex xroms Format Conversion

## Overview

xamrex includes built-in support for converting AMReX plotfile data to [xroms](https://github.com/xoceanmodel/xroms)-compatible format. This enables seamless integration with xroms analysis tools for ocean model post-processing, including derivative calculations, grid interpolation, and other specialized operations.

## Why xroms Format?

xroms expects data in ROMS (Regional Ocean Modeling System) format with specific coordinate naming conventions. The xroms conversion feature automatically:

1. **Renames coordinates** from AMReX naming to ROMS naming conventions
2. **Adds CF-compliant attributes** for xgcm (extended grid context manager) compatibility
3. **Provides vertical parameters** needed by xroms (Vtransform, Vstretching, etc.)
4. **Generates s-coordinates** if needed for vertical positioning

## Quick Start

```python
from xamrex import AMReXEntrypoint

# Create entry point
ep = AMReXEntrypoint()

# Load plotfile in xroms format
ds = ep.open_dataset(
    'path/to/plotfile',
    xroms_format=True,           # Enable xroms format conversion
  xroms_vtransform=2,          # ROMS vertical transform (1=old, 2=new)
  xroms_grid_file='path/to/roms_grid_or_ini.nc',  # Optional metadata source (hc, Cs_r, Cs_w, ...)
  xroms_strict_grid=False,     # True = fail if any grid fields cannot be conformed
)

# Dataset is now ready for xroms operations
print(ds.coords)  # Shows xi_rho, eta_rho, s_rho, etc.
```

## Coordinate Naming Convention

### Horizontal Coordinates

| AMReX Name | xroms Name | Grid Position | Description |
|-----------|----------|---------------|-------------|
| `x` | `xi_rho` | Cell centers (x) | RHO-grid x-coordinates |
| `x_u` | `xi_u` | U-points (x) | U-grid x-coordinates (staggered in x) |
| `x_psi` | `xi_psi` | Corner points (x) | PSI-grid x-coordinates |
| `y` | `eta_rho` | Cell centers (y) | RHO-grid y-coordinates |
| `y_v` | `eta_v` | V-points (y) | V-grid y-coordinates (staggered in y) |
| `y_psi` | `eta_psi` | Corner points (y) | PSI-grid y-coordinates |

### Vertical Coordinates

| AMReX Name | xroms Name | Grid Position | Description |
|-----------|----------|---------------|-------------|
| `z` | `s_rho` | Cell centers (z) | RHO-grid z-coordinates (default: -1 to 0) |
| `z_w` | `s_w` | W-points (z) | W-grid z-coordinates (staggered in z) |

## C-Grid Staggering

The converted dataset respects the Arakawa C-grid staggering convention used in ocean models:

```
       RHO-grid          U-grid           V-grid
       (centers)         (x-face)         (y-face)

    ┌───┬───┬───┐     ┌──•──┬──•──┬──•──┐   ┌───┬───┬───┐
    │ • │ • │ • │     │     │     │     │   │ • • • │
    ├───┼───┼───┤     ├──•──┼──•──┼──•──┤   ├───────┤
    │ • │ • │ • │     │     │     │     │   │ • • • │
    ├───┼───┼───┤     ├──•──┼──•──┼──•──┤   ├───────┤
    │ • │ • │ • │     │     │     │     │   │ • • • │
    └───┴───┴───┘     └──•──┴──•──┴──•──┘   └───┴───┴───┘
    
    Variables:        Variables:         Variables:
    temp, salt,       u_vel, u_velx      v_vel, v_vely
    x_velocity,
    y_velocity
```

Data variables are automatically assigned to the correct grid based on their stagger position:

- **RHO-grid**: Scalar variables (temp, salt) and diagnostic velocity components
- **U-grid**: u-component of velocity (staggered in x-direction)
- **V-grid**: v-component of velocity (staggered in y-direction)
- **W-grid**: w-component of velocity (staggered in z-direction)
- **PSI-grid**: Corner points (vorticity calculations, etc.)

## Parameter Reference

### `open_dataset()` Parameters for xroms Conversion

```python
ds = ep.open_dataset(
    filename_or_obj,
    xroms_format: bool = False,      # Enable xroms format conversion
  xroms_vtransform: int = 2,       # ROMS vertical transform
  xroms_grid_file: str | Path | xr.Dataset | None = None,  # Optional ROMS metadata source
  xroms_strict_grid: bool = False,  # Fail-fast on unconformable grid fields
    # ... other parameters
)
```

**Parameters:**

- `xroms_format` (bool): 
  - If `True`, converts coordinates and dimensions to xroms-compatible format
  - If `False` (default), keeps standard AMReX naming
  - Default: `False`

- `xroms_vtransform` (int):
  - ROMS vertical transform type for s-coordinate system
  - `1`: Old transform
  - `2`: New transform (default; Shchepetkin & McWilliams, more accurate for thin surface layers)
  - Only used if dataset doesn't already have `Vtransform` attribute
  - Default: `2`

- `xroms_grid_file` (str, Path, or xr.Dataset):
  - Optional source dataset used to fill missing ROMS variables needed by xroms
  - Useful when AMReX plotfiles do not include values like `hc`, `Cs_r`, `Cs_w`, or `h`
  - Existing variables in the AMReX dataset are not overwritten (merge is fill-only)
  - Can be a file path (e.g., grid/initial/history NetCDF) or an already-open `xarray.Dataset`

- `xroms_strict_grid` (bool):
  - If `True` and `xroms_grid_file` is provided, raise an error when candidate
    grid variables/coordinates cannot be conformed to the dataset shape
  - If `False` (default), incompatible fields are skipped with warnings

## Requirements and Data Sources

When using `xroms_format=True`, there are two levels of requirements:

1. **Coordinate rename/CF metadata only** (basic xgcm grid-aware operations)
2. **Full `xroms.roms_dataset(...)` vertical-depth workflow** (computes `z_rho`, `z_w`, metrics)

### Minimum for Basic xroms-Format Conversion

At minimum, AMReX plotfiles need the core staggered coordinates/variables that map to ROMS-style dimensions:

- Horizontal coordinates: `x`, `y` (plus staggered coordinates if present)
- Vertical coordinates: `z` and optionally `z_w`
- Data variables can remain AMReX-native names; aliases (`u`, `v`, `w`) are added when possible

This mode is enough for many horizontal/staggered-grid operations but not enough for full physical depth reconstruction.

### Required for `xroms.roms_dataset()` Depth Calculations

To compute physically meaningful vertical coordinates (`z_rho`, `z_w`) with `Vtransform` 1 or 2, the dataset must include:

- `h` (bathymetry)
- `zeta` (free surface elevation)
- `Cs_r` and `Cs_w` (stretching curves)
- `s_rho` and `s_w` (sigma coordinates)
- `hc` (critical depth parameter; scalar variable preferred)

`xroms_grid_file` is intended to provide static ROMS metadata (`h`, `Cs_r`, `Cs_w`, masks, metrics, lon/lat, etc.) when missing from plotfiles.

Important:

- `zeta` is typically time-dependent and should usually come from the plotfile/history data being analyzed.
- If `zeta` is absent, `xroms.roms_dataset()` cannot compute realistic time-varying depths.
- If a variable already exists in the AMReX dataset, it is **not** replaced by `xroms_grid_file`; this can preserve mismatched values if names collide.

### Grid File Expectations (`xroms_grid_file`)

Recommended source: a ROMS-compatible NetCDF grid/ini/history file with dimensions that can conform to the AMReX dataset.

Typical useful fields:

- Required for depth reconstruction support: `h`, `Cs_r`, `Cs_w`, `s_rho`, `s_w`
- Common horizontal metadata: `pm`, `pn`, `f`, `angle`, `mask_rho`, `mask_u`, `mask_v`, `mask_psi`, `lon_*`, `lat_*`
- Vertical transform metadata: `Vtransform`, `Vstretching`
- `hc` as either:
  - scalar variable (preferred), or
  - global attribute (supported; promoted to scalar dataset variable during conversion)

If dimensions are incompatible, fields are skipped (or raise with `xroms_strict_grid=True`).

### Vertical Coordinate Semantics

`xroms` expects sigma-style vertical coordinates (`s_rho`, `s_w`) in approximately `[-1, 0]` and bottom-to-surface ordering.

`xamrex` conversion now normalizes non-sigma vertical coordinates (for example physical-z plotfile coordinates) to sigma coordinates so depth formulas are consistent with ROMS conventions.

## Dataset Attributes

After conversion, the dataset includes these ROMS-specific attributes:

```python
ds.attrs['Vtransform']   # Vertical transform type (1 or 2)
ds.attrs['Vstretching']  # Stretching function type (default: 4)
```

## Handling Missing Variables

A warning is issued if the dataset lacks variables needed for full xroms functionality:

```
Dataset missing ROMS variables: h, zeta, Cs_r, Cs_w, hc.
Some xroms functionality (e.g., z-coordinate computation) may be limited.
These are optional for basic grid operations.
```

**What these variables do:**

| Variable | Purpose |
|----------|---------|
| `h` | Water depth (bathymetry) for z-coordinate computation |
| `zeta` | Sea surface elevation for z-coordinate computation |
| `Cs_r` | Stretching curves at RHO-points |
| `Cs_w` | Stretching curves at W-grid points |
| `hc` | Critical depth for vertical coordinate stretching |

**When do you need them?**

- **Required for**: Computing actual z-coordinates (physical depths)
- **Optional for**: Grid operations, interpolation, staggered grid analysis
- **Common availability**: Full ROMS output files usually include these; simplified plotfiles often do not

## Usage Examples

### Example 1: Load and Inspect

```python
from xamrex import AMReXEntrypoint

ep = AMReXEntrypoint()
ds = ep.open_dataset('plt_my_case', xroms_format=True)

# Inspect coordinates
print("Horizontal dimensions:")
print(f"  xi_rho: {len(ds.xi_rho)}, xi_u: {len(ds.xi_u) if 'xi_u' in ds else 'N/A'}")
print(f"  eta_rho: {len(ds.eta_rho)}, eta_v: {len(ds.eta_v) if 'eta_v' in ds else 'N/A'}")
print(f"Vertical dimensions:")
print(f"  s_rho: {len(ds.s_rho)}, s_w: {len(ds.s_w)}")

# Check which data variables exist
print("\nData variables on each grid:")
for var in ds.data_vars:
    dims = ds[var].dims
    grid = "RHO" if "xi_u" not in dims else "U"
    print(f"  {var}: {dims} ({grid}-grid)")
```

### Example 2: Analyze Velocity Fields

```python
# Velocity components are on staggered grids
u_vel = ds.u_vel   # On U-grid (xi_u, eta_rho, s_rho)
v_vel = ds.v_vel   # On V-grid (xi_rho, eta_v, s_rho)
w_vel = ds.w_vel   # On W-grid (xi_rho, eta_rho, s_w)

# Access data at specific depths
surface_u = ds.u_vel.isel(s_rho=-1)  # Surface layer
bottom_u = ds.u_vel.isel(s_rho=0)     # Bottom layer

# Select spatial region
region = ds.isel(xi_rho=slice(100, 200), eta_rho=slice(50, 150))
```

### Example 3: With xgcm for Interpolation

```python
from xamrex.xroms_compat import _create_xgcm_grid

# Create xgcm Grid for interpolation operations
xgrid = _create_xgcm_grid(ds)

# Interpolate U velocity to RHO points
u_to_rho = xgrid.interp(ds.u_vel, 'X', boundary='fill')

# Interpolate V velocity to RHO points
v_to_rho = xgrid.interp(ds.v_vel, 'Y', boundary='fill')

# Compute speed on RHO grid
speed_on_rho = (u_to_rho**2 + v_to_rho**2)**0.5
```

### Example 4: Multiple Time Steps

```python
# Convert multiple plotfiles in time series
import glob

plotfiles = sorted(glob.glob('output/plt_*'))
ds_time = ep.open_dataset(plotfiles, xroms_format=True)

# Now you have time dimension with xroms format
print(ds_time.ocean_time)  # Time coordinate
print(ds_time.u_vel.shape)  # (time, z, y, x)

# Analyze time evolution
surface_temp_evolution = ds_time.temp.isel(s_rho=-1)
```

### Example 5: Supply ROMS Metadata From Grid File

```python
from xamrex import AMReXEntrypoint

ep = AMReXEntrypoint()
ds = ep.open_dataset(
  'path/to/plotfiles',
  xroms_format=True,
  xroms_grid_file='path/to/roms_grid_1km.nc',  # supplies hc/Cs_r/Cs_w/h/etc.
)

# Now xroms.roms_dataset(ds, Vtransform=2) has required vertical metadata.
```

### Example 6: Ensure `zeta` Is Present for Depth Calculations

```python
import xarray as xr
from xamrex import AMReXEntrypoint

ep = AMReXEntrypoint()

ds = ep.open_dataset(
  'path/to/plotfiles',
  xroms_format=True,
  xroms_grid_file='path/to/roms_grid_1km.nc',
)

# If zeta is missing, xroms depth calculations will fail or be non-physical.
# Provide zeta from a matching history/ini source when available.
if 'zeta' not in ds:
    zeta_src = xr.open_dataset('path/to/matching_history_or_ini.nc')['zeta']
    ds['zeta'] = zeta_src

# Then call xroms.roms_dataset(ds, Vtransform=2)
```

## Coordinate Attributes

After conversion, all coordinates have CF-compliant metadata:

```python
print(ds.xi_rho.attrs)
# Output:
# {
#     'axis': 'X',
#     'long_name': 'xi-coordinate on RHO-points',
#     'units': 'm',
#     'c_grid_axis_shift': 0.0
# }

print(ds.s_w.attrs)
# Output:
# {
#     'axis': 'Z',
#     'long_name': 's-coordinate on W-points (0 < s < -1)',
#     'units': 'nondimensional',
#     'valid_min': -1.0,
#     'valid_max': 0.0,
#     'c_grid_axis_shift': -0.5
# }
```

These attributes are used by xgcm and other tools for grid-aware operations.

## Comparison: Before and After

### Before Conversion (AMReX format)

```python
ds = ep.open_dataset('plotfile')
print(ds.coords)
# Output:
# Coordinates:
#   ocean_time  (ocean_time) float64 0.0
#   x           (x) float64 0.0 200.0 400.0 ... 8200.0
#   y           (y) float64 0.0 50.0 100.0 ... 700.0
#   z           (z) float64 -9.688 -9.062 -8.438 ... -0.312
#   x_psi       (x_psi) float64 100.0 300.0 500.0 ... 8300.0
#   y_psi       (y_psi) float64 25.0 75.0 125.0 ... 725.0
#   z_w         (z_w) float64 -10.0 -9.375 -8.75 ... 0.0
```

### After Conversion (xroms format)

```python
ds = ep.open_dataset('plotfile', xroms_format=True)
print(ds.coords)
# Output:
# Coordinates:
#   ocean_time  (ocean_time) float64 0.0
#   xi_rho      (xi_rho) float64 0.0 200.0 400.0 ... 8200.0
#   eta_rho     (eta_rho) float64 0.0 50.0 100.0 ... 700.0
#   s_rho       (s_rho) float64 -0.969 -0.906 -0.844 ... -0.031
#   xi_psi      (xi_psi) float64 100.0 300.0 500.0 ... 8300.0
#   eta_psi     (eta_psi) float64 25.0 75.0 125.0 ... 725.0
#   s_w         (s_w) float64 -1.0 -0.938 -0.875 ... 0.0
```

## Troubleshooting

### Issue: "Dataset missing ROMS variables"

**Cause**: The plotfile lacks certain variables needed for full xroms functionality.

**Solution**: This is a warning, not an error. For many analyses, these variables aren't needed:
- If you only need grid positioning and staggered grid analysis: **No action needed**
- If you need z-coordinates: **Manually add** bathymetry (`h`) and sea surface height (`zeta`)

### Issue: Dimension mismatch with xroms functions

**Cause**: xroms functions expect specific dimension naming conventions.

**Solution**: Verify the dataset was converted with `xroms_format=True` and check:
```python
print(sorted(ds.coords))  # Should show xi_rho, eta_rho, s_rho, etc.
```

### Issue: Plotfile vs NetCDF `z_rho` disagree strongly

**Common causes**:

- `zeta` missing or sourced from a different run/time than the plotfile state
- `h`, `Cs_r`, `Cs_w`, or `hc` differ between the two datasets
- Sigma coordinate ordering mismatch (`s_rho` reversed)
- Horizontal index mismatch when comparing subsets (for example one dataset cropped with `1:-1` and the other not)

**Checks**:

```python
print(ds.s_rho.values[:3], ds.s_rho.values[-3:])
print('has zeta:', 'zeta' in ds)
print('has h/Cs/hc:', [k for k in ['h', 'Cs_r', 'Cs_w', 'hc'] if k in ds])
```

### Issue: xgcm Grid creation fails

**Cause**: xgcm not installed or coordinate structure doesn't match expectations.

**Solution**:
```python
# Install xgcm
pip install xgcm

# Check coordinate attributes
print(ds.xi_rho.attrs)  # Should have 'axis' attribute
```

## See Also

- [xroms Documentation](https://xroms.readthedocs.io/)
- [xgcm Documentation](https://xgcm.readthedocs.io/)
- [ROMS Model Documentation](https://www.myroms.org/)
- [Arakawa C-Grid](https://en.wikipedia.org/wiki/Arakawa_grids)
