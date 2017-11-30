# This file is part of OpenDrift.
#
# OpenDrift is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2
#
# OpenDrift is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenDrift.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Knut-Frode Dagestad, MET Norway

import logging

import numpy as np
from netCDF4 import Dataset, MFDataset, num2date

from basereader import BaseReader


class Reader(BaseReader):

    def __init__(self, filename=None, name=None):

        if filename is None:
            raise ValueError('Need filename as argument to constructor')

        filestr = str(filename)
        if name is None:
            self.name = filestr
        else:
            self.name = name

        try:
            # Open file, check that everything is ok
            logging.info('Opening dataset: ' + filestr)
            if ('*' in filestr) or ('?' in filestr) or ('[' in filestr):
                logging.info('Opening files with MFDataset')
                self.Dataset = MFDataset(filename)
            else:
                logging.info('Opening file with Dataset')
                self.Dataset = Dataset(filename, 'r')
        except Exception as e:
            raise ValueError(e)

        logging.debug('Finding map projection.')
        # Find projection (variable which as proj4 string)
        for var_name in self.Dataset.variables:
            var = self.Dataset.variables[var_name]
            for att in var.ncattrs():
                if 'proj4' in att:
                    self.proj4 = str(var.__getattr__(att))
                    grid_mapping = var_name
        if not hasattr(self, 'proj4'):
            self.proj4 = '+proj=longlat'  # Assuming lonlat
            #raise ValueError('Did not find any proj4 string in dataset')

        logging.debug('Finding coordinate variables.')
        # Find x, y and z coordinates
        for var_name in self.Dataset.variables:
            var = self.Dataset.variables[var_name]
            if var.ndim > 1:
                continue  # Coordinates must be 1D-array
            attributes = var.ncattrs()
            standard_name = ''
            long_name = ''
            axis = ''
            units = ''
            CoordinateAxisType = ''
            if 'standard_name' in attributes:
                standard_name = var.__dict__['standard_name']
            if 'long_name' in attributes:
                long_name = var.__dict__['long_name']
            if 'axis' in attributes:
                axis = var.__dict__['axis']
            if 'units' in attributes:
                units = var.__dict__['units']
            if '_CoordinateAxisType' in attributes:
                CoordinateAxisType = var.__dict__['_CoordinateAxisType']
            if standard_name == 'longitude' or \
                    long_name == 'longitude' or \
                    axis == 'X' or \
                    CoordinateAxisType == 'Lon' or \
                    standard_name == 'projection_x_coordinate':
                self.xname = var_name
                # Fix for units; should ideally use udunits package
                if units == 'km':
                    unitfactor = 1000
                else:
                    unitfactor = 1
                x = var[:]*unitfactor
                self.unitfactor = unitfactor
                self.numx = var.shape[0]
            if standard_name == 'latitude' or \
                    long_name == 'latitude' or \
                    axis == 'Y' or \
                    CoordinateAxisType == 'Lat' or \
                    standard_name == 'projection_y_coordinate':
                self.yname = var_name
                # Fix for units; should ideally use udunits package
                if units == 'km':
                    unitfactor = 1000
                else:
                    unitfactor = 1
                y = var[:]*unitfactor
                self.numy = var.shape[0]
            if standard_name == 'depth' or axis == 'Z':
                if 'positive' not in var.ncattrs() or \
                        var.__dict__['positive'] == 'up':
                    self.z = var[:]
                else:
                    self.z = -var[:]
            if standard_name == 'time' or axis == 'T' or var_name == 'time':
                # Read and store time coverage (of this particular file)
                time = var[:]
                time_units = units
                self.times = num2date(time, time_units)
                self.start_time = self.times[0]
                self.end_time = self.times[-1]
                if len(self.times) > 1:
                    self.time_step = self.times[1] - self.times[0]
                else:
                    self.time_step = None

        if 'x' not in locals():
            raise ValueError('Did not find x-coordinate variable')
        if 'y' not in locals():
            raise ValueError('Did not find y-coordinate variable')
        self.xmin, self.xmax = x.min(), x.max()
        self.ymin, self.ymax = y.min(), y.max()
        self.delta_x = np.abs(x[1] - x[0])
        self.delta_y = np.abs(y[1] - y[0])
        if np.abs(x[-1] - x[-2]) != self.delta_x:
            print x[1::] - x[0:-1]
            raise ValueError('delta_x is not constant!')
        if np.abs(y[-1] - y[-2]) != self.delta_y:
            print y[1::] - y[0:-1]
            raise ValueError('delta_y is not constant!')
        self.x = x  # Store coordinate vectors
        self.y = y

        # Find all variables having standard_name
        self.variable_mapping = {}
        for var_name in self.Dataset.variables:
            if var_name in [self.xname, self.yname, 'depth']:
                continue  # Skip coordinate variables
            var = self.Dataset.variables[var_name]
            attributes = var.ncattrs()
            if 'standard_name' in attributes:
                standard_name = str(var.__dict__['standard_name'])
                if standard_name in self.variable_aliases:  # Mapping if needed
                    standard_name = self.variable_aliases[standard_name]
                self.variable_mapping[standard_name] = str(var_name)

        self.variables = self.variable_mapping.keys()

        # Run constructor of parent Reader class
        super(Reader, self).__init__()

    def get_variables(self, requested_variables, time=None,
                      x=None, y=None, z=None, block=False,jo_plot=False):

        joo = False
        requested_variables, time, x, y, z, outside = self.check_arguments(
            requested_variables, time, x, y, z)

        nearestTime, dummy1, dummy2, indxTime, dummy3, dummy4 = \
            self.nearest_time(time)

        if hasattr(self, 'z') and (z is not None):
            # Find z-index range
            # NB: may need to flip if self.z is ascending
            indices = np.searchsorted(-self.z, [-z.min(), -z.max()])
            indz = np.arange(np.maximum(0, indices.min() - 1 -
                                        self.verticalbuffer),
                             np.minimum(len(self.z), indices.max() + 1 +
                                        self.verticalbuffer))
            if len(indz) == 1:
                indz = indz[0]  # Extract integer to read only one layer
        else:
            indz = 0

        # Find indices corresponding to requested x and y
        indx = np.floor((x-self.xmin)/self.delta_x).astype(int)
        indy = np.floor((y-self.ymin)/self.delta_y).astype(int)

        indxi = indx
        indyi = indy
        print("Xind SHAP" , indx.shape)
        # If x or y coordinates are decreasing, we need to flip
        if self.x[0] > self.x[-1]:
            indx = len(self.x) - indx
        if self.y[0] > self.y[-1]:
            indy = len(self.y) - indy
        if block is True:
            # Adding buffer, to cover also future positions of elements
            buffer = self.buffer
            indx = np.arange(np.max([0, indx.min()-buffer]),
                             np.min([indx.max()+buffer, self.numx]))
            indy = np.arange(np.max([0, indy.min()-buffer]),
                             np.min([indy.max()+buffer, self.numy]))
        else:
            indx[outside] = 0  # To be masked later
            indy[outside] = 0

        print("Xind BLOC" , indx.shape)
        variables = {}

        from IPython import embed; embed()
        for par in requested_variables:
            var = self.Dataset.variables[self.variable_mapping[par]]

            if var.ndim == 2:
                variables[par] = var[indy, indx]
            elif var.ndim == 3:
                variables[par] = var[indxTime, indy, indx]
            elif var.ndim == 4:
                if jo_plot:
                    # hack because the netcdf cannot index large num 
                    ss = np.array(var[indxTime,indz,:,:])
                    assert(indx.shape == indy.shape)
                    print("MAXMIN", ss.min(), ss.max())
                    variables[par] = ss[indy.ravel(),indx.ravel()].reshape(indx.shape)
                    #from IPython import embed; embed()
                else:
                    variables[par] = var[indxTime, indz, indy, indx]
            else:
                raise Exception('Wrong dimension of variable: ' +
                                self.variable_mapping[par])

            #from IPython import embed; embed()
            # If 2D array is returned due to the fancy slicing methods
            # of netcdf-python, we need to take the diagonal
            if variables[par].ndim > 1 and block is False:
                if not jo_plot:
                    variables[par] = variables[par].diagonal()

            # Mask values outside domain
            if not jo_plot:
                variables[par] = np.ma.array(variables[par], ndmin=2, mask=False)
                if block is False:
                    variables[par].mask[outside] = True

        variables['time'] = nearestTime
        # Store coordinates of returned points
        try:
            variables['z'] = self.z[indz]
        except:
            variables['z'] = None
        if jo_plot:
            variables['x'] = indx
            variables['y'] = indy
            return variables
        if block is True:
            variables['x'] = \
                self.Dataset.variables[self.xname][indx]*self.unitfactor
            # Subtracting 1 from indy (not indx) makes Norkyst800
            # fit better with GSHHS coastline - but unclear why
            variables['y'] = \
                self.Dataset.variables[self.yname][indy]*self.unitfactor
        else:
            variables['x'] = self.xmin + (indx-1)*self.delta_x
            variables['y'] = self.ymin + (indy-1)*self.delta_y

        print("ret X" , variables['x'].shape)
        #from IPython import embed; embed()
        return variables
