# Copyright 2011-2013, Vinothan N. Manoharan, Thomas G. Dimiduk,
# Rebecca W. Perry, Jerome Fung, and Ryan McGorty, Anna Wang
#
# This file is part of HoloPy.
#
# HoloPy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HoloPy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HoloPy.  If not, see <http://www.gnu.org/licenses/>.
'''
Calculates holograms of spheres using Fortran implementation of Mie
theory. Uses superposition to calculate scattering from multiple
spheres. Uses full radial dependence of spherical Hankel functions for
scattered field.

.. moduleauthor:: Thomas G. Dimiduk <tdimiduk@physics.harvard.edu>
.. moduleauthor:: Jerome Fung <fung@physics.harvard.edu>
.. moduleauthor:: Vinothan N. Manoharan <vnm@seas.harvard.edu>
'''
from __future__ import division
import numpy as np
from ...core.helpers import _ensure_array
from ..errors import TheoryNotCompatibleError, UnrealizableScatterer
from ..scatterer import Sphere, Scatterers
from .scatteringtheory import FortranTheory
from .mie_f import mieangfuncs, miescatlib
from .mie_f.multilayer_sphere_lib import scatcoeffs_multi

#I think that I need copy.copy to make a copy of a Schema, but there probably is a better way
import copy


class Mie(FortranTheory):
    """
    Compute scattering using the Lorenz-Mie solution.

    This theory calculates exact scattering for single spheres and approximate
    results for groups of spheres.  It does not account for multiple scattering,
    hence the approximation in the case of multiple spheres.  Neglecting
    multiple scattering is a good approximation if the particles are
    sufficiently seperated.

    This model can also calculate the exact scattered field from a
    spherically symmetric particle with an arbitrary number of layers
    with differing refractive indices, using Yang's recursive
    algorithm ([Yang2003]_).

    By default, calculates radial component of scattered electric fields,
    which is nonradiative.
    """

    # don't need to define __init__() because we'll use the base class
    # constructor

    def __init__(self, compute_escat_radial = True):
        self.compute_escat_radial = compute_escat_radial
        # call base class constructor
        super(Mie, self).__init__()

    def _calc_scat_matrix(self, scatterer, schema):
        if isinstance(scatterer, Sphere):
            scat_coeffs = self._scat_coeffs(scatterer, schema.optics)

            # TODO: actually use (rather than ignore) the phi
            scat_matrs = [mieangfuncs.asm_mie_far(scat_coeffs, theta) for
                          theta, phi in schema.positions_theta_phi()]
            return np.array(scat_matrs)
        else:
            raise TheoryNotCompatibleError(self, scatterer)

    def _calc_field(self, scatterer, schema):
        """
        Calculate fields for single or multiple spheres

        Parameters
        ----------
        scatterer : :mod:`scatterpy.scatterer` object
            scatterer or list of scatterers to compute field for
        selection : array of integers (optional)
            a mask with 1's in the locations of pixels where you
            want to calculate the field, defaults to all pixels
        Returns
        -------
        field : :class:`.ElectricField`with shape `imshape`
            scattered electric field

        Notes
        -----
        For multiple particles, this code superposes the fields
        calculated from each particle (using calc_mie_fields()).
        """
        if isinstance(scatterer, Sphere):
            scat_coeffs = self._scat_coeffs(scatterer, schema.optics)

            # mieangfuncs.f90 works with everything dimensionless.
            # tranpose to get things in fortran format
            # TODO: move this transposing to a wrapper
            if self.compute_escat_radial:
                fields = mieangfuncs.mie_fields(schema.positions_kr_theta_phi(
                        origin = scatterer.center).T, scat_coeffs,
                                                schema.optics.polarization, 1)
            else:
                fields = mieangfuncs.mie_fields(schema.positions_kr_theta_phi(
                        origin = scatterer.center).T, scat_coeffs,
                                                schema.optics.polarization, 0)
            fields = self._finalize_fields(scatterer.z, fields, schema)
        
        elif isinstance(scatterer, Scatterers):
            spheres = scatterer.get_component_list()

            field = self._calc_field(spheres[0], schema)
            for sphere in spheres[1:]:
                field += self._calc_field(sphere, schema)
            fields = field
        else:
            raise TheoryNotCompatibleError(self, scatterer)
    
        return self._set_internal_fields(fields, scatterer)
        
        
    def _calc_internal_field(self, scatterer, schema):
         """
        Calculate fields for single or multiple spheres

        Parameters
        ----------
        scatterer : :mod:`scatterpy.scatterer` object
            scatterer or list of scatterers to compute field for

        schema :
        
        Returns
        -------
        field : :class:`.ElectricField`with shape `imshape`
            scattered electric field

   
        """
        
        if not isinstance(scatterer, Sphere):
            raise TheoryNotCompatibleError(self, scatterer)
        else:
            scat_coeffs = self._scat_coeffs(scatterer, schema.optics)
            
            center_to_center = scatterer.center - schema.center
            unit_vector = center_to_center - abs(center_to_center).sum()

            if not schema.contains(scatterer.center - unit_vector):
                print 'scatterer not in schema'
                #raise some error since the scatterer is not in the schema
            else:
                origin = schema.origin
                extent = schema.extent
                shape  = schema.shape
                
                spherical_coords = schema.positions_r_theta_phi(
                        origin = scatterer.center)
                
                r,theta,phi = spherical_coords[:,0],spherical_coords[:,1],spherical_coords[:,2]
            
                xo,yo,zo = schema.center
                x = r*np.sin(theta)*np.cos(phi) + xo
                y = r*np.sin(theta)*np.sin(phi) + yo
                z = r*np.cos(theta)             + zo
                
                #ind is a list of the indices of the spherical coords that are within the scatterer
                ind = np.array([scatterer.contains(xyz) for xyz in zip(x,y,z)]).T
                            
                points_in_scatterer = schema.positions_kr_theta_phi(
                        origin = scatterer.center)[ind]
                        
                #######################
                ######This will be replaced with a call to the fortran function to find the internal fields        
                fields = mieangfuncs.mie_fields(points_in_scatterer.T, scat_coeffs,
                                                schema.optics.polarization, 0)
                
                #Hopefully we can switch to this soon:                                
#                 fields = mieangfuncs.mie_internal_fields(points_in_scatterer.T, scat_coeffs,
#                                 schema.optics.polarization, 0)
                ###############
                
                # We create a selection schema to pass to _finalize_fields so that it knows that 
                # we are only interested in the internal fields
                selection_schema = copy.copy(schema)
                selection_schema._selection = np.reshape(ind,(shape))
                                  
            return self._finalize_fields(scatterer.z, fields, selection_schema)
    
    

    def _calc_cross_sections(self, scatterer, optics):
        """
        Calculate scattering, absorption, and extinction cross
        sections, and asymmetry parameter for spherically
        symmetric scatterers.

        Parameters
        ----------
        scatterer : :mod:`scatterpy.scatterer` object
            spherically symmetric scatterer to compute for
            (Calculation would need to be implemented in a radically
            different way, via numerical quadrature, for sphere clusters)

        Returns
        -------
        cross_sections : array (4)
            Dimensional scattering, absorption, and extinction
            cross sections, and <cos \theta>

        Notes
        -----
        The radiation pressure cross section C_pr is given by
        C_pr = C_ext - <cos \theta> C_sca.

        The radiation pressure force on a sphere is

        F = (n_med I_0 C_pr) / c

        where I_0 is the incident intensity.  See van de Hulst, p. 14.
        """
        if isinstance(scatterer, Scatterers):
            raise UnrealizableScatterer(self, scatterer,
                                        "Use Multisphere to calculate " +
                                        "radiometric quantities")
        albl = self._scat_coeffs(scatterer, optics)

        cscat, cext, cback = miescatlib.cross_sections(albl[0], albl[1]) * \
            (2. * np.pi / optics.wavevec**2)

        cabs = cext - cscat # conservation of energy

        asym = 4. * np.pi / (optics.wavevec**2 * cscat) * \
            miescatlib.asymmetry_parameter(albl[0], albl[1])

        return np.array([cscat, cabs, cext, asym])

    def _scat_coeffs(self, s, optics):
        x_arr = optics.wavevec * _ensure_array(s.r)
        m_arr = _ensure_array(s.n) / optics.index

        # Check that the scatterer is in a range we can compute for
        if x_arr.max() > 1e3:
            raise UnrealizableScatterer(self, s, "radius too large, field "+
                                        "calculation would take forever")

        if len(x_arr) == 1 and len(m_arr) == 1:
            # Could just use scatcoeffs_multi here, but jerome is in favor of
            # keeping the simpler single layer code here
            lmax = miescatlib.nstop(x_arr[0])
            return  miescatlib.scatcoeffs(x_arr[0], m_arr[0], lmax)
        else:
            return scatcoeffs_multi(m_arr, x_arr)
