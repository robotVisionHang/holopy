# Copyright 2011-2016, Vinothan N. Manoharan, Thomas G. Dimiduk,
# Rebecca W. Perry, Jerome Fung, Ryan McGorty, Anna Wang, Solomon Barkley
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

import warnings
import unittest
import tempfile

import numpy as np
from numpy.testing import assert_allclose, assert_raises, assert_equal

from holopy.core.metadata import data_grid, clean_concat, illumination as illum
from holopy.core.io.vis import display_image, show
from holopy.core.io.io import get_example_data
from holopy.core.tests.common import assert_obj_close
from holopy.core.errors import BadImage


# Creating some d-dimensional arrays for testing visualization:
ARRAY_2D = np.arange(20).reshape(5, 4)
ARRAY_3D = np.arange(60).reshape(3, 5, 4)
ARRAY_4D = np.transpose(
    [ARRAY_3D, ARRAY_3D + 0.5, 0 * ARRAY_3D],
    axes=(1, 2, 3, 0))
ARRAY_5D = np.reshape(ARRAY_4D, ARRAY_4D.shape + (1,))


with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    import matplotlib.pyplot as plt
plt.ioff()


def convert_ndarray_to_xarray(array, extra_dims=None):
    if array.ndim > 2:
        z = range(len(array))
    else:
        z = 0
    array = data_grid(array, spacing=1, z=z, extra_dims=extra_dims)
    array.attrs['_image_scaling'] = None
    return array


class TestDisplayImage(unittest.TestCase):
    def test_basics(self):
        # test simplest cases
        basic = convert_ndarray_to_xarray(ARRAY_3D)
        assert_obj_close(display_image(basic, scaling=None), basic)
        assert_obj_close(display_image(basic.transpose(), scaling=None), basic)

        # test complex values
        cplx = basic.copy()+0j
        cplx[0, 0, :] = cplx[0, 0, :] / np.sqrt(2) * (1 + 1j)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            assert_obj_close(display_image(cplx, scaling=None), basic)

        # test custom dim names
        dims = basic.assign_coords(
            dim1=basic['x'], dim2=basic['y'], dim3=basic['z'])
        dims = dims.swap_dims({'x': 'dim1', 'y': 'dim2', 'z': 'dim3'})
        dims = display_image(dims, vert_axis='dim1', horiz_axis='dim2',
                             depth_axis='dim3', scaling=None)
        assert_allclose(dims.values, basic.values)
        t5 = ARRAY_5D.transpose([4, 1, 2, 0, 3])
        t5 = convert_ndarray_to_xarray(
            t5, extra_dims={"t": [0, 1, 2], illum: [0, 1, 2]})
        t5 = display_image(t5, depth_axis='t', scaling=None)
        xr4 = convert_ndarray_to_xarray(
            ARRAY_4D, extra_dims={illum: [0, 1, 2]})
        assert_obj_close(t5.values, xr4.values)

    def test_np_arrays(self):
        # test interpret axes
        xr2 = convert_ndarray_to_xarray(ARRAY_2D)
        assert_obj_close(display_image(ARRAY_2D, scaling=None), xr2)
        xr3 = convert_ndarray_to_xarray(ARRAY_3D)
        assert_obj_close(display_image(ARRAY_3D, scaling=None), xr3)
        transposed3 = np.transpose(ARRAY_3D, [1, 0, 2])
        assert_obj_close(display_image(transposed3, scaling=None), xr3)

        # test specify axes
        xr3trans = convert_ndarray_to_xarray(transposed3)
        assert_obj_close(
            display_image(ARRAY_3D, depth_axis=1, scaling=None), xr3trans)
        assert_obj_close(
            display_image(ARRAY_3D, vert_axis=0, horiz_axis=2, scaling=None),
            xr3trans)

    def test_excess_dims(self):
        assert_raises(BadImage, display_image, ARRAY_2D[0])
        assert_raises(BadImage, display_image, ARRAY_4D)
        xr4 = convert_ndarray_to_xarray(ARRAY_4D, extra_dims={'t': [0, 1, 2]})
        assert_raises(BadImage, display_image, xr4)
        xr5 = convert_ndarray_to_xarray(
            np.array(ARRAY_5D), extra_dims={illum: [0, 1, 2], 't': [0]})
        assert_raises(BadImage, display_image, xr5)
        col1 = convert_ndarray_to_xarray(
            ARRAY_4D, extra_dims={illum: [0, 1, 2]})
        col2 = convert_ndarray_to_xarray(
            ARRAY_4D, extra_dims={illum: [3, 4, 5]})
        xr6cols = clean_concat([col1, col2], dim=illum)
        assert_raises(BadImage, display_image, xr6cols)

    def test_scaling(self):
        # test scaling exceeds intensity bounds
        my_scale = (-5, 100)
        xr3 = (convert_ndarray_to_xarray(ARRAY_3D)+5)/105
        disp = display_image(ARRAY_3D, scaling=my_scale)
        assert_allclose(disp.values, xr3.values)
        assert_equal(disp.attrs['_image_scaling'], my_scale)

        # test scaling constricts intensity bounds
        wide3 = ARRAY_3D.copy()
        wide3[0, 0, 0] = -5
        wide3[-1, -1, -1] = 100
        xr3 = convert_ndarray_to_xarray(ARRAY_3D)/59
        assert_equal(display_image(wide3).attrs['_image_scaling'], my_scale)
        assert_obj_close(display_image(wide3, (0, 59)).values, xr3.values)

    def test_colours(self):
        # test flat colour dim
        xr3 = convert_ndarray_to_xarray(
            ARRAY_4D[:, :, :, 0:1], extra_dims={illum: [0]})
        assert_obj_close(display_image(xr3), display_image(ARRAY_3D))

        # test colour name formats
        base = convert_ndarray_to_xarray(
            ARRAY_4D, extra_dims={illum: ['red', 'green', 'blue']})
        cols = [['Red', 'Green', 'Blue'],
                ['r', 'g', 'b'],
                [0, 1, 2],
                ['a', 's', 'd']]
        for collist in cols:
            xr4 = convert_ndarray_to_xarray(
                ARRAY_4D, extra_dims={illum: collist})
            assert_obj_close(display_image(xr4, scaling=None), base)

        # test colours in wrong order
        xr4 = convert_ndarray_to_xarray(
            ARRAY_4D[:, :, :, [0, 2, 1]],
            extra_dims={illum: ['red', 'blue', 'green']})
        assert_allclose(display_image(xr4, scaling=None).values, base.values)

        # test missing colours
        slices = [[0, 2, 1], [1, 0], [0, 1], [0, 1]]
        possible_valid_colors = [
            ['red', 'blue', 'green'],
            ['green', 'red'],
            [0, 1],
            ['x-pol', 'y-pol']]
        dummy_channel = [None, 2, -1, -1]
        for i, c, d in zip(slices, possible_valid_colors, dummy_channel):
            xr4 = convert_ndarray_to_xarray(
                ARRAY_4D[:, :, :, i], extra_dims={illum: c})
            xr4 = display_image(xr4, scaling=None)
            if d is not None:
                assert_equal(xr4.attrs['_dummy_channel'], d)
                del xr4.attrs['_dummy_channel']
            assert_obj_close(xr4, base)


def test_show():
    d = get_example_data('image0001')
    try:
        show(d)
    except RuntimeError:
        # this occurs on travis since there is no display
        raise SkipTest()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', (DeprecationWarning, UserWarning))
        plt.savefig(tempfile.TemporaryFile(suffix='.pdf'))
