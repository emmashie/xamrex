"""
Example: Convert AMReX plotfile data to xroms-compatible format.

This example demonstrates how to use xamrex's xroms format conversion feature
to prepare AMReX/REMORA data for use with xroms analysis tools.
"""

from xamrex import AMReXEntrypoint
import xarray as xr

# =============================================================================
# Basic Usage: Convert to xroms format
# =============================================================================

ep = AMReXEntrypoint()

# Load a plotfile and automatically convert to xroms format
ds = ep.open_dataset(
    'path/to/plotfile',
    xroms_format=True,  # Enable xroms format conversion
   xroms_vtransform=2,  # ROMS vertical transform (1=old, 2=new)
   # Optional: supply ROMS metadata source when plotfiles lack hc/Cs_r/Cs_w/h
   # xroms_grid_file='path/to/roms_grid_or_ini.nc',
)

print("Converted dataset coordinates:")
print(ds.coords)
print("\nDataset attributes (includes ROMS parameters):")
print({k: v for k, v in ds.attrs.items() if k in ['Vtransform', 'Vstretching']})

# =============================================================================
# Coordinate Naming Convention
# =============================================================================

# AMReX → xroms coordinate mapping:
#
# Horizontal:
#   x        → xi_rho     (cell centers in x)
#   x_u      → xi_u       (u-point locations in x)
#   x_psi    → xi_psi     (psi-point/corner locations)
#   y        → eta_rho    (cell centers in y)
#   y_v      → eta_v      (v-point locations in y)
#   y_psi    → eta_psi    (psi-point/corner locations)
#
# Vertical:
#   z        → s_rho      (cell centers in z)
#   z_w      → s_w        (w-point locations in z)

print("\nCoordinates available after conversion:")
for name in ['xi_rho', 'xi_u', 'eta_rho', 'eta_v', 's_rho', 's_w']:
    if name in ds.coords:
        print(f"  {name}: {len(ds.coords[name])} points")

# =============================================================================
# Data Variables and Grid Positions
# =============================================================================

print("\nData variables and their grid positions:")
for var in sorted(ds.data_vars):
    dims = ds[var].dims
    # Infer grid position from dimensions
    if 'xi_u' in dims:
        grid = "U-grid (x-face)"
    elif 'eta_v' in dims:
        grid = "V-grid (y-face)"
    elif 's_w' in dims and 'eta_v' not in dims and 'xi_u' not in dims:
        grid = "W-grid (z-face)"
    else:
        grid = "RHO-grid (cell centers)"
    print(f"  {var:20s} {dims} [{grid}]")

# =============================================================================
# Using with xroms (if available)
# =============================================================================

try:
    import xroms
    
    print("\n=== xroms Integration ===")
    print("Note: xroms may require additional variables like 'h' (bathymetry),")
    print("'zeta' (sea surface height), and stretching parameters (Cs_r, Cs_w, hc).")
    print("\nFor simple grid operations without z-coordinate computation:")
    
    # Create xgcm Grid (needed for xroms interpolation)
    from xamrex.xroms_compat import _create_xgcm_grid
    xgrid = _create_xgcm_grid(ds)
    
    print("✓ xgcm Grid created successfully")
    print(f"  Grid coordinates: {list(xgrid.coords.keys())}")
    
    # Now you can use xroms features like:
    # - Interpolate between grids: xgrid.interp(data, 'X')
    # - Work with staggered velocity fields
    # - Compute derivatives and other operations
    
except ImportError:
    print("\nNote: xroms not installed. Install with: pip install xroms")

# =============================================================================
# Typical Workflow
# =============================================================================

print("\n=== Typical Workflow ===")
print("""
1. Load data with xroms format enabled:
   ds = ep.open_dataset(plotfile, xroms_format=True)

2. Check available variables:
   print(ds.data_vars)

3. For basic analysis (without z-coordinates):
   - Use xgcm grid for interpolation
   - Analyze velocity fields (u_vel, v_vel, w_vel) on staggered grids
   - No additional variables needed

4. For full xroms functionality (z-coordinates, derivatives, etc.):
   - Requires: h (bathymetry), zeta (SSH), Cs_r, Cs_w, hc
   - These may not be available in all plotfiles
   - Consider adding them to the dataset if needed

5. Example analysis with staggered grids:
   # Get velocity on different grids
   u_on_rho = xgrid.interp(ds.u_vel, 'X', boundary='fill')  # interpolate u to rho
   
   # Compute velocity magnitude on rho-grid
   v_on_rho = xgrid.interp(ds.v_vel, 'Y', boundary='fill')  # interpolate v to rho
   speed_on_rho = (u_on_rho**2 + v_on_rho**2)**0.5
""")

# =============================================================================
# Tips and Best Practices
# =============================================================================

print("=== Tips and Best Practices ===")
print("""
1. Staggered Data: The converted dataset properly identifies variables on
   different C-grid positions (rho, u, v, w, psi). This information is
   preserved in the dimension names.

2. Coordinate Attributes: All coordinates have CF-compliant attributes:
   - axis: 'X', 'Y', 'Z' for xgcm compatibility
   - long_name: descriptive names
   - c_grid_axis_shift: indicates stagger position

3. Vertical Coordinates: The dataset adds default s-coordinates ranging
   from -1 (bottom) to 0 (top). If your data has specific s-coordinate
   values, manually update:
   ds['s_rho'].values = your_s_rho_values
   ds['s_w'].values = your_s_w_values

4. Missing ROMS Variables: A warning will be issued if the dataset lacks
   variables needed for full xroms functionality. This is OK for many
   analyses that only need grid positioning information.

5. Performance: The conversion uses shallow copy (deep=False) for
   efficiency with large dask-backed arrays.
""")
