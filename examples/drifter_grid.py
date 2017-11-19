#!/usr/bin/env python

from datetime import timedelta, datetime
import numpy as np
import logging
from opendrift.readers import reader_basemap_landmask
from opendrift.readers import reader_netCDF_CF_generic, reader_grid
from opendrift.models.oceandrift import OceanDrift
import matplotlib.pyplot as plt
import os
import pickle
o = OceanDrift()  # Basic drift model suitable for passive tracers or drifters

#######################
# Preparing Readers
#######################

# Landmask (Basemap)
basename_pkl = os.path.join(o.test_data_folder(), '16Nov2015_NorKyst_z_surface/basemap.pkl')
if not os.path.exists(basename_pkl):
    logging.info("Creating basemap for area")
    reader_basemap = reader_basemap_landmask.Reader(
                    llcrnrlon=4, llcrnrlat=59.8,
                    urcrnrlon=6, urcrnrlat=61,
                    resolution='h', projection='merc')
    pickle.dump(reader_basemap, open(basename_pkl, 'wb'))
else:
    logging.info("Loading basemap for area from: %s" %basename_pkl)
    reader_basemap = pickle.load(open(basename_pkl, 'rb'))

xsize=81
ysize=150
from LatLon import LatLon, Latitude, Longitude

# returns array of shape ny,nx containing lon,lat coordinates
aslons, aslats, asxs, asys = reader_basemap.map.makegrid(xsize,ysize,True)
slons = aslons[0,:]
slats = aslats[:,0]
print(slons.shape)
ll = LatLon(Latitude(slats.min()), Longitude(slons.min()))
lr = LatLon(Latitude(slats.min()), Longitude(slons.max()))
ul = LatLon(Latitude(slats.max()), Longitude(slons.min()))
xdis = ll.distance(lr)
ydis = ll.distance(ul)
delta_x = xsize/float(xdis)
delta_y = ysize/float(ydis)
u = np.ones((ysize,xsize))*-.5
v = np.ones((ysize,xsize))*5.5
# when u=.1 and v=2, the arrows point north
# when u=2 and v=.1, the arrows point east
# when u=-2 and v=.1, the arrows point west

param_values = {'x_sea_water_velocity':u,
                'y_sea_water_velocity':v}

reader_current = reader_grid.Reader(x=slons, y=slats, 
                             delta_x=delta_x, delta_y=delta_y, 
                             parameter_value_map=param_values)

#from IPython import embed; embed()
o.add_reader([reader_basemap,reader_current])
#######################
# Seeding elements
#######################

# Elements are moved with the ocean current, in addition to a fraction of 
# the wind speed (wind_drift_factor). This factor depends on the properties
# of the elements. Typical empirical values are:
# - 0.035 (3.5 %) for oil and iSphere driftes
# - 0.01  (1 %) for CODE drifters partly submerged ~0.5 m
# As there are large uncertainties, it makes sence to provide a statistical
# distribution of wind_drift_factors

# Using a constant value for all elements:
#wind_drift_factor = 0.03

# Giving each element a unique (random) wind_drift_factor
st = datetime.fromtimestamp(0)
o.seed_elements(4.7, 59.9, radius=1, number=10, 
                time=st)
#
########################
## Running model
########################
o.run(steps=50, time_step=timedelta(minutes=94))
#from IPython import embed; embed()
###########################
# Print and plot results
###########################
#print(o)
#o.animation()

# Plot trajectories, colored by the wind_drift_factor of each element
o.plot(background=['x_sea_water_velocity', 'y_sea_water_velocity'])
plt.show()
