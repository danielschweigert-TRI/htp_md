"""
Module for methods to compute properties for the polymer electrolytes.
"""
import numpy as np

from htpmd.shared.utils import check_params
from htpmd.constants import ATOM_MASSES
from pymatgen.core.structure import Structure


def compute_diffusivity(trajectory, **params):
    """
    Description:
        Diffusivity of a specified atom type (unit: cm^2/s).

        Example:
        `li_diffusivity = compute_diffusivity(trajectory, **{'target_type': 90})`
        or
        `li_diffusivity = compute_diffusivity(trajectory, target_type=90)`

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:
                                                            target_type (int)

    Returns:
        float:                                          diffusivity (for given target_type)

    """
    required_parameters = ('target_type', )
    check_params(required_parameters, params)

    target_idx = np.nonzero(trajectory.raw_types == params['target_type'])[0]
    target_coords = trajectory.unwrapped_coords[:, target_idx]
    msd = np.mean(np.sum((target_coords[-1] - target_coords[0])**2, axis=-1))
    diffusivity = msd / (len(target_coords) - 1) / 6 * 5e-5  # cm^2/s
    return diffusivity


def compute_polymer_diffusivity(trajectory, **params):
    """
    Description:
        Diffusivity of the polymer, defined by the average diffusivity of
        N, O, S atoms in the polymer chain.

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:

    Returns:
        float:                                          diffusivity (for polymer)

    """
    required_parameters = tuple()
    check_params(required_parameters, params)

    # TODO: should F be included?
    solvate_types = (
        (trajectory.atom_types == 7) | (trajectory.atom_types == 8) |
         (trajectory.atom_types == 16))
    poly_solvate_types = (trajectory.raw_types < 90) & solvate_types
    poly_solvate_idx = np.nonzero(poly_solvate_types)[0]
    target_coords = trajectory.unwrapped_coords[:, poly_solvate_idx]
    msd = np.mean(np.sum((target_coords[-1] - target_coords[0])**2, axis=-1))
    return msd / (len(target_coords) - 1) / 6 * 5e-5  # cm^2/s


def compute_molarity(trajectory, **params):
    """
    Description:
        Molarity of the polymer/salt mixture (unit: mol Li / kg polymer).

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:

    Returns:
        float:                                          molarity

    """
    required_parameters = tuple()
    check_params(required_parameters, params)

    poly_idx = np.nonzero(trajectory.raw_types < 89)[0]
    li_idx = np.nonzero(trajectory.atom_types == 3)[0]

    atom_masses = np.array(ATOM_MASSES)

    poly_mass = np.sum(atom_masses[trajectory.atom_types[poly_idx]])

    return float(len(li_idx)) / poly_mass * 1e3


def compute_conductivity(trajectory, **params):
    """
    Description:
        Compute the conductivity using the cluster-Nernst-Einstein described
        in the following paper (unit: S/cm).

        France-Lanord and Grossman. "Correlations from ion pairing and the
        Nernst-Einstein equation." Physical review letters 122.13 (2019): 136001.

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:
                                                            pop_mat: np.array

    Returns:
        float:                                          conductivity

    """
    required_parameters = ('pop_mat', )
    check_params(required_parameters, params)

    max_cluster = 10
    e_const = 1.6021766209e-19
    kb_const = 1.38064852e-23
    T = 353.0
    pop_mat = params['pop_mat']

    li_diff = compute_diffusivity(trajectory, target_type=90)  # cm^2/s
    tfsi_diff = compute_diffusivity(trajectory, target_type=93)  # cm^2/s

    assert np.isclose(trajectory.lattices[0:1], trajectory.lattices).all()

    V = np.prod(trajectory.lattices[0]) * 1e-24  # cm^3

    cond = 0.
    total_ion = 0.

    for i in range(max_cluster):
        for j in range(max_cluster):
            if i > j:
                cond += e_const**2 / V / kb_const / T * \
                    (i - j)**2 * pop_mat[i, j] * li_diff
            elif i < j:
                cond += e_const**2 / V / kb_const / T * \
                    (i - j)**2 * pop_mat[i, j] * tfsi_diff
            else:
                pass
            total_ion += (i + j) * pop_mat[i, j]

    return cond  # S/cm


def compute_msd_curve(trajectory, **params):
    """
    Description:
        Computes Mean Squared Dispacement curve (unit: ns, A^2)

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:
                                                            target_type (int)

    Returns:
        ts:                                              time series (np.array)
        msds:                                            mean squared displacement (np.array)
    """

    required_parameters = ('target_type', )
    check_params(required_parameters, params)

    target_idx = np.nonzero(trajectory.raw_types == params['target_type'])[0]
    target_coords = trajectory.unwrapped_coords[:, target_idx]

    ts = np.linspace(1, target_coords.shape[0] - 1, 100, dtype=int)
    msds = np.array([
        np.mean(np.sum((target_coords[t:] - target_coords[:-t])**2, axis=-1))
        for t in ts])
    # Convert to ns
    ts = ts * 2e-3
    return ts, msds


def get_cif_at_frame(trajectory, **params):
    """
    Description:
        Computes the cif text representation of the structure at frame k.

    Version: 1.0.0

    Author:
        Name:                                           Tian Xie
        Affiliation:                                    MIT
        Email:                                          <optional>

    Args:
        trajectory (trajectory.base.Trajectory):        trajectory to compute metric on
        **params:                                       Methodology specific parameters.
                                                        Required fields:
                                                            k (int)

    Returns:

    """
    required_parameters = ('k', )
    check_params(required_parameters, params)

    structure = Structure(
        lattice=np.diag(trajectory.lattices[params['k']]),
        species=trajectory.atom_types,
        coords=trajectory.wrapped_coords[params['k']],
        coords_are_cartesian=True,
        to_unit_cell=True
    )
    return structure.to('cif')
