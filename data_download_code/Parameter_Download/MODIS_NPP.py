import os
import shutil
import requests
from datetime import datetime, timedelta

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from tqdm import tqdm

from Utilities.Path_Utilities import getEnhancedBoltFire_Location, getInputParameters
from Utilities.Most_Used_Functions import snap_bbox_to_grid

def MODIS_download_geotiff(image, bounds, geotiff_path, scale=500):
    if os.path.exists(geotiff_path):
        print(f"{geotiff_path} exists, skipping!")
        return True

    try:
        url = image.getDownloadUrl({
            "bands": ["PsnNet"],
            "region": bounds.getInfo()["coordinates"],
            "scale": scale,
            "crs": "EPSG:4326",
            "format": "GEO_TIFF",})

        response = requests.get(url, stream=True)

        if response.status_code == 200:
            with open(geotiff_path, "wb") as f:
                shutil.copyfileobj(response.raw, f)

            print(f"Saved GeoTIFF to {geotiff_path}")
            return True
        else:
            print(f"GeoTIFF download failed.")
            return False

    except Exception as e:
        print(f"Error downloading GeoTIFF")
        return False



def MODIS_download_variables():
    PsnNet = {
        "image_url": "MODIS/061/MOD17A2HGF",
        "variable": "PsnNet",
        "resolution": 500,
        "scale": 0.0001,
    }
    return [PsnNet], {"PsnNet": PsnNet}


def MODIS_download_numpy_direct(image, bounds, npy_output_path, scale_factor=0.0001, fill_value=np.nan):
    if os.path.exists(npy_output_path):
        print(f"{npy_output_path} skipping, already there")
        return True

    try:
        ee_fill_value = -30001

        sample = image.sampleRectangle(region=bounds,defaultValue=ee_fill_value).getInfo()

        arr = np.array(sample["properties"]["PsnNet"], dtype=np.float32)
        arr[arr == ee_fill_value] = np.nan

        arr *= scale_factor
        np.save(npy_output_path, arr)

       # print(f"Saved NumPy array to {npy_output_path}")
        return True

    except Exception as e:
        print(f"Error saving NumPy array {npy_output_path}: {e}")
        return False




def MODIS_downloads(lightning_path, LIWtype):
    fires = gpd.read_file(lightning_path).to_crs(4326)

    downloaded_fires = []
    failed_fires = []
    saved_fires = 0

    _, key_vars = MODIS_download_variables()

    for _, row in tqdm(fires.iterrows(), total=len(fires)):
        fire_id = str(row["FireID"]).split(".")[0]

        if fire_id in downloaded_fires:
            continue

        output_folder = os.path.join(getEnhancedBoltFire_Location(), fire_id, LIWtype)
        os.makedirs(output_folder, exist_ok=True)

        start_date_dt = datetime.strptime(row["Str_Time"][:10], "%Y-%m-%d")
        start_date = start_date_dt.strftime("%Y-%m-%d")
   
        #date_str = start_date.replace("-", "")

        StartDate_dt = datetime.strptime(start_date, "%Y-%m-%d")
        date_str = StartDate_dt.strftime("%Y%m%d")

  ## from beginning of the year to the start of the lightning strike
        accum_start_dt = datetime(StartDate_dt.year, 1, 1)
        start_str = accum_start_dt.strftime("%Y-%m-%d")
        end_str = StartDate_dt.strftime("%Y-%m-%d") 


        bounds = [
            row["geometry"].bounds[3],  # W
            row["geometry"].bounds[0],  # S
            row["geometry"].bounds[1],  # E
            row["geometry"].bounds[2],  # N
        ]

        resolution = 0.0001
        bounds = snap_bbox_to_grid(bounds, resolution, resolution)

        bounds = ee.Geometry.Rectangle(
            [
                bounds[1] - resolution / 2.0,
                bounds[0] + resolution / 2.0,
                bounds[3] + resolution / 2.0,
                bounds[2] - resolution / 2.0,
            ]
        )

        downloads_worked = True

        for _, var_info in key_vars.items():
            variable = var_info["variable"]

            try:
                if variable != "PsnNet":
                    continue

                npy_path = os.path.join(output_folder, f"Fixed_Cummulative_PsnNet_{date_str}.npy")

                collection = ee.ImageCollection(var_info["image_url"]).filterDate(f"{start_str}", f"{end_str}").select("PsnNet")

       
                n_images = collection.size().getInfo()
                if n_images == 0:
                    print(f"No PsnNet images found for {fire_id} in window {start_str}–{end_str}")
                    downloads_worked = False
                    continue

                image = collection.sum().clip(bounds)

                image = image.reproject( crs="EPSG:4326",   scale=var_info["resolution"])

                npy_download = MODIS_download_numpy_direct(image=image, bounds=bounds, npy_output_path=npy_path, scale_factor=var_info["scale"])

                # if  npy_download: # tiff_download and
                #     print(f"PsnNet geotiff and numpy downloaded for {fire_id}")
                # else:
                #     downloads_worked = False

            except Exception as e:
                print(f" Problem downloading {fire_id}")
                downloads_worked = False

        if downloads_worked:
            downloaded_fires.append(fire_id)
            saved_fires += 1
        else:
            failed_fires.append(fire_id)

    print(f" PsnNet download completed - successful: {saved_fires}, failed: {len(failed_fires)}")

    if failed_fires:
        failed_df = pd.DataFrame(failed_fires, columns=["FailedFireID"])
        failed_export_path = os.path.join(getInputParameters(), "PsnNet_Failed_Fires.csv")
        failed_df.to_csv(failed_export_path, index=False)
        print(f"Failed Fires exported to: {failed_export_path}")
