#!/usr/bin/env python

from datetime import datetime, timedelta

from opendrift.readers import reader_basemap_landmask
from opendrift.readers import reader_netCDF_CF_generic
from opendrift.models.openoil import OpenOil

o = OpenOil(loglevel=0)  # Set loglevel to 0 for debug information

# Arome
#reader_arome = reader_netCDF_CF_generic.Reader('http://thredds.met.no/thredds/dodsC/arome25/arome_metcoop_default2_5km_latest.nc')
reader_arome = reader_netCDF_CF_generic.Reader(o.test_data_folder() + '16Nov2015_NorKyst_z_surface/arome_subset_16Nov2015.nc')

# Norkyst
#reader_norkyst = reader_netCDF_CF_generic.Reader('http://thredds.met.no/thredds/dodsC/sea/norkyst800m/1h/aggregate_be')
reader_norkyst = reader_netCDF_CF_generic.Reader(o.test_data_folder() + '16Nov2015_NorKyst_z_surface/norkyst800_subset_16Nov2015.nc')

# Landmask (Basemap)
reader_basemap = reader_basemap_landmask.Reader(
                    llcrnrlon=4, llcrnrlat=59.8,
                    urcrnrlon=6, urcrnrlat=61,
                    resolution='h', projection='merc')

o.add_reader([reader_basemap, reader_norkyst, reader_arome])

# Seeding some particles
lon = 4.6; lat = 60.0; # Outside Bergen
#lon = 6.73; lat = 62.78; # Outside Trondheim

time = None
#time = datetime(2015, 9, 22, 6, 0, 0)
time = [reader_arome.start_time,
        reader_arome.start_time + timedelta(hours=30)]
#time = reader_arome.start_time

# Seed oil elements at defined position and time
o.seed_elements(lon, lat, radius=50, number=10, time=time,
                wind_drift_factor=.02)

print o
print o.list_configspec()  # Show configuration values and options

# Adjusting some configuration
o.set_config('processes:diffusion', True)
o.set_config('processes:dispersion', True)
o.set_config('processes:evaporation', True)
o.set_config('processes:emulsification', True)
o.set_config('drift:current_uncertainty', .1)
o.set_config('drift:wind_uncertainty', 1)

# Running model (until end of driver data)
o.run(end_time=reader_norkyst.end_time, time_step=1800,
      time_step_output=3600, outfile='openoil.nc',
      export_variables=['mass_oil'])

# Print and plot results
print o
o.plot(background=['x_sea_water_velocity', 'y_sea_water_velocity'], buffer=.5)
#o.animation()
#o.animation(filename='openoil_time_seed.gif')
o.plot()
#o.plot_property('mass_oil')
#o.plot_property('x_sea_water_velocity')
