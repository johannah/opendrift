#!/usr/bin/env python

from datetime import timedelta
import numpy as np
import logging
from opendrift.readers import reader_basemap_landmask
from opendrift.readers import reader_netCDF_CF_generic
from opendrift.models.oceandrift import OceanDrift
from opendrift.models.drifterdrift import DrifterDrift
import os
import sys
import pickle
import time
import errno

def get_random_valid_lon(LLlon, URlon, num_rd_choices)
        lon_choices = np.linspace(LLlon, URlon, num_rd_choices)
        rd_lon_init = np.random.choice(lon_choices, 1)[0]
        logging.info("Generating random initial lon at: %s" %rd_lon_init)

def get_random_valid_lat(LLlat, URlat, num_rd_choices):
        lat_choices = np.linspace(LLlat, URlat, num_rd_choices)
        rd_lat_init = np.random.choice(lat_choices, 1)[0]
        logging.info("Generating random initial lat at: %s" %rd_lat_init)


class drifterPropagate():
    def __init__(self, LLlon, LLlat, URlon, URlat, 
            current_nc_path, wind_nc_path='', drifter_name='1', 
            drifter_battery_life_hours=6, num_rd_choices=500, 
            rd_lon_init=None, rd_lat_init=None, drifter_age_secs=0):
        """
        :drifter_name: string to use for referencing drifter
        :current_nc_path: file path to current vector fields 
        :wind_nc_path: file path to current wind fields 
        """

        if not os.path.exists(current_nc_path):
            logging.error("Current nc file: %s does not exist" %current_nc_path)
            raise IOError(errno.ENOENT, 'file not found:', current_nc_path)
        
        reader_current = reader_netCDF_CF_generic.Reader(current_nc_path)
        reader_wind = reader_netCDF_CF_generic.Reader(wind_nc_path)

    
        self.omodel = DrifterDrift()  # Basic drift model suitable for passive tracers or drifters
        # Landmask (Basemap)
        current_folder = os.path.split(current_nc_path)[0]
        mapname = os.path.split(current_nc_path)[1].split('.')[0] + \
               'basemap_UR%02.02flon_%02.02flat_LL%02.02flon_%02.02flat.pkl' %(
                          URlon, URlat, LLlon, LLlat)
        basename_pkl = os.path.join(current_folder, mapname)
        if not os.path.exists(basename_pkl):
            logging.info("Creating basemap for area")
            reader_basemap = reader_basemap_landmask.Reader(
                            llcrnrlon=LLlon, llcrnrlat=LLlat,
                            urcrnrlon=URlon, urcrnrlat=URlat,
                            resolution='h', projection='merc')
            pickle.dump(reader_basemap, open(basename_pkl, 'wb'))
        else:
            logging.info("Loading basemap for area from: %s" %basename_pkl)
            reader_basemap = pickle.load(open(basename_pkl, 'rb'))
        self.omodel.add_reader([reader_basemap, reader_current, reader_wind])
        # initiate time tracker
        self.current_time = reader_current.start_time
        self.init_time=reader_current.start_time
        self.drifter_secs = drifter_age_secs
        self.max_drifter_secs=60*60*drifter_battery_life_hours # hours
        # pick random initial position (will not be used if drifter is placed)
        if type(rd_lon_init) != float:
            rd_lon_init = get_random_valid_lon(LLlon, URlon, num_rd_choices)
        if type(rd_lat_init) != float:
            rd_lat_init = get_random_valid_lat(LLlat, URlat, num_rd_choices)
        self.set_drifter_status(0, rd_lon_init, rd_lat_init) 

    def set_drifter_battery_life_secs(self, secs_passed):
        """
        :secs_passed: float to drain battery by seconds and mark age of drifter deployment
        """
        print("SECONDS_PASSED", secs_passed)
        self.drifter_secs += secs_passed
        self.drifter_secs_remaining = self.max_drifter_secs-self.drifter_secs
        self.battery_percentage = self.drifter_secs/float(self.max_drifter_secs)
        self.omodel.set_config('drift:max_age_seconds', self.drifter_secs_remaining)

    def set_drifter_status(self, secs_passed, lon, lat):
        """
        :secs_passed time to age the drifter's battery on status since last update
        :lon longitude in decimal degrees that describes current state (dropon/dropoff/after propagate)
        :lat latitude in decimal degrees that describes current state (dropon/dropoff/after propagate)
        """
        self.lon = lon
        self.lat = lat
        self.set_drifter_battery_life_secs(secs_passed)
        self.current_time = self.current_time + timedelta(seconds=secs_passed)
        logging.info('updating status lon:%s lat:%s' %(lon, lat))
        logging.info('updating status time:%s battery remaining:%s' %(self.current_time, self.battery_percentage))

    def propagate(self, time_step=timedelta(minutes=1), 
            duration=timedelta(minutes=10),
            num_elements=500, seed_radius=1, wind_drift_factor=.03):
        """
        :drifter_time
        :timestep timedelta() of interval to log position
        :duration timedelta() of time to propagate before reporting back position
        """

        print('num elements', num_elements)
        # Elements are moved with the ocean current, in addition to a fraction of 
        # the wind speed (wind_drift_factor). This factor depends on the properties
        # of the elements. Typical empirical values are:
        # - 0.035 (3.5 %) for oil and iSphere driftes
        # - 0.01  (1 %) for CODE drifters partly submerged ~0.5 m
        # As there are large uncertainties, it makes sence to provide a statistical
        # distribution of wind_drift_factors
        wind_drift_factor = np.random.uniform(0, wind_drift_factor, num_elements)
        # updating the drifter time does not seem to work without resetting the model
        # TODO set time remaining properly
        print(self.lon, self.lat)
        self.omodel.seed_elements(self.lon, self.lat, 
                                  radius=seed_radius, number=num_elements,
                                  time=self.init_time,
                                  wind_drift_factor=wind_drift_factor)
        #from IPython import embed; embed()
        self.omodel.run(time_step=time_step, duration=duration)
    
        num_elements_active = self.omodel.num_elements_active()
        # make sure that some of the seeds survived and not all were stranded/dead
        if num_elements_active:
            choices = np.arange(0,num_elements_active)
            # randomly sample one of the seeds to use as the true position
            drifter_index = np.random.choice(choices,size=1)[0]
            if not hasattr(self, 'history'):
                self.history = self.omodel.history[drifter_index,:]
            else:
                self.history = np.concatenate((self.history, self.omodel.history[drifter_index,1:]))
            drifter_id = self.omodel.elements.ID[drifter_index]
            drifter_lat = self.omodel.elements.lat[drifter_index]
            drifter_lon = self.omodel.elements.lon[drifter_index]
            # get time in secs of this run
            drifter_runtime_secs = self.omodel.elements.age_seconds[drifter_index]
            self.set_drifter_status(drifter_runtime_secs, drifter_lon, drifter_lat)
            # remove all of the elements from the batch so that we can start 
            # over from the position of the selected element in drifter_index
            self.omodel.deactivate_elements(choices)
            self.omodel.remove_deactivated_elements()
            #lat_history = o.history['lat'][drifter_index]
            #lon_history = o.history['lon'][drifter_index]
            #x_wind = o.history['x_wind'][drifter_index]
            #y_wind = o.history['y_wind'][drifter_index]
            #x_seav = o.history['x_sea_water_velocity'][drifter_index]
            #y_seav = o.history['y_sea_water_velocity'][drifter_index]
            #wind_drift_factor = o.history['wind_drift_factor'][drifter_index]
            #status = o.history['status'][drifter_index]
            #age_secs = o.history['age_secs'][drifter_index]
            
            # time update seems to break things - TODO
            #drifter_time = drifter_time + timedelta(seconds=drifter_age)
            # TODO Report position
            # seed from reported position
    

'''    
# Plot trajectories, colored by the wind_drift_factor of each element
#o.plot(linecolor='wind_drift_factor')
'''
def test_invalid_current_file():
    dprop = drifterPropagate(LLlon=4.0, LLlat=59.8, URlon=5, URlat=61, current_nc_path='notarealfile.foobar')

def test_opendrift_install():
    from opendrift.models.oceandrift import OceanDrift

def test_example_norway_init():
    from opendrift.models.oceandrift import OceanDrift
    o = OceanDrift()
    base_folder = o.test_data_folder()
    norway16folder = "16Nov2015_NorKyst_z_surface" 
    current_path = os.path.join(base_folder, norway16folder,
           'norkyst800_subset_16Nov2015.nc')
    wind_path = os.path.join(base_folder,  norway16folder,
               'arome_subset_16Nov2015.nc')
    dprop = drifterPropagate(LLlon=4.0, LLlat=59.8, URlon=5, URlat=61, 
                             current_nc_path=current_path, wind_nc_path=wind_path, 
                             rd_lon_init=4.7, rd_lat_init=59.9)
    return dprop

def test_example_norway_propagate_duration():
    dprop = test_example_norway_init()
    total_drift_secs = 0
    for i in range(10):
        current_time = dprop.current_time
        log_every = np.random.randint(10,30)
        log_interval_secs = timedelta(seconds=(log_every))
        # ensure even duration
        report_every = log_every*np.random.randint(5,10)
        duration_secs = timedelta(seconds=report_every)
        expected_final_time = duration_secs + current_time
        dprop.propagate(log_interval_secs, 
                        duration=duration_secs,
                        num_elements=400, 
                        seed_radius=2, wind_drift_factor=.02)
        assert(dprop.current_time == expected_final_time)
        total_drift_secs += duration_secs.seconds
        print("Adding seconds", duration_secs)
    
    
    #from IPython import embed; embed()
    drifter_secs_remaining = dprop.max_drifter_secs-total_drift_secs
    assert(drifter_secs_remaining == dprop.drifter_secs_remaining)

test_example_norway_propagate_duration()
# todo init history
# todo step through time?
# 
