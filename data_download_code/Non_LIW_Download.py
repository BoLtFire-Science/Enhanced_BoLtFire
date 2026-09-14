import os
from datetime import datetime

import pandas as pd
from datetime import timedelta, datetime
import geopandas as gpd
import geopandas as gpd
import pandas as pd
import ee
import requests  
import shutil
from tqdm import tqdm  
from shapely.geometry import box

from Utilities.Most_Used_Functions import getGlanceCRS
from Utilities.Path_Utilities import get_entln_continent, get_preprocessing_boltfire, get_non_liws, get_gwis_main_dataset
from Utilities.Most_Used_Functions import getGlanceCRS
from Utilities.Path_Utilities import get_gwis_main_dataset

def clip_entln_by_liws_buffered(continent):
    """Using the GWIS & BoLtFire datasets, for each BoLtFire LIW, search backwards year-by-year to find other lightning events that did not create a fire.
    Base code is written by the authors. AI was used to edit."""
    ClippedENTLN = []
    NonLIWs_wo_Flashes = []
    crs = getGlanceCRS(continent)

    # Load all fire data once
    fires = gpd.read_file(os.path.join(get_non_liws(), f"BoLtFire_Buffered_{continent}.shp")).to_crs(crs)

    # Caches
    globfire_cache = {}
    entln_cache = {}

    for _, row in tqdm(fires.iterrows(), total=fires.shape[0], desc="Processing Fires", unit="fire"):
        year = int(row["FireYear"])
        month = int(row["StartDate"].split("-")[1])
        continent_short = continent
        fireID = int(row["FireID"])
        fire_geom = row["geometry"]
        fire_bounds = box(*fire_geom.bounds)

        # look back from year-1 down to 2012
        for fireyear in range(year - 1, 2011, -1):
            gf_key = (fireyear, continent_short)
            # load globfire for this year
            if gf_key not in globfire_cache:
                gf_path = f"{get_gwis_main_dataset()}original_globfire_filtered_{fireyear}_{continent_short}.shp"
                if os.path.exists(gf_path):
                    globfire_cache[gf_key] = gpd.read_file(gf_path).to_crs(crs)
                else:
                    print (f"GlobFire file not found for year {fireyear} and continent {continent_short}: {gf_path}. Skipping.")
                    continue

            globfire_data = globfire_cache[gf_key]
            GlobFire_clipped = gpd.clip(globfire_data[globfire_data.intersects(fire_bounds)], fire_geom)

            if GlobFire_clipped.empty:
                next_year = fireyear - 1
                gf_key_next = (next_year, continent_short)
                if next_year >= 2012:
                    if gf_key_next not in globfire_cache:
                        gf_path_next = f"{get_gwis_main_dataset()}original_globfire_filtered_{next_year}_{continent_short}.shp"
                        if os.path.exists(gf_path_next):
                            globfire_cache[gf_key_next] = gpd.read_file(gf_path_next).to_crs(crs)
                        else:
                            print (f"GlobFire file not found for year {next_year} and continent {continent_short}: {gf_path_next}. Skipping")
                            continue

                    globfire_data_next = globfire_cache[gf_key_next]
                    GlobFire_clipped_next = gpd.clip(
                        globfire_data_next[globfire_data_next.intersects(fire_bounds)],
                        fire_geom
                    )

                    # if 2 years back there is any globfire, skip ENTLN for current fireyear
                    if not GlobFire_clipped_next.empty:
                        continue

                # if years of empty globfire, do the ENTLN clipping:
                entln_key = (fireyear, continent_short)
                if entln_key not in entln_cache:
                    entln_path = f"{get_entln_continent()}ENTLN_Boreal_{fireyear}_{continent_short}.shp"
                    if os.path.exists(entln_path):
                        entln_df = gpd.read_file(entln_path).to_crs(crs)
                        entln_df["timestamp"] = pd.to_datetime(entln_df["timestamp"].str[:26], format="%Y-%m-%dT%H:%M:%S.%f", errors='coerce')
                        entln_cache[entln_key] = entln_df
                    else:
                        print(f"ENTLN file not found for year {fireyear} and continent {continent_short}: {entln_path}. Skipping.")
                        continue

                entln_data = entln_cache[entln_key]

        
                entln_data["timestamp"] = pd.to_datetime(entln_data["timestamp"],errors="coerce",infer_datetime_format=True)

                entln_filtered = entln_data[
                    (entln_data["timestamp"].dt.month == month) &
                    (entln_data.intersects(fire_bounds))
                ]

                ENTLN_clipped = gpd.clip(entln_filtered, fire_geom)

                if not ENTLN_clipped.empty:
                    ENTLN_clipped["FireID"] = fireID
                    ENTLN_clipped["LIWYear"] = year
                    ENTLN_clipped["NonLIWYear"] = fireyear
                    ENTLN_clipped["FlashCnt"] = len(ENTLN_clipped)
                    ClippedENTLN.append(ENTLN_clipped)
                    break

        else:
            NonLIWs_wo_Flashes.append({"FireID": fireID, "ENTLNYr": fireyear, "Reason": "fires", "geometry": fire_geom})

    # Save clipped ENTLN
    if ClippedENTLN:
        ClippedENTLN_gdf = gpd.GeoDataFrame(pd.concat(ClippedENTLN, ignore_index=True), crs=crs)
        output_path = os.path.join(get_non_liws(), f"All_NonLIW_Flashes_{continent}.shp")
        ClippedENTLN_gdf.to_file(output_path)
        print(f"Saved all Non-LIW flashes to: {output_path}")

    # Save fire records with no lightning found
    if NonLIWs_wo_Flashes:
        NonLIWs_gdf = gpd.GeoDataFrame(NonLIWs_wo_Flashes, crs=crs)
        output_path_non = os.path.join(get_non_liws(), f"{continent}_NonLIWs_without_Flashes.shp")
        NonLIWs_gdf.to_file(output_path_non)
        print("Saved fires without flashes.")

def get_neares_flashes(continent):
    """Using the list of non-wildfire starting lightning events, find the nearest flash to each BoLtFire LIW ignition point."""
    Nearest_NonLIW_Flash = []
    #BoLtFire - flashes file location
    LIWFlashes_file_path = os.path.join(get_preprocessing_boltfire(), f"BoLtFire_Buffered_{continent}_All.shp")
    LIWFlashes_file = gpd.read_file(LIWFlashes_file_path).to_crs(getGlanceCRS(continent))
    # NonLIW BoltFire - flashes file location
    NonLIWFlashes_file_path = os.path.join(get_non_liws(), f"All_NonLIW_Flashes_{continent}.shp")
    NonLIWFlashes_file = gpd.read_file(NonLIWFlashes_file_path).to_crs(getGlanceCRS(continent))

    # Select Long,Lat for geometry to use in matching
    NonLIWFlashes = gpd.GeoDataFrame(NonLIWFlashes_file, geometry=gpd.points_from_xy(NonLIWFlashes_file["longitude"], NonLIWFlashes_file["latitude"]))

    # Group non-LIW flashes by FireID
    NonLIW_Grouped = NonLIWFlashes.groupby("FireID")

    for _, row in tqdm(LIWFlashes_file.iterrows(), total=LIWFlashes_file.shape[0], desc="Processing LIW flashes"):
        fire_id = row["FireID"]
        longlat = gpd.GeoDataFrame([row], geometry=gpd.points_from_xy([row["IgnLong"]], [row["IgnLat"]]))
        if fire_id in NonLIW_Grouped.groups:
            candidates = NonLIW_Grouped.get_group(fire_id)
            distances = candidates.geometry.distance(longlat.iloc[0]["geometry"])
            nearest_idx = distances.idxmin()
            nearest_row = candidates.loc[nearest_idx]
            nearest_row.geometry = row.geometry
            startdate_str = nearest_row["starttime"].split("T")[0]
            startdate = datetime.strptime(startdate_str, "%Y-%m-%d")
            StartDate = startdate.strftime("%Y-%m-%d")
            nearest_row["StartDate"] = StartDate
            enddate_str = nearest_row["endtime"].split("T")[0]
            enddate = datetime.strptime(enddate_str, "%Y-%m-%d")
            EndDate = enddate.strftime("%Y-%m-%d")
            nearest_row["EndDate"] = EndDate
            Nearest_NonLIW_Flash.append(nearest_row)

    Nearest_NonLIW_Flash_gpd = gpd.GeoDataFrame(Nearest_NonLIW_Flash, crs=getGlanceCRS(continent))
    output_path = os.path.join(get_non_liws(), f"NonLIW_Nearest_Flash_{continent}.shp")
    Nearest_NonLIW_Flash_gpd.to_file(output_path)
    print(f"Saved nearest Non-LIW flashes to: {output_path}")

def download_image_modis(output_folder, resolution, FireID, bounds, image, vis_params, filename):
    """ Function to download MODIS imagery from Google Earth Engine """
    url = image.visualize(**vis_params).getDownloadURL({
        "dimensions": f"{resolution}x{resolution}",
        'region': bounds,
        'format': 'GEO_TIFF',
        "crs": "EPSG:4326"
    })

    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(os.path.join(output_folder, filename), 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
        del response
        print(f"Downloaded {filename} to {FireID} folder.")
    else:
        print(f"Failed to download {filename}. HTTP status code: {response.status_code}")


def download_non_liw_image_modis(continent, NonLIW_file_path):
    """ This function is the base function to help download pre- and post- fire MODIS imagery for Non-LIW events using Google Earth Engine. 
    These images are used to visually ensure lightning did not create a fire event. """
    NonLIW_file = gpd.read_file(NonLIW_file_path).to_crs(4326)
    downloaded_NonLIWs = []
    skipped_NonLIWs = []
    savedImages = 0
    for _, row in NonLIW_file.iterrows():
        FireID = str(row["FireID"])
        if FireID in downloaded_NonLIWs:
            continue
        base_output = os.path.join(get_non_liws(), "Imagery", continent, FireID)
        # if the folder exists and contains any files, assume we're done
        if os.path.isdir(base_output) and any(os.scandir(base_output)):
            print(f"Skipping {FireID}: output already exists at {base_output}")
            skipped_NonLIWs.append(FireID)
            continue
        # Visual parameters for RGB
        trueColor_vis_params = {
            'bands': ['sur_refl_b01', 'sur_refl_b04', 'sur_refl_b03'],
            'min': -100,
            'max': 3000,
        }
        # Visual parameters for classified dNBR
        dNBR_vis_params = {
            'min': 1,
            'max': 5,
            'palette': ['#006400', '#7FFF00', '#FFFF00','#FFA500', '#FF0000']  
        }
        # Visual parameters for binary image
        Binary_dNBR_vis_params = {
            'min': 0,
            'max': 1,
            'palette': ['black', 'white']
        }

        timestamp = row["StartDate"]
        year = int(timestamp.split("-")[0])

        # Get dates
        preNonLIW_start = datetime.strptime(timestamp, "%Y-%m-%d") + timedelta(days=-7)
        preNonLIW_end = datetime.strptime(timestamp, "%Y-%m-%d") + timedelta(days=+1)
        postNonLIW_start = datetime.strptime(timestamp, "%Y-%m-%d") + timedelta(days=-1)
        postNonLIW_end = datetime.strptime(timestamp, "%Y-%m-%d") + timedelta(days=+10)
        preNonLIW_start_str = preNonLIW_start.strftime("%Y-%m-%d")
        postNonLIW_end_str = postNonLIW_end.strftime("%Y-%m-%d")

        resolution = 500
        # Get bounds
        bound = [row["geometry"].bounds[0],  # West
                row["geometry"].bounds[1],  # South
                row["geometry"].bounds[2],  # East
                row["geometry"].bounds[3]]  # North
        bounds = ee.Geometry.Rectangle(bound)

        if year >= 2012:
            NIR_band = 'sur_refl_b02'
            SWIR_band = 'sur_refl_b07'
            bands_select = ['sur_refl_b01', 'sur_refl_b02', 'sur_refl_b03', 'sur_refl_b04', 'sur_refl_b07']
            # Load Aqua and Terra collections for pre-fire period
            prefireImCol_Aqua = ee.ImageCollection("MODIS/061/MYD09A1") \
                .filterDate(preNonLIW_start.strftime("%Y-%m-%d"), preNonLIW_end.strftime("%Y-%m-%d")) \
                .filterBounds(bounds).select(bands_select)  

            prefireImCol_Terra = ee.ImageCollection("MODIS/061/MOD09A1") \
                .filterDate(preNonLIW_start.strftime("%Y-%m-%d"), preNonLIW_end.strftime("%Y-%m-%d")) \
                .filterBounds(bounds).select(bands_select)

            # Merge Aqua and Terra collections
            prefireImCol = prefireImCol_Aqua.merge(prefireImCol_Terra)

            # Load Aqua and Terra collections for post-fire period
            postfireImCol_Aqua = ee.ImageCollection("MODIS/061/MYD09A1") \
                .filterDate(postNonLIW_start.strftime("%Y-%m-%d"), postNonLIW_end.strftime("%Y-%m-%d")) \
                .filterBounds(bounds).select(bands_select) 

            postfireImCol_Terra = ee.ImageCollection("MODIS/061/MOD09A1") \
                .filterDate(postNonLIW_start.strftime("%Y-%m-%d"), postNonLIW_end.strftime("%Y-%m-%d")) \
                .filterBounds(bounds).select(bands_select)

            # Merge Aqua and Terra collections
            postfireImCol = postfireImCol_Aqua.merge(postfireImCol_Terra)

            # Check if image collections are empty
            if prefireImCol.size().getInfo() == 0 or postfireImCol.size().getInfo() == 0:
                print(f"Skipping MODIS images for Id {FireID} due to insufficient data.")
                skipped_NonLIWs.append(FireID)
                continue

            else:
                Pre = prefireImCol.mosaic()
                Post = postfireImCol.mosaic()

                # Calculate NBR and dNBR for MODIS
                Pre_NBR = Pre.normalizedDifference([NIR_band, SWIR_band])
                Post_NBR = Post.normalizedDifference([NIR_band, SWIR_band])
                dNBR = Pre_NBR.subtract(Post_NBR)

                # Classify dNBR into severity levels
                """
                1 - enhanced regrowth
                2 - unburned
                3 - low severity
                4 - moderate severity
                5 - high severity 
                """
                classified_dNBR = ee.Image(0) \
                    .where(dNBR.lt(-0.1), 1) \
                    .where(dNBR.gte(-0.1).And(dNBR.lte(0.1)), 2) \
                    .where(dNBR.gt(0.1).And(dNBR.lte(0.27)), 3) \
                    .where(dNBR.gt(0.27).And(dNBR.lte(0.66)), 4) \
                    .where(dNBR.gt(0.66), 5)  

                # Create binary image: 1 for Moderate and High Severity, 0 otherwise
                binary = classified_dNBR.gte(4).selfMask()
                output_folder = os.path.join(get_non_liws(), "Imagery", continent,FireID)

                os.makedirs(output_folder, exist_ok=True)

                download_image_modis(output_folder, resolution, FireID, bounds, Pre, trueColor_vis_params, f'MODIS_PreFire_{FireID}_{preNonLIW_start_str}.tif')
                download_image_modis(output_folder, resolution, FireID, bounds, Post, trueColor_vis_params, f'MODIS_PostFire_{FireID}_{postNonLIW_end_str}.tif')
                download_image_modis(output_folder, resolution, FireID, bounds, classified_dNBR, dNBR_vis_params, f'MODIS_dNBR_{FireID}.tif')
                download_image_modis(output_folder, resolution, FireID, bounds, binary, Binary_dNBR_vis_params, f'MODIS_Binary_{FireID}.tif')

                print(f"Processed MODIS images for Id {FireID}")

                downloaded_NonLIWs.append(FireID)
                savedImages += 1
    if len(skipped_NonLIWs) >= 1:
       skipped_NonLIWs_gdf = gpd.GeoDataFrame(skipped_NonLIWs)
       output_path_non = os.path.join(get_non_liws(), "skipped_NonLIWs_gdf.shp")
       skipped_NonLIWs_gdf.to_file(output_path_non)
    print("All MODIS downloads completed.")

