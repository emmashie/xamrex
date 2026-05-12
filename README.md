# REMORA-problems

A collection of problem setups and test cases for REMORA (Regional EMulating Ocean-model Resolution Advancement), an ocean modeling framework built on AMReX.

## Overview

This repository contains configured problem setups for REMORA simulations. Currently includes:

### RiverPlume

A 3D ocean simulation demonstrating river plume dynamics with adaptive mesh refinement (AMR). This problem setup models the interaction between river discharge and coastal ocean dynamics.

**Key Features:**
- **Adaptive Mesh Refinement**: Two-way coupled AMR with refinement ratios of 3:3:1 (x:y:z)
- **Domain**: 80 km × 100 km × 20 m depth
- **Grid Resolution**: 38 × 48 × 32 cells (base level)
- **Turbulence Closure**: GLS (Generic Length Scale) k-ε model
- **River Input**: NetCDF-based river forcing
- **Boundary Conditions**: Mixed (slipwall on west, outflow on south/east/north)
- **Time Integration**: 10-second timestep with 30:1 barotropic splitting

**Physical Parameters:**
- Coriolis forcing (beta-plane approximation)
- Quadratic bottom friction (CD = 3.0×10⁻³)
- Linear equation of state
- Vertical terrain-following coordinates (s-coordinates)

## Repository Structure

```
REMORA-problems/
└── RiverPlume/
    ├── prob.H           # Problem header with class definitions
    ├── prob.cpp         # Problem implementation
    ├── inputs           # Runtime configuration file
    ├── river.nc         # River forcing data (NetCDF)
    ├── GNUmakefile      # Build configuration
    └── Make.package     # Package specification
```

## Prerequisites

- [REMORA](https://github.com/AMReX-Codes/REMORA) - Regional ocean modeling framework
- [AMReX](https://github.com/AMReX-Codes/amrex) - Adaptive mesh refinement library
- C++ compiler with C++17 support
- NetCDF library (for data I/O)
- MPI (for parallel execution)

## Building and Running

1. **Build the problem:**
   ```bash
   cd RiverPlume
   make -j
   ```

2. **Run the simulation:**
   ```bash
   ./REMORA3d.exe inputs
   ```

3. **Output:**
   - Plot files: `ocean_out/plt*` (every 360 timesteps)
   - Checkpoint files: `chk*` (disabled by default)

## Configuration

Key parameters can be modified in the `inputs` file:

- **Grid resolution**: `remora.n_cell`
- **Domain size**: `remora.prob_lo` and `remora.prob_hi`
- **Timestep**: `remora.fixed_dt`
- **AMR settings**: `amr.max_level`, `amr.ref_ratio_vect`
- **Physical parameters**: Coriolis, drag coefficients, mixing parameters
- **Output frequency**: `remora.plot_int`

## Loading 2D Variables (Post-processing)

When opening AMReX plotfiles with `xarray`, include 2D multifab groups via
`auxiliary_multifabs`.

```python
import os
from pathlib import Path
import xarray as xr

plt_root = Path('/Users/nuss851/REMORA-problems/RiverPlume/ocean_out')

# Load base level plus 2D groups
aux_groups = ['rho2d', 'u2d', 'v2d']
ds0 = xr.open_dataset(
   os.path.join(plt_root),
   engine='amrex',
   level=0,
   pattern='plt*',
   auxiliary_multifabs=aux_groups,
)
```

This makes the requested 2D groups available in the returned dataset for
plotting and analysis.

## References

- REMORA Documentation: [https://remora.readthedocs.io](https://remora.readthedocs.io)
- AMReX Documentation: [https://amrex-codes.github.io/amrex](https://amrex-codes.github.io/amrex)

## License

This project is licensed under the MIT License - see below for details.

```
MIT License

Copyright (c) 2025 Robert Hetland

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

