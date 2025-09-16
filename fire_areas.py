from datetime import datetime
import os
from owslib.wms import WebMapService

from fire_utils import (
    generate_datetimes,
    compute_grid_for_bbox,
    split_bbox,
    calculate_image_size,
    get_wms_image,
    load_image,
    detect_areas,
    calculate_polygon_areas,
    create_geodataframe,
    create_shapefile,
    update_shapefile
)

def process_fire_grid(
    bbox: tuple,
    start: str,
    end: str,
    shapefile_path: str,
    step_minutes: int = 10,
    pixel_size_m: float = 500.0,
    base_px: int = 500,
    detection_params: dict = None
):
    """
    Iterate over a large bounding box divided into sub-bboxes and send fire detections to AGOL.

    Parameters
    ----------
    bbox : tuple
        (lon_min, lat_min, lon_max, lat_max) of the area of interest.
    start : str
        Start date and time in ISO format ('YYYY-MM-DDTHH:MM:SS').
    end : str
        End date and time in ISO format ('YYYY-MM-DDTHH:MM:SS').
    shapefile_path : str
        Path to the output shapefile.
    step_minutes : int, optional
        Temporal interval in minutes (default=10).
    pixel_size_m : float, optional
        Target spatial resolution in meters (default=500).
    base_px : int, optional
        Base pixel width/height of each subimage (default=500).
    detection_params : dict, optional
        Extra parameters for fire detection, forwarded to `fire_areas`.
        Accepted keys:
            - method : str, detection method ('rgb', 'hsv' [default], or 'combined').
            - upscale_factor : int, scaling factor for subpixel simulation (default=1).
            - blur_sigma : float, sigma for Gaussian blur (default=3.0).
            - threshold_value : float, threshold (0–1) after blur (default=0.7).
            - tol : int, tolerance for RGB detection (default=40).
        Example:
            detection_params = {
                "method": "combined",
                "upscale_factor": 2,
                "blur_sigma": 2.5
            }

    Notes
    -----
    - The bbox is split into sub-bboxes such that each subimage covers roughly
      (base_px * pixel_size_m) meters.
    - The function prints progress for each (time, sub-bbox) combination.
    - Errors are caught and printed but do not stop execution.
    """
    
    # generate all timestamps
    start, end = datetime.fromisoformat(start), datetime.fromisoformat(end) 
    times = generate_datetimes(start, end, step_minutes)

    # split bbox into sub-bboxes
    n_rows, n_cols = compute_grid_for_bbox(bbox, pixel_size_m=pixel_size_m, base_px=base_px)
    sub_boxes = split_bbox(bbox, n_rows, n_cols)

    print(f"🚀 Starting processing: {len(times)} timestamps × {len(sub_boxes)} sub-bboxes")

    for i, time in enumerate(times, start=1):
        print(f"\n⏱️ Time {i}/{len(times)} → {time}")

        for j, sbox in enumerate(sub_boxes, start=1):
            print(f"   📍 Sub-bbox {j}/{len(sub_boxes)}: {sbox}")
            try:
                fire_areas(sbox, time, shapefile_path, detection_params=detection_params)
            except Exception as e:
                print(f"   ❌ Error at {time}, sub-bbox {j}: {e}")

    print("\n✅ Processing completed.")

def fire_areas(bbox: tuple, date_str: str, shapefile_path: str, detection_params: dict = None):
    """
    🔥 Wildfire monitoring using WMS images from EUMETSAT.

    This function downloads images from the EUMETSAT WMS service, detects
    burned areas, converts them into polygons, and updates a shapefile with
    their temporal evolution.

    Source
    ------
    WMS_URL:       https://view.eumetsat.int/geoserver/wms
    TARGET_LAYER:  mtg_fd:rgb_firetemperature
    QUICK GUIDE:   https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide

    Parameters
    ----------
    bbox : tuple
        Bounding box as (lon_min, lat_min, lon_max, lat_max).
    date_str : str
        Date and time in format 'YYYY-MM-DDTHH:MM:SSZ'.
    shapefile_path : str
        Path to the output shapefile.
    detection_params : dict, optional
        Extra parameters for fire detection.
        Accepted keys:
            - method : str, detection method ('rgb', 'hsv' [default], or 'combined').
            - upscale_factor : int, scaling factor for subpixel simulation (default=1).
            - blur_sigma : float, sigma for Gaussian blur (default=3.0).
            - threshold_value : float, threshold (0–1) after blur (default=0.7).
            - tol : int, tolerance for RGB detection (default=40).
        Example:
            detection_params = {
                "method": "rgb",
                "upscale_factor": 2,
                "blur_sigma": 2.5
            }
    """

    # Default detection settings
    params = {
        "method": "hsv",
        "upscale_factor": 4,
        "blur_sigma": 3.0,
        "threshold_value": 0.7,
        "tol": 40
    }
    if detection_params:
        params.update(detection_params)
    
    # 🌐 Source WMS (not edit)
    WMS_URL =       'https://view.eumetsat.int/geoserver/wms'
    TARGET_LAYER =  'mtg_fd:rgb_firetemperature'

    # 🌐 Connect to WMS service
    print("🔌 Connecting to WMS...")
    wms = WebMapService(WMS_URL, version="1.3.0")

    # 🖼️ Download image from WMS
    size = calculate_image_size(bbox)
    img_bytes = get_wms_image(wms, TARGET_LAYER, bbox, date_str, size)

    # 🧠 Process image and get contours
    rgb, transform, crs = load_image(img_bytes)
    contours, adjusted_transform = detect_areas(
        rgb,
        transform,
        method=params["method"],
        upscale_factor=params["upscale_factor"],
        blur_sigma=params["blur_sigma"],
        threshold_value=params["threshold_value"],
        tol=params["tol"]
    )
    if not contours:
        print("⚠️ No contours detected.")
        return

    # 🔲 Generated polygons and create GeoDataFrame
    polygons, areas = calculate_polygon_areas(contours, adjusted_transform)
    if not polygons:
        print("⚠️ No valid polygons generated.")
        return

    new_gdf = create_geodataframe(polygons, areas, crs, date_str)

    # 💾 Create or updated shapefile
    if not os.path.exists(shapefile_path):
        create_shapefile(new_gdf, shapefile_path)
    else:
        update_shapefile(new_gdf, shapefile_path)