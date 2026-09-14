import os
import glob

import numpy as np
import pandas as pd 
import geopandas as gpd

from Utilities.Path_Utilities import get_preprocessing_boltfire, get_non_liws, get_enhanced_boltfire_location, get_csv_results

def normalize_continent(code: str) -> str:
    """ change NA to NorthAm, AS and EU to Eurasia """
    if code == "NA":
        return "NorthAm"
    elif code in ("AS", "EU"):
        return "Eurasia"
    return code  

def get_fire_and_hold_labels():
    """
    Returns:
      fire_labels: dict mapping unique_id → 0/1
      hold_labels: dict mapping unique_id → int(days of holdover; 0 if no fire)
    Base code is written by the authors. AI was used to edit.
    """
    labels = {}

    LIW_path = os.path.join(get_preprocessing_boltfire(), f"BoLtFire_LIWs_ALL.shp")
    NonLIW_path = os.path.join(get_non_liws(),f"BoLtFire_NonLIWs_ALL.shp")

    LIW_gdf = gpd.read_file(LIW_path)
    NonLIW_gdf = gpd.read_file(NonLIW_path)


    for _, row in LIW_gdf.iterrows():
        fid = str(row["FireID"]).split(".")[0]
        if fid not in labels:
            labels[fid] = {}

        labels[fid]["LIW"] = {
        "fire_type" : 1,
        "holdover" : int(row["HoldoverRD"]),
        "FireSize" : row["ClassSize"],
        "continent" : normalize_continent(row["cnt_short"]),
        "LC_Name" : row["LCName"],
        "LCDN": row["LCDN"],
        "year" : row["FireYear"],
        "PeakCurr": row["PeakCurr"],
        "Polarity": row["Polarity"],
        "Multiplcty": row["Multiplcty"],
        "Duration": row["Duration"],
        "EcoName": row["EcoName"],
        }


    for _, row in NonLIW_gdf.iterrows():
        fid   = str(row["FireID"]).split(".")[0]
        if fid not in labels:
            labels[fid] = {}

        labels[fid]["NonLIW"] = {
        "fire_type" : 0,
        "holdover" : 0,
        "FireSize" : row["ClassSize"],
        "continent" : normalize_continent(row["cnt_short"]),
        "year" : row["NonLIWYear"],
        "PeakCurr": row["PeakCurr"],
        "Polarity": row["Polarity"],
        "Multiplcty": row["Multiplcty"],
        "Duration": row["Duration"],
        "EcoName": row["ECO_NAME"],
        "LC_Name" : labels[fid]["LIW"]["LC_Name"],
        "LCDN": labels[fid]["LIW"]["LCDN"],
        }        

    return labels

def compute_era5_means_with_offset():
    """
    For each fire and LIWType, computes mean ERA5-Land variables (tp, t2m, ws, rh) for each 1-day offset in [-15, +15] relative to the lightning event. 
    Also includes invariant means (duration, multiplicity, peakcurrent, polarity) and NPP mean. 
    Saves results to CSV.
    Base code is written by the authors. AI was used to edit.
    """
    dir = get_enhanced_boltfire_location()
    output_dir = get_csv_results()
    era5_vars = ["tp", "t2m", "ws", "rh"]
    invariant_variables = ["duration", "multiplicity", "peakcurrent", "polarity"]

    records = []
    fire_paths = glob.glob(os.path.join(dir, "*"))
    labels = get_fire_and_hold_labels()

    for fire_path in fire_paths:
        FireID = os.path.basename(fire_path)
        if not os.path.isdir(fire_path):
            continue

        LIWType_paths = glob.glob(os.path.join(fire_path, "*"))
        for LIWType_path in LIWType_paths: 
            LType = os.path.basename(LIWType_path)
            # Invariant means
            invariant_means = {f"{inv}_mean": np.nan for inv in invariant_variables}
            invariant_fp = os.path.join(LIWType_path, "Invariant_only.npz")
            if os.path.isfile(invariant_fp):
                inv_data = np.load(invariant_fp, allow_pickle=True)
                for inv_var in invariant_variables:
                    if inv_var in inv_data:
                        invariant_means[f"{inv_var}_mean"] = np.nanmean(inv_data[inv_var])


            # Load NPP
            npp_mean = np.nan
            npp_files = glob.glob(os.path.join(LIWType_path, "Npp_*.npy"))
            if npp_files:
                try:
                    npp_array = np.load(npp_files[0], allow_pickle=True)
                    npp_mean = np.nanmean(npp_array)
                except Exception as e:
                    print(f"Warning: failed to load NPP for {FireID}/{LType} — {e}")

            # Per-day offset records
            for offset in range(-15, 15):
                rec = {"FireID": FireID,
                    "LIWType": LType,
                    "offset": offset,
                    "holdover": labels[FireID][LType]["holdover"],
                    "fire_type": labels[FireID][LType]["fire_type"],
                    "FireSize": labels[FireID][LType]["FireSize"],
                    "continent": labels[FireID][LType]["continent"],
                    "LC_Name": labels[FireID][LType]["LC_Name"],
                    "year": labels[FireID][LType]["year"],
                    "PeakCurr": labels[FireID][LType]["PeakCurr"],
                    "Polarity": labels[FireID][LType]["Polarity"],
                    "Multiplcty": labels[FireID][LType]["Multiplcty"],
                    "Duration": labels[FireID][LType]["Duration"],
                    "LCDN": labels[FireID][LType]["LCDN"],
                    "EcoName": labels[FireID][LType]["EcoName"],
                    "NPP": npp_mean
                    }

                # Add invariant means
                rec.update(invariant_means)

                # Format offset
                offset_hours_int = int(round(offset))
                offset_hours_value = f"{offset_hours_int:+03d}"

                era5_pattern = os.path.join(LIWType_path, f"ERA5Land_*{offset_hours_value}.npy")
                matching_files = glob.glob(era5_pattern)

                for var in era5_vars:
                    var_files = [f for f in matching_files if var in os.path.basename(f)]
                    if var_files:
                        arr = np.load(var_files[0], allow_pickle=True)

                        if var == "tp":
                            val = np.nanmean(arr)
                            if np.isnan(val) or val < 0:
                                val = 0
                            rec[f"{var}_mean"] = val
                        else:
                            rec[f"{var}_mean"] = np.nanmean(arr)  
                    else:
                        rec[f"{var}_mean"] = np.nan

                records.append(rec)

    # Create DataFrame
    df = pd.DataFrame(records)
    df["Multiplcty"] = df["Multiplcty"].replace(0, 1) # per internal information, multiplicity should be at least 1

    if df.empty:
        print("No data found. Empty DataFrame returned.")
        return df

    df = df.sort_values(["FireID", "LIWType", "offset"]).reset_index(drop=True)

    # Clean column order
    mean_invariant_cols = [f"{v}_mean" for v in invariant_variables]
    era5_cols = [f"{v}_mean" for v in era5_vars]
    desired_order = (
        ["FireID", "LIWType", "offset", "holdover", "FireSize", "fire_type",
        "continent", "year", "LC_Name", "PeakCurr", "Polarity", "Multiplcty",
        "Duration", "LCDN", "EcoName","NPP"]
        + mean_invariant_cols
        + era5_cols
    )

    df = df[[col for col in desired_order if col in df.columns]]

    # Save CSV
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, "summary_stats_dataset_NPP6.csv")
    df.to_csv(out_path, index=False)
    print(f"CSV saved to:\n    {out_path}  (rows: {len(df)})")

    return df
