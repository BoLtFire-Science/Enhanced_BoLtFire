import os
import geopandas as gpd
import glob
import pandas as pd
import math
import xarray as xr
import numpy as np
from Utilities.Path_Utilities import get_root_folder

def translator_return_variables(variable_dictionary):
    """Return lists of ERA5 variables with improved structure."""
    # Get the flat dictionary of variable translations
    _, _, _, flat_dict = variable_dictionary
    
    # Group variables by category based on their naming
    variables = {}
    for _, name in flat_dict.items():
        variables[f"{name}"] = [name]
        
    return variables

def Export_Shapefile(filtered, output_folder, output_filename):
    """Exports a GeoDataFrame to a shapefile, ensuring geometries are valid and the output directory exists."""
    #check for invalid polygons, buffer them by 0 to remove the issue (works with self inserted polygons)
    filtered["geometry"] = filtered["geometry"].apply(fix_invalid_geometry)
   # If output_folder not there, create it
    os.makedirs(output_folder, exist_ok=True)
    # Path for the output shapefile
    output_shapefile_path = os.path.join(output_folder, output_filename + ".shp")
    # Export to shapefile
    filtered.to_file(output_shapefile_path, driver='ESRI Shapefile')
    print(f"Filtered file exported to: {output_shapefile_path}")

def fix_invalid_geometry(geometry):
    """Fixes invalid geometries by applying a zero-width buffer, which can resolve issues with self-intersecting polygons."""
    if not geometry.is_valid:
          geometry = geometry.buffer(0)
    return geometry

def loadGlanceProjectionZones():
    """Loads the Glance Grid shapefiles for each continent, extracts the continent name, and returns a GeoDataFrame containing all continents with their geometries."""
    continents = []
    for continent_shape in glob.glob(f"{get_root_folder()}Glance_Grid/*.shp"):
        continent = gpd.read_file(continent_shape).to_crs(4326)
        continent = continent[["geometry"]]
        name = os.path.basename(continent_shape).split("_")[0]
        continent["name"] = name
        continents.append(continent)
    continents = gpd.GeoDataFrame(pd.concat(continents),crs=4326)
    return continents

def loadBiomes(names=["Boreal Forests/Taiga"]):
    """Loads the Ecoregions shapefile, selects only the necessary columns, filters for the specified biome names, and returns a GeoDataFrame containing the filtered ecoregions."""
    # Ecoregions
    Ecoregions = gpd.read_file(f"{get_root_folder()}Biomes/Ecoregions2017.shp").to_crs(4326)
    # Select only the necessary columns from Ecoregions dataset
    Ecoregions_subset = gpd.GeoDataFrame(Ecoregions[['BIOME_NAME', 'ECO_BIOME_', 'REALM', "ECO_NAME","ECO_ID", "geometry"]])
    # Filter the Ecoregions_subset to include only "Boreal Forests/Taiga" or "Tundra"
    Ecoregions_subset = Ecoregions[Ecoregions['BIOME_NAME'].isin(names)]
    return Ecoregions_subset

def CountryBoundaries():
    """Loads the country boundaries shapefile, ensures geometries are valid, and returns a GeoDataFrame containing the country names and their geometries."""
    countries = gpd.read_file(f"{get_root_folder()}CountryBoundaries/WB_countries_Admin0_10m.shp").to_crs(4326)
    countries["country"] = countries["NAME_EN"]
    for i, row in countries.iterrows():
         if row["country"] == None:
              countries.loc[i,"country"] = row["NAME_2"]
    countries = countries[["country","geometry"]]
    return countries
  
def getGlanceCRS(name):
    """Returns the appropriate CRS string for the given continent name based on the Glance Grid specifications."""
    if name == "AF":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - AF - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",20],PARAMETER["latitude_of_center",5],UNIT["meter",1.0]]'
    elif name == "AN":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - AN - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",0],PARAMETER["latitude_of_center",-90],UNIT["meter",1.0]]'
    elif name == "AS":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - AS - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",100],PARAMETER["latitude_of_center",45],UNIT["meter",1.0]]'
    elif name == "EU":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - EU - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",20],PARAMETER["latitude_of_center",55],UNIT["meter",1.0]]'
    elif name == "OC":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - OC - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",135],PARAMETER["latitude_of_center",-15],UNIT["meter",1.0]]'
    elif name == "NA":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - NA - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",-100],PARAMETER["latitude_of_center",50],UNIT["meter",1.0]]'
    elif name == "SA":
         return 'PROJCS["BU MEaSUREs Lambert Azimuthal Equal Area - SA - V01",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["degree",0.0174532925199433]],PROJECTION["Lambert_Azimuthal_Equal_Area"],PARAMETER["false_easting",0.0],PARAMETER["false_northing",0.0],PARAMETER["longitude_of_center",-60],PARAMETER["latitude_of_center",-15],UNIT["meter",1.0]]'
    
def snap_bbox_to_grid(bounds, res_lat, res_lon):
    """Snaps the given bounding box to a grid defined by the specified latitude and longitude resolutions, ensuring that the resulting bounding box aligns with the grid."""
    half_res_lat = res_lat / 2
    half_res_lon = res_lon / 2
    north, west, south, east = bounds
    north_snapped = math.ceil(north/ res_lat) * res_lat+half_res_lat
    south_snapped = math.floor(south / res_lat) * res_lat-half_res_lat
    west_snapped = math.floor(west / res_lon) * res_lon-half_res_lon
    east_snapped = math.ceil(east/ res_lon) * res_lon+half_res_lon
    return [north_snapped, west_snapped, south_snapped, east_snapped]

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
    lat_mask = (lats > south) & (lats < north)
    lon_mask = (lons > west) & (lons < east)

    lat_indices = np.where(lat_mask)[0]
    lon_indices = np.where(lon_mask)[0]

    if len(lat_indices) == 0 or len(lon_indices) == 0:
        raise ValueError("No data points within given bbox.")

    clipped = arr.isel(
        latitude=xr.DataArray(lat_indices, dims="latitude"),
        longitude=xr.DataArray(lon_indices, dims="longitude")
    )

    return clipped

def fast_bbox_clip_sel(arr, bbox, resolution=0.1):
    """
    Clip DataArray to bbox [north, west, south, east] using .sel with nearest.
    Works even if latitude is descending.
    Base code is written by the authors. AI was used to edit.
    """
    north, west, south, east = bbox

    # Latitude may be descending in many NetCDFs
    lat_asc = arr.latitude.values[0] < arr.latitude.values[-1]

    if lat_asc:
        lat_slice = np.arange(south, north,resolution)   # ascending: min→max
    else:
        lat_slice = np.arange(north, south,-resolution)   # descending: max→min

    lon_slice = np.arange(west, east,resolution)

    clipped = arr.sel(
        latitude=lat_slice,
        longitude=lon_slice,
        method="nearest"   # snap edges to nearest pixel centers
    )

    return clipped

