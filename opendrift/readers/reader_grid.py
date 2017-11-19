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


from basereader import BaseReader
import numpy as np


class Reader(BaseReader):
    
    def __init__(self, x, y, delta_x, delta_y, parameter_value_map):
        '''init with a map {'variable_name': value, ...}'''

        for key, var in parameter_value_map.iteritems():
            parameter_value_map[key] = np.atleast_1d(var)
        self.projected = True
        
        self._parameter_value_map = parameter_value_map
        self.variables = parameter_value_map.keys()
        # values are lat lon
        self.proj4 = '+proj=latlong'

        self.xmin = min(x)
        self.xmax = max(x)
        self.ymin = min(y)
        self.ymax = max(y)
        self.x = x
        self.y = y
        self.numx = x.shape[0]
        self.numy = y.shape[0]
        # delta meters
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.start_time = None
        self.end_time = None
        self.time_step = None
        self.name = 'grid_reader'

        # Run constructor of parent Reader class
        super(Reader, self).__init__()
        
    
    def get_variables(self, requested_variables, time=None,
                      x=None, y=None, z=None, block=False):
        
        print('X shap begin', x.shape)
        variables = {'time': time, 'z': z}

        # get indices
        indx = []
        indy = []
        if type(x) == list:
            for xx in x:
                indy.append(np.argmin(abs(xx-self.x)))
        elif type(x) == np.ndarray:
            for xx in list(x.ravel()):
                indx.append(np.argmin(abs(xx-self.x)))
            indx = np.array(indx)#.reshape(x.shape)
        elif type(x) == type(None):
            indx = None
        else:
            # value?
            indx.append(np.argmin(abs(x-self.x)))
        if type(y) == list:
            for yy in y:
                indy.append(np.argmin(abs(yy-self.y)))
        elif type(y) == np.ndarray: 
            for yy in list(y.ravel()):
                indy.append(np.argmin(abs(yy-self.y)))
            indy = np.array(indy)#.reshape(y.shape)

        elif type(y) == type(None):
            indy = None
        else:
            # value?
            indy.append(np.argmin(abs(y-self.y)))
       

        print('Xind shap begin', indx.shape)
        if block is True: 
            # add buffer to cover future positions of elements
            buf = self.buffer
            indx = np.arange(np.max([0, indx.min()-buf]), 
                             np.min([indx.max()+buf, self.numx]))
            indy = np.arange(np.max([0, indy.min()-buf]), 
                             np.min([indy.max()+buf, self.numy]))

        print('Xind shap block', indx.shape)

 
        if type(indx) == type(None):
            variables['x'] = None
            variables['y'] = None
            for par in requested_variables:
               if par in self._parameter_value_map.keys():
                   #print("READING", par, indy, indx)
                   variables[par] = None
            
            
        else:
            variables['x'] = self.x[indx]
            variables['y'] = self.y[indy]
            for par in requested_variables:
                if par in self._parameter_value_map.keys():
                    var = self._parameter_value_map[par]
                    try:
                        variables[par] = var[indy,:][:, indx]
                    except Exception, e:
                        print(e)
                    #print(par,'from index', indx,  variables[par])
        
        print("FINISHED")
        print('var[x]', variables['x'].shape)
        print('var[other]', par,variables[par].shape)
        return variables
        
