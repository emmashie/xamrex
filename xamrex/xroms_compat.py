"""
xroms compatibility conversion for AMReX/REMORA datasets.

Converts xamrex-loaded datasets to xroms format for use with xroms functions.
"""
import warnings
from pathlib import Path
import numpy as np
import xarray as xr


def to_xroms_format(ds, create_grid=False, vtransform=2, add_z_coords=False, grid_file=None, strict_grid=False):
    """
    Convert AMReX/REMORA dataset to xroms-compatible format.
    
    Renames coordinates and dimensions to match ROMS conventions:
    - x → xi_rho, x_u → xi_u, x_psi → xi_psi
    - y → eta_rho, y_v → eta_v, y_psi → eta_psi
    - z → s_rho, z_w → s_w
    
    Adds xgcm-compatible attributes for grid setup.
    
    Parameters
    ----------
    ds : xr.Dataset
        Dataset loaded from AMReX plotfile via xamrex
    create_grid : bool, optional
        If True, create and attach an xgcm.Grid object (requires xgcm).
        Default: False
    vtransform : int, optional
        ROMS vertical transform: 1 = old, 2 = new (default; Shchepetkin & McWilliams).
        Only used if the dataset doesn't already have this attribute.
        Default: 2
    add_z_coords : bool, optional
        If True, attempt to compute z-coordinates from s_rho (requires bathymetry h
        and sea_surface_height zeta). For AMReX/REMORA data which typically doesn't
        have these, set to False. Default: False
    grid_file : str, Path, or xr.Dataset, optional
        Optional ROMS/REMORA grid or metadata dataset to source missing variables
        required by xroms (e.g., hc, Cs_r, Cs_w, h, pm, pn). Existing variables
        in ds are not overwritten.
    strict_grid : bool, optional
        If True and grid_file is provided, raise ValueError when any candidate
        grid variable/coordinate cannot be conformed to dataset dimensions.
        Default: False
        
    Returns
    -------
    ds_roms : xr.Dataset
        Dataset with ROMS-style coordinates and dimensions
    xgrid : xgcm.Grid or None
        If create_grid=True, returns xgcm Grid object; otherwise None
    """
    ds_roms = ds.copy(deep=False)
    
    # Mapping from AMReX coordinate names to ROMS names
    # Maps based on stagger position
    coord_renames = {
        # X-direction
        'x': 'xi_rho',       # cell centers
        'x_u': 'xi_u',       # u-points (face centers in x)
        'x_psi': 'xi_psi',   # corner points
        
        # Y-direction  
        'y': 'eta_rho',      # cell centers
        'y_v': 'eta_v',      # v-points (face centers in y)
        'y_psi': 'eta_psi',  # corner points
        
        # Z-direction
        'z': 's_rho',        # rho-points (cell centers)
        'z_w': 's_w',        # w-points (face centers in z)
    }
    
    # Rename coordinates
    rename_dict = {old: new for old, new in coord_renames.items() if old in ds_roms.coords}
    if rename_dict:
        ds_roms = ds_roms.rename(rename_dict)
    
    # Also rename dimensions if they exist
    dim_renames = {}
    for old_name, new_name in coord_renames.items():
        if old_name in ds_roms.dims:
            dim_renames[old_name] = new_name
    if dim_renames:
        ds_roms = ds_roms.rename(dim_renames)

    # AMReX face-centered sizes are often +1 relative to rho dimensions.
    # xroms/ROMS expects interior C-grid staggering (u/v/psi are typically -1).
    ds_roms = _trim_staggered_dims_to_roms(ds_roms)
    
    # Add CF attributes for coordinates
    _add_cf_attributes(ds_roms)

    # Merge missing ROMS metadata/coordinates from external grid file if provided.
    if grid_file is not None:
        ds_roms = _merge_grid_file_metadata(ds_roms, grid_file, strict_grid=strict_grid)
    
    # Add ROMS vertical parameters needed by xroms
    _add_vertical_params(ds_roms, vtransform=vtransform)

    # Add ROMS-standard aliases for common velocity variable names.
    _add_roms_variable_aliases(ds_roms)

    # Ensure chunk metadata includes all dims used by staggered variables.
    # This avoids xgcm KeyError on dims like xi_u/eta_v when using dask-backed data.
    ds_roms = _normalize_chunk_metadata(ds_roms)
    
    # Create grid object if requested
    xgrid = None
    if create_grid:
        try:
            import xgcm
            xgrid = _create_xgcm_grid(ds_roms)
        except ImportError:
            warnings.warn("xgcm not installed; cannot create grid object. "
                         "Install with: pip install xgcm")
    
    if create_grid:
        return ds_roms, xgrid
    else:
        return ds_roms


def _add_cf_attributes(ds):
    """Add CF-compliant and xgcm-compatible attributes to coordinates."""
    
    cf_attrs = {
        # X-direction coordinates
        'xi_rho': {
            'axis': 'X',
            'long_name': 'xi-coordinate on RHO-points',
            'units': 'm',
            'c_grid_axis_shift': 0.0,
        },
        'xi_u': {
            'axis': 'X',
            'long_name': 'xi-coordinate on U-points',
            'units': 'm',
            'c_grid_axis_shift': -0.5,
        },
        'xi_psi': {
            'axis': 'X',
            'long_name': 'xi-coordinate on PSI-points',
            'units': 'm',
            'c_grid_axis_shift': -0.5,
        },
        
        # Y-direction coordinates
        'eta_rho': {
            'axis': 'Y',
            'long_name': 'eta-coordinate on RHO-points',
            'units': 'm',
            'c_grid_axis_shift': 0.0,
        },
        'eta_v': {
            'axis': 'Y',
            'long_name': 'eta-coordinate on V-points',
            'units': 'm',
            'c_grid_axis_shift': -0.5,
        },
        'eta_psi': {
            'axis': 'Y',
            'long_name': 'eta-coordinate on PSI-points',
            'units': 'm',
            'c_grid_axis_shift': -0.5,
        },
        
        # Z-direction coordinates
        's_rho': {
            'axis': 'Z',
            'long_name': 's-coordinate on RHO-points (0 < s < -1)',
            'units': 'nondimensional',
            'valid_min': -1.0,
            'valid_max': 0.0,
            'c_grid_axis_shift': 0.0,
        },
        's_w': {
            'axis': 'Z',
            'long_name': 's-coordinate on W-points (0 < s < -1)',
            'units': 'nondimensional',
            'valid_min': -1.0,
            'valid_max': 0.0,
            'c_grid_axis_shift': -0.5,
        },
    }
    
    for coord_name, attrs in cf_attrs.items():
        if coord_name in ds.coords:
            ds.coords[coord_name].attrs.update(attrs)


def _add_vertical_params(ds, vtransform=2):
    """
    Add ROMS vertical coordinate parameters needed by xroms.
    
    These are dataset attributes that xroms uses to understand vertical coordinates.
    """
    # Add Vtransform if not already present
    if 'Vtransform' not in ds.attrs:
        ds.attrs['Vtransform'] = vtransform
    
    # Add default stretching parameters if not present
    # These are standard ROMS defaults
    if 'Vstretching' not in ds.attrs:
        ds.attrs['Vstretching'] = 4  # Default stretching type
    
    def _needs_sigma_rebuild(vals):
        """Return True when vertical coordinate values are not ROMS sigma-like."""
        vals = np.asarray(vals)
        if vals.size == 0:
            return True
        finite = np.isfinite(vals)
        if not np.all(finite):
            return True
        # ROMS sigma coordinates should live near [-1, 0].
        # AMReX plotfile physical z-coordinates (e.g. -5000..0 m) must be rebuilt.
        vmin = float(vals.min())
        vmax = float(vals.max())
        if vmin < -1.5 or vmax > 0.5:
            return True
        return False

    # Check if s_rho coordinate exists and generate sigma values if needed
    if 's_rho' in ds.coords:
        ns_rho = len(ds.s_rho)
        s_rho_vals = ds.s_rho.values
        if np.all(s_rho_vals == np.arange(len(s_rho_vals))) or _needs_sigma_rebuild(s_rho_vals):
            # ROMS convention is bottom-to-surface ordering: approximately -1 -> 0
            new_s_rho = -1.0 + (np.arange(ns_rho) + 0.5) / ns_rho
            ds.coords['s_rho'] = new_s_rho
    
    # Check if s_w coordinate exists and generate sigma values if needed
    if 's_w' in ds.coords:
        ns_w = len(ds.s_w)
        s_w_vals = ds.s_w.values
        if np.all(s_w_vals == np.arange(len(s_w_vals))) or _needs_sigma_rebuild(s_w_vals):
            # ROMS convention is bottom-to-surface ordering: -1 -> 0
            new_s_w = -1.0 + np.arange(ns_w) / (ns_w - 1)
            ds.coords['s_w'] = new_s_w
    
    # Add notice about missing variables needed for full xroms functionality
    missing_roms_vars = []
    for required_var in ['h', 'zeta', 'Cs_r', 'Cs_w', 'hc']:
        if required_var not in ds.data_vars and required_var not in ds.coords:
            missing_roms_vars.append(required_var)
    
    if missing_roms_vars:
        warnings.warn(
            f"Dataset missing ROMS variables: {', '.join(missing_roms_vars)}. "
            f"Some xroms functionality (e.g., z-coordinate computation) may be limited. "
            f"These are optional for basic grid operations."
        )


def _add_roms_variable_aliases(ds):
    """Add ROMS-standard variable aliases expected by xroms workflows."""
    alias_candidates = {
        'u': ('u', 'u_vel', 'uvel', 'u_velocity', 'x_velocity'),
        'v': ('v', 'v_vel', 'vvel', 'v_velocity', 'y_velocity'),
        'w': ('w', 'w_vel', 'wvel', 'w_velocity', 'z_velocity'),
    }

    for alias, candidates in alias_candidates.items():
        if alias in ds.data_vars:
            continue
        for name in candidates:
            if name in ds.data_vars:
                ds[alias] = ds[name]
                break


def _normalize_chunk_metadata(ds):
    """Ensure all dataset dimensions appear in chunk metadata when dask-backed."""
    try:
        chunk_map = ds.chunks
    except Exception:
        return ds

    if chunk_map is None:
        return ds

    missing = [dim for dim in ds.dims if dim not in chunk_map]
    if not missing:
        return ds

    return ds.chunk({dim: -1 for dim in missing})


def _trim_staggered_dims_to_roms(ds):
    """Trim AMReX staggered dimensions to ROMS interior C-grid conventions."""
    trim_map = {
        'xi_u': 'xi_rho',
        'eta_v': 'eta_rho',
        'xi_psi': 'xi_rho',
        'eta_psi': 'eta_rho',
    }

    for stag_dim, rho_dim in trim_map.items():
        if stag_dim not in ds.dims or rho_dim not in ds.dims:
            continue

        stag_n = int(ds.sizes[stag_dim])
        rho_n = int(ds.sizes[rho_dim])

        # Convert AMReX face-count (rho+1) to ROMS interior count (rho-1)
        # by dropping one boundary element on each side.
        if stag_n == rho_n + 1 and stag_n >= 3:
            ds = ds.isel({stag_dim: slice(1, -1)})

    return ds


def _merge_grid_file_metadata(ds, grid_file, strict_grid=False):
    """
    Merge missing ROMS metadata/variables from a grid file or Dataset.

    Parameters
    ----------
    ds : xr.Dataset
        xroms-formatted dataset to augment.
    grid_file : str, Path, or xr.Dataset
        Source containing ROMS metadata variables.

    Returns
    -------
    xr.Dataset
        Augmented dataset.
    """
    if isinstance(grid_file, xr.Dataset):
        grid_ds = grid_file
    elif isinstance(grid_file, (str, Path)):
        grid_ds = xr.open_dataset(grid_file)
    else:
        raise TypeError(
            "grid_file must be a path-like string or xarray.Dataset"
        )

    # Common ROMS variables/coordinates used by xroms metric and vertical logic.
    # Only copy if missing in target dataset to avoid clobbering AMReX-derived data.
    candidate_names = [
        'h', 'hc', 'Cs_r', 'Cs_w',
        'pm', 'pn', 'f', 'angle',
        'mask_rho', 'mask_u', 'mask_v', 'mask_psi',
        'lon_rho', 'lat_rho', 'lon_u', 'lat_u',
        'lon_v', 'lat_v', 'lon_psi', 'lat_psi',
        's_rho', 's_w',
    ]

    def _upsample_dim_nearest(var, dim, factor):
        """Repeat values along a dimension by integer factor."""
        if factor <= 1:
            return var
        idx = xr.DataArray(np.repeat(np.arange(int(var.sizes[dim])), factor), dims=(dim,))
        return var.isel({dim: idx})

    def _trim_center_dim(var, dim, new_size):
        """Center-trim a dimension to a requested size."""
        src_n = int(var.sizes[dim])
        if new_size >= src_n:
            return var
        delta = src_n - int(new_size)
        left = delta // 2
        right = delta - left
        return var.isel({dim: slice(left, src_n - right)})

    def _conform_1d(var, dim, tgt_n):
        """
        Conform one dimension to target size using crop/upsample.

        Strategy:
        1) exact match
        2) center-crop if source is larger
        3) integer upsample if source is smaller
        4) if needed, trim one cell at each edge (ROMS interior) then upsample
        """
        src_n = int(var.sizes[dim])
        tgt_n = int(tgt_n)

        if src_n == tgt_n:
            return var

        if src_n > tgt_n:
            return _trim_center_dim(var, dim, tgt_n)

        # src_n < tgt_n
        if tgt_n % src_n == 0:
            return _upsample_dim_nearest(var, dim, tgt_n // src_n)

        # Common case for AMR-vs-grid mismatch: drop one edge cell each side,
        # then upscale interior to refined level.
        if src_n > 2:
            interior_n = src_n - 2
            if tgt_n % interior_n == 0:
                trimmed = var.isel({dim: slice(1, -1)})
                return _upsample_dim_nearest(trimmed, dim, tgt_n // interior_n)

        return None

    def _conform_to_target(var):
        """Return var cropped to target ds dims where possible; else None."""
        if len(var.dims) == 0:
            return var

        out = var
        for dim in out.dims:
            if dim not in ds.dims:
                return None

            conformed = _conform_1d(out, dim, int(ds.sizes[dim]))
            if conformed is None:
                return None
            out = conformed

        for dim in out.dims:
            if int(out.sizes[dim]) != int(ds.sizes[dim]):
                return None

        # Drop attached coordinate indexes so assignment aligns by dimension only.
        return xr.DataArray(
            out.data,
            dims=out.dims,
            attrs=out.attrs,
            name=out.name,
        )

    skipped = []

    for name in candidate_names:
        if name in ds:
            continue
        if name in grid_ds:
            conformed = _conform_to_target(grid_ds[name])
            if conformed is not None:
                ds[name] = conformed
            else:
                msg = (
                    f"Skipping grid variable '{name}' due to incompatible dimensions: "
                    f"source={dict(grid_ds[name].sizes)}, target={dict(ds.sizes)}"
                )
                skipped.append(msg)
                warnings.warn(msg)
            continue
        if name in ds.coords:
            continue
        if name in grid_ds.coords:
            conformed = _conform_to_target(grid_ds.coords[name])
            if conformed is not None:
                ds = ds.assign_coords({name: conformed})
            else:
                msg = (
                    f"Skipping grid coordinate '{name}' due to incompatible dimensions: "
                    f"source={dict(grid_ds.coords[name].sizes)}, target={dict(ds.sizes)}"
                )
                skipped.append(msg)
                warnings.warn(msg)

    if strict_grid and skipped:
        max_lines = 12
        details = "\n".join(skipped[:max_lines])
        extra = ""
        if len(skipped) > max_lines:
            extra = f"\n... and {len(skipped) - max_lines} more"
        raise ValueError(
            "xroms strict grid mode failed: one or more grid-file fields could not be "
            "conformed to dataset dimensions.\n"
            f"{details}{extra}"
        )

    # Populate key ROMS attrs if missing and available as attrs or scalar vars.
    for attr_name in ('Vtransform', 'Vstretching'):
        if attr_name in ds.attrs:
            continue
        if attr_name in grid_ds.attrs:
            ds.attrs[attr_name] = grid_ds.attrs[attr_name]
            continue
        if attr_name in grid_ds:
            val = grid_ds[attr_name].values
            if np.ndim(val) == 0:
                ds.attrs[attr_name] = val.item()

    # xroms expects hc as a dataset variable (ds.hc), not only as a global attr.
    # Some grid files store hc in attrs, so promote it when missing.
    if 'hc' not in ds and 'hc' in grid_ds.attrs:
        ds['hc'] = xr.DataArray(
            np.array(grid_ds.attrs['hc']),
            attrs={'long_name': 'S-coordinate parameter, critical depth', 'units': 'meter'},
        )

    return ds


def _create_xgcm_grid(ds):
    """Create xgcm Grid object for ROMS dataset."""
    import xgcm
    
    # Determine which coordinates are available
    coords_dict = {}
    
    # X-direction
    if 'xi_rho' in ds.coords:
        x_dict = {'center': 'xi_rho'}
        if 'xi_u' in ds.coords:
            x_dict['inner'] = 'xi_u'
        if 'xi_psi' in ds.coords:
            x_dict['right'] = 'xi_psi'  # Alternative: corner point
        coords_dict['X'] = x_dict
    
    # Y-direction
    if 'eta_rho' in ds.coords:
        y_dict = {'center': 'eta_rho'}
        if 'eta_v' in ds.coords:
            y_dict['inner'] = 'eta_v'
        if 'eta_psi' in ds.coords:
            y_dict['right'] = 'eta_psi'  # Alternative: corner point
        coords_dict['Y'] = y_dict
    
    # Z-direction (if present)
    if 's_rho' in ds.coords:
        z_dict = {'center': 's_rho'}
        if 's_w' in ds.coords:
            z_dict['outer'] = 's_w'
        coords_dict['Z'] = z_dict
    
    # Create Grid object
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xgrid = xgcm.Grid(ds, coords=coords_dict, periodic=[])
    
    return xgrid
