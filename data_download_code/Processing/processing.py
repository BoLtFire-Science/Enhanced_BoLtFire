import os
import glob
import time

from functools import partial
from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from calendar import monthrange
from concurrent.futures import ProcessPoolExecutor

import pytz
import geopandas as gpd
import pandas as pd
import xarray as xr
import numpy as np
from timezonefinder import TimezoneFinder

def generate_monthly_utcfiles_parallel(root_folder, worker_count=5):
    """Generates monthly UTC files for all variables in parallel."""
    variables = {"10u":"u10", "10v":"v10", "2t":"t2m", "2d":"d2m", "tp":"tp"}

    for var in variables:
        startDate = datetime.strptime("201201", '%Y%m')
        endDate = datetime.strptime("202212", '%Y%m')

        while startDate != endDate:
            start_time = time.time()
            previous_month = startDate + relativedelta(months= -1)
            next_month = startDate + relativedelta(months=1)
            file_paths = [f"{root_folder}clipped_{var}_{datetime.strftime(startDate,'%Y%m')}.nc"]

            if os.path.exists(f"{root_folder}clipped_{var}_{datetime.strftime(previous_month,'%Y%m')}.nc"):
                file_paths.append(f"{root_folder}clipped_{var}_{datetime.strftime(previous_month,'%Y%m')}.nc")
            if os.path.exists(f"{root_folder}clipped_{var}_{datetime.strftime(next_month,'%Y%m')}.nc"):
                file_paths.append(f"{root_folder}clipped_{var}_{datetime.strftime(next_month,'%Y%m')}.nc")


            datasets = [xr.decode_cf(xr.open_mfdataset(file_path,engine="netcdf4", decode_times = False, preprocess=clean)) for file_path in file_paths]
            dataset = xr.concat(datasets, dim="time")
            
            if variables[var] != "tp":
                process_func = partial(
                    process_utc_offset, dataset=dataset, startDate=startDate, variable=variables[var], root_folder=root_folder)
            else:
                process_func = partial(
                    process_utc_offset_accumulative, dataset=dataset, startDate=startDate, variable=variables[var], root_folder=root_folder)
            utc_offsets = list(range(-12, 13))

            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                _ = list(executor.map(process_func, utc_offsets))
            
            dataset.close()
            print(f"Processed {var} for {startDate.strftime('%Y%m')} in {time.time() - start_time:.2f} seconds")
            startDate = startDate + relativedelta(months=1)

def process_utc_offset_accumulative(utc_offset,dataset,startDate,variable,root_folder):
    """Process a single UTC offset for the given month for accumulative variables
    Base code is written by the authors. AI was used to edit."""

    start = time.time()

    if os.path.exists(f"{root_folder}clipped_utc/clipped_{variable}_{startDate.year}{startDate.month:02d}_utc_{utc_offset:+03d}.nc"):
        print(f"File already exists for {variable} {startDate.year}{startDate.month:02d} with UTC offset {utc_offset:+03d}, skipping.")
        return
    
    local_midnight_in_utc = (0 - utc_offset) % 24
    if local_midnight_in_utc == 0:
        local_midnight_in_utc = 24

    ds_UTC_midnight = dataset.sel(step=timedelta(hours=24))
    ds_local_midnight = dataset.sel(step=timedelta(hours=local_midnight_in_utc))
    
    ds_UTC_midnight = ds_UTC_midnight.sel(time=~ds_UTC_midnight.time.to_index().duplicated())
    ds_local_midnight = ds_local_midnight.sel(time=~ds_local_midnight.time.to_index().duplicated())

    ds_local_midnight = ds_local_midnight.assign_coords(
        time=ds_UTC_midnight.time
        )

    ds_local_to_utc_midnight = ds_UTC_midnight - ds_local_midnight
    ds_local_to_utc_midnight = ds_local_to_utc_midnight.assign_coords(
        time=ds_local_to_utc_midnight.time - np.timedelta64(1, "D")
    )

    ds_accum_local = ds_local_midnight + ds_local_to_utc_midnight

    shift = int(utc_offset<0)
    ds_accum_local = ds_accum_local.assign_coords(
        time=ds_accum_local.time + np.timedelta64(shift, "D")
    )

    concated_data = ds_accum_local.sel(time=ds_accum_local.time.dt.month==startDate.month)
    concated_data.to_netcdf(f"{root_folder}clipped_utc/clipped_{variable}_{startDate.year}{startDate.month:02d}_utc_{utc_offset:+03d}.nc", mode='w', format='NETCDF4')
    
    print (f"Completed UTC offset {utc_offset} for {startDate.strftime('%Y%m')} and var {variable} in {time.time() - start:.2f} seconds")

def process_utc_offset(utc_offset,dataset,startDate,variable,root_folder):
    """Process a single UTC offset for the given month."""
    start= time.time()
    slice_function_times = []
    day_offset = 0
    if utc_offset < 0:
        day_offset = 1
    if utc_offset > 0:
        day_offset = -1
    end_day = monthrange(startDate.year, startDate.month)[1]
    offseted_days = []
    if os.path.exists(f"{root_folder}clipped_utc/clipped_{variable}_{startDate.year}{startDate.month:02d}_utc_{utc_offset:+03d}.nc"):
        print(f"File already exists for {variable} {startDate.year}{startDate.month:02d} with UTC offset {utc_offset:+03d}, skipping.")
        return
      
    for current_day in range(0+day_offset, end_day+day_offset):
        offseted_hours = []
        current_day_date = startDate + timedelta(days=current_day, hours=utc_offset) 
        if day_offset<0: 
            current_day_date = startDate + timedelta(days=current_day+1,hours=utc_offset)
        current_day_date = current_day_date.replace(hour=0, minute=0, second=0, microsecond=0)
        for current_hour in range(0, 24):
            current_datetime = startDate + timedelta(days=current_day, hours=current_hour) + timedelta(hours=utc_offset)
            current_date = current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
            current_step = current_datetime - current_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

            if current_step.seconds == 0:
                current_slice = dataset.sel({"time": current_date + timedelta(days=-1), "step": timedelta(hours=24)})
            else:                            
                current_slice = dataset.sel({"time": current_date, "step": current_step})
            s = time.time()
            current_slice = select_correct_time_slice(current_slice, variable)
            slice_function_times.append(time.time()-s)
            # Apply variable-specific transformations
            if variable in ["t2m", "d2m"]:
                current_slice = current_slice - 273.15
    
            offseted_hours.append(current_slice)

        day_stack = xr.concat(offseted_hours, dim="time")
        offseted_hours = day_stack.max(dim="time") 
        offseted_hours = offseted_hours.expand_dims({"day": [current_day_date]})
        offseted_days.append(offseted_hours)

    concated_data = xr.concat(offseted_days, dim="day")
    concated_data.to_netcdf(f"{root_folder}clipped_utc/clipped_{variable}_{startDate.year}{startDate.month:02d}_utc_{utc_offset:+03d}.nc", mode='w', format='NETCDF4')
    print(f"Slice times: lowest: {min(slice_function_times):.4f}s; highest:{max(slice_function_times):.4f}s; average:{(sum(slice_function_times)/len(slice_function_times)):.4f}s")
    print (f"Completed UTC offset {utc_offset} for {startDate.strftime('%Y%m')} and var {variable} in {time.time() - start:.2f} seconds")

def fast_bbox_clip(arr, bbox):
    """
    Clip array to bbox [north, west, south, east],
    but shift selection one pixel up (north) and left (west).
    Works even if coordinates are unsorted.
    Base code is written by the authors. AI was used to edit.
    """
    north, west, south, east = bbox

    # Get coordinates
    lats = arr.latitude.values
    lons = arr.longitude.values

    # Build a 1D mask for latitude
    lat_mask = (lats >= south) & (lats <= north)
    lon_mask = (lons >= west) & (lons <= east)

    lat_indices = np.where(lat_mask)[0]
    lon_indices = np.where(lon_mask)[0]

    if len(lat_indices) == 0 or len(lon_indices) == 0:
        raise ValueError("No data points within given bbox.")

    # Shift indices by -1 (up and left), ensuring bounds
    lat_indices = np.clip(lat_indices - 1, 0, len(lats) - 1)
    lon_indices = np.clip(lon_indices - 1, 0, len(lons) - 1)

    clipped = arr.isel(
        latitude=xr.DataArray(lat_indices, dims="latitude"),
        longitude=xr.DataArray(lon_indices, dims="longitude")
    )

    return clipped

tz_cache = {}
tf = TimezoneFinder()
def get_timezone_offset_hours(lat, lon, dt):
    """Get the timezone offset in hours for the given latitude, longitude, and datetime."""
    key = (round(lat, 2), round(lon, 2))
    if key in tz_cache:
        return tz_cache[key]
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return 0  # Default to UTC if timezone cannot be determined
    local_tz = pytz.timezone(tz_name)
    localized_dt = local_tz.localize(dt)
    offset = localized_dt.utcoffset().total_seconds() / 3600
    tz_cache[key] = int(offset)
    return int(offset)

def get_local_datetime(dt, offset_hours):
    """Convert a UTC datetime to local datetime using the provided offset in hours."""
    return dt - timedelta(hours=offset_hours)

def load_all_fire_metadata(continent_paths_dict):
    """Loads fire metadata from all continents and returns a list of tuples containing (continent, LIWType, FireID, geometry, StartTime)."""
    all_fires = []
    for continent, list in continent_paths_dict.items():
        for combo in list:
            LIWType, path = combo
            Fires = gpd.read_file(path).to_crs(4326)
            for _, row in Fires.iterrows():
                FireID = str(row["FireID"]).split(".")[0]
                fire_geom = row["geometry"]
                str_time = row["Str_Time"]
                all_fires.append((continent, LIWType, FireID, fire_geom, str_time))
    return all_fires

def group_fires_by_year(fire_metadata):
    """Groups fire metadata by year"""
    grouped_fires = defaultdict(list)
    for continent, LIWType, FireID, fire_geom, str_time in fire_metadata:
        year = str_time[:4] 
        grouped_fires[year].append((continent, LIWType, FireID, fire_geom, str_time))
    return grouped_fires

def preload_era5_data_for_year(year,base_dir,var_list):
    """Preloads ERA5 data for a given year and list of variables, returning a dictionary of xarray Datasets."""
    year_data = {}
    for var in var_list:
        var_dir = os.path.join(base_dir, var)
        if not os.path.exists(var_dir):
            print(f"Variable directory does not exist: {var_dir}")
            continue
        file_paths = glob.glob(os.path.join(var_dir, f"{var}_{year}*.nc"))
        if not file_paths:
            print(f"No files found for {var} in {year}")
            continue
        ds = xr.open_mfdataset(file_paths, combine='nested',concat_dim="time",engine="netcdf4")
        n_hours = ds.dims["time"]
        ds = ds.assign_coords(time=pd.date_range(start=f"{year}-04-01", periods=n_hours, freq="h")) 
        year_data[var] = ds.load()
    return year_data


def calculate_rh_ws(root_folder):
    """Calculates relative humidity and wind speed from temperature, dew point, and wind components, and saves the results as new NetCDF files."""
    var_names = [("t2m", "d2m"), ("u10", "v10")]
    for year in range(2012,2023):
        for month in range(1,13):
            year_month = f"{year}{month:02d}"
            for utc in range(-12,13):
                for var_name in var_names:
                    file1 = xr.open_dataset(os.path.join(root_folder,f"clipped_{var_name[0]}_{year_month}_utc_{utc:+03d}.nc"))
                    file2 = xr.open_dataset(os.path.join(root_folder,f"clipped_{var_name[1]}_{year_month}_utc_{utc:+03d}.nc"))    

                    da1 = _as_dataarray(file1.get(var_name[0], file1))
                    da2 = _as_dataarray(file2.get(var_name[1], file2))                                   


                    if var_name[0] == "t2m" and var_name[1] == "d2m":
                        combined = calculate_relative_humidity(da1, da2)
                        var_name_new = "rh"
                    if var_name[0] == "u10" and var_name[1] == "v10":
                        combined = calculate_wind_speed(da1, da2)
                        var_name_new = "ws"

                    file1.close()
                    file2.close()

                    combined_ds = xr.Dataset({var_name_new: combined})
                    combined_ds.to_netcdf(
                        f"{root_folder}/clipped_{var_name_new}_{year_month}_utc_{utc:+03d}.nc",
                        mode='w', format='NETCDF4'
                    )
                    print(f"Finished processing file: {var_name_new} for {year_month} UTC {utc}")
            print("All variables processed.")

def calculate_relative_humidity(T, TD):
    """
    Calculate RH from 2m temperature (°C) and dewpoint temperature (K)
    using the formula from the image.
    Base code is written by the authors. AI was used to edit.
    """
    T = _as_dataarray(T)
    TD = _as_dataarray(TD)

    RH = 100 * ((112 - 0.1 * T + TD) / (112 + 0.9 * T)) ** 8
    return RH

def calculate_wind_speed(WU, WV):
    """
    Calculate Wind Speed from U and V wind components.
    """
    WU = _as_dataarray(WU)
    WV = _as_dataarray(WV)
    Wind_Speed = np.sqrt(WU**2 + WV**2) 
    return Wind_Speed

def _as_dataarray(obj):
    """Return a DataArray whether input is a DataArray or a single-var Dataset.
    AI was used to generate this code."""
    if isinstance(obj, xr.DataArray):
        return obj
    if isinstance(obj, xr.Dataset):
        key = next(iter(obj.data_vars))
        return obj[key]
    return xr.DataArray(obj)

def clean(ds):
    """Preprocess function to drop unnecessary variables and handle time decoding issues when loading GRIB files with xarray."""
    if "valid_time" in ds:
        ds = ds.drop_vars("valid_time")
    return ds

def select_correct_time_slice(slices, variable):
    """Selects the correct time slice from the given slices for the specified variable, handling cases where multiple time slices are returned."""
    if isinstance(slices.time.values, (list, np.ndarray)):
        for t in slices.time.values:
            exact_matches = slices.time == t
            matched = slices.sel(time=exact_matches)

            for i in range(matched.sizes["time"]):
                entry = matched.isel(time=i)
                data = entry[variable]

                if data.size == 0:
                    continue
                if data.isnull().all():
                    continue
                if np.isnan(data).all():
                    continue

                return entry 
    else:
        return slices
