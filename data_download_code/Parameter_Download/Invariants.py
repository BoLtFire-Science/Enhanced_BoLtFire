import os

import rasterio 
import geopandas as gpd
from datetime import datetime
import numpy as np 

from rasterio.transform import from_bounds

from Utilities.Most_Used_Functions import snap_bbox_to_grid
from Utilities.Path_Utilities import get_era5_reanalysis_folder

def scale_to_bounds(data, grid_size=(512, 512)):
    """
    Scale the input data to fit within the bounds of a given geometry and grid size.
    Here we are just replicating the value across the entire grid for simplicity.
    """
    scaled_data = np.full(grid_size, data)
    return scaled_data


def generate_invariants_data(lightning_path, LIWtype):
    """For each fire, generates invariant data (peak current, multiplicity, duration, polarity, month) 
    and saves it as .npy files (for model input) and GeoTIFFs (for visualization)."""
    Fires = gpd.read_file(lightning_path).to_crs(4326)

    for _, row in Fires.iterrows():
        FireID = str(row["FireID"]).split(".")[0]
        
        # Get bounds (North, West, South, East)
        bounds = [row["geometry"].bounds[3],  # North
                  row["geometry"].bounds[0],  # West
                  row["geometry"].bounds[1],  # South
                  row["geometry"].bounds[2]]  # East
        resolution = 0.5
        bounds = snap_bbox_to_grid(bounds, resolution, resolution)

        StartDaterow = row["StartDate"]
        StartDate = datetime.strptime(StartDaterow, "%Y-%m-%d")
        month = StartDate.strftime("%m") 

        # Define invariants
        invariants = {
            "peakcurrent": row["PeakCurr"],
            "multiplicity": row["Multiplcty"],
            "duration": row["Duration"],
            "econame": row["EcoID"],
            "areaHa": row["AreaHa"],
            "polarity": 0 if row["Polarity"].lower() == "negative" else 1 ,
            "month": int(month)
        }

        output_path = os.path.join(get_era5_reanalysis_folder(), FireID, LIWtype, "Invariant_data")
        os.makedirs(output_path, exist_ok=True)

        for name, value in invariants.items():
            # Scale the value to fit the bounds of the fire
            scaled_data = scale_to_bounds(value, grid_size=(1,1))
            
            np.save(os.path.join(output_path, f"{name}.npy"), scaled_data)
