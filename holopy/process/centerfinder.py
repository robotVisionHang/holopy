# Copyright 2011, Vinothan N. Manoharan, Thomas G. Dimiduk, Rebecca W. Perry,
# Jerome Fung, and Ryan McGorty
#
# This file is part of Holopy.
#
# Holopy is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Holopy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Holopy.  If not, see <http://www.gnu.org/licenses/>.
"""
The centerfinder module is a group of functions for locating the
center of a particle or dimer in a hologram. This can be useful for
determining an initial parameter guess for hologram fitting.

.. moduleauthor:: Rebecca W. Perry <rperry@seas.harvard.edu>
.. moduleauthor:: Jerome Fung <fung@physics.harvard.edu>
"""

import scipy
import numpy
import scipy.ndimage
from scipy import arange, around, array, int16, zeros, sqrt

def center_find(image,scale=.5):
    """
    Finds the coordinates of the center of a holographic pattern
    The coordinates returned are in pixels (row number, column number).

    Intended for fiding the center of single particle or dimer
    holograms which basically show concentric circles. The optional
    scale parameter (between 0 and 1) gives a lower threshold of image
    intensity gradient relative to the maximum gradient (1) to take
    into account when finding the center. 

    Parameters
    ----------
    image : ndarray
        image to find the center of
    
    scale : float (optional)
        gradient magnitude threshold

    Notes
    -----
    When scale is close to 1, the code will run quickly but may lack
    accuracy. When scale is set to 0, the gradient at all pixels will
    contribute to finding the center and the code will take a little
    bit longer. The user should pay attention to how the magnitude of
    the gradients correlates with finding an accurate center.
    """
    x_deriv,y_deriv = image_gradient(image)
    res,acc = hough(x_deriv,y_deriv,scale)
    return res


def image_gradient(image):
    """ 
    Uses the sobel operator as a numerical approximation of a
    derivative to find the x and y components of the image's intensity
    gradient at each pixel.

    Parameters
    ----------
    image : ndarray
        image to find the gradient of
    """
    gradx = scipy.ndimage.sobel(image, axis = 0)
    grady = -1*scipy.ndimage.sobel(image, axis=1)
    return gradx, grady


def hough(x_deriv, y_deriv,scale=.5):
    """
    Following the approach of a Hough transform, finds the pixel which
    the most gradients point towards or away from. Uses only gradients
    with magnitude greater than scale*maximum gradient. Once the pixel
    is found, uses a brightness-weighted average around that pixel to
    refine the center location to return.

    Parameters
    ----------
    x_deriv : numpy.ndarray
        x-component of image intensity gradient

    y_deriv : numpy.ndarray
        y-component of image intesity gradient
    
    scale : float (optional)
        gradient magnitude threshold

    """
    #Finding the center: Using the derivatives we have already found
    #(effectively the gradient), we "draw" lines through pixels
    #parallel to the gradient and add all these lines together in the
    #array called "accumulator."  Because of the
    #concentric-circle-patterned hologram, the maximum of accumulator
    #should be the center of the pattern.  Rebecca W. Perry, Jerome Fung
    #11/20/2009
    
    #Edited by Rebecca Dec. 1, 2009 to include weighted average

    accumulator = zeros(x_deriv.shape)
    dim = x_deriv.shape[0]
    gradient_mag = sqrt(x_deriv**2 + y_deriv**2)
    threshold = scale*gradient_mag.max()
    
    points_to_vote = scipy.where(gradient_mag > threshold)
    points_to_vote = array([points_to_vote[0], points_to_vote[1]]).transpose()

    for coords in points_to_vote:
        # draw a line
        # add it to the accumulator
        slope = y_deriv[coords[0], coords[1]]/x_deriv[coords[0], coords[1]]
	if abs(slope) > 1.:
            line = around(coords[1] - slope*(arange(dim) - coords[0]))
	    acc_cols = int16(line[(array(line >= 0) * array(line < dim))])
            acc_rows = arange(dim, dtype='int16')[(array(line >= 0) * 
                                                   array(line < dim))]
        else:
            line = around(coords[0] - 1/slope * (arange(dim) - coords[1]))
            acc_cols = arange(dim, dtype = 'int16')[(array(line >= 0) * 
                                                     array(line < dim))]
            acc_rows = int16(line[(array(line >= 0) * array(line < dim))])
        
        accumulator[acc_rows, acc_cols] = accumulator[acc_rows, acc_cols] + 1
    #m is row number, n is column number
    [m,n]=scipy.unravel_index(accumulator.argmax(), accumulator.shape) 
    #brightness average around brightest pixel:
    small_sq=accumulator[m-10:m+11,n-10:n+11] 
    #the part of the accumulator to average over
    rowNum,colNum=numpy.mgrid[m-10:m+11,n-10:n+11]
    #row and column of the revised center:
    weightedRowNum=scipy.average(rowNum,None,small_sq)
    weightedColNum=scipy.average(colNum,None,small_sq)
    return array([weightedRowNum, weightedColNum]), accumulator