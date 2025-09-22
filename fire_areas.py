from datetime import datetime
import numpy as np
import os
from owslib.wms import WebMapService

# Nota: Asegúrate de que fire_utils.py contiene las funciones correctas
# que se han mantenido sin cambios en este flujo de trabajo.
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
    Iterate over a large bounding box divided into sub-bboxes and send fire detections to shapefile.

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
            - threshold_value : float, threshold (0–1) after blur (default=0.8).
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

    consecutive_false = 0

    for i, time in enumerate(times, start=1):
        print(f"\n⏱️ Time {i}/{len(times)} → {time}")

        all_false_this_time = True
        
        polygons_this_time = []
        areas_this_time = []

        for j, sbox in enumerate(sub_boxes, start=1):
            print(f"   📍 Sub-bbox {j}/{len(sub_boxes)}: {sbox}")
            try:
                res = fire_areas(sbox, time, detection_params=detection_params)
                if res and res != "false_image" and res[0] is not None:
                    polygons, areas, crs = res
                    polygons_this_time.extend(polygons)
                    areas_this_time.extend(areas)
                    all_false_this_time = False
                elif res == 'false_image':
                    all_false_this_time = True
                else:
                    all_false_this_time = False
            except Exception as e:
                print(f"   ❌ Error at {time}, sub-bbox {j}: {e}")
                all_false_this_time = False

        if polygons_this_time:
            new_gdf = create_geodataframe(polygons_this_time, areas_this_time, 'EPSG:4326', time)

            if new_gdf.empty:
                print("⚠️ Warning: No wildfires were detected in the area for the dates range.")
                return

            # 💾 Create or update shapefile
            if not os.path.exists(shapefile_path):
                create_shapefile(new_gdf, shapefile_path)
            else:
                update_shapefile(new_gdf, shapefile_path)

        if all_false_this_time:
            consecutive_false += 1
            print(f"🔕 All sub-bboxes false image at {time} (consecutive={consecutive_false})")
        else:
            consecutive_false = 0

        if consecutive_false >= 2:
            print("⛔ Two consecutive false image time iterations → stopping process early.")
            break

def fire_areas(bbox: tuple, date_str: str, detection_params: dict = None):
    """
    🔥 Wildfire monitoring using WMS images from EUMETSAT.

    This function downloads images from the EUMETSAT WMS service, detects
    burned areas, converts them into polygons.

    Returns:
    - (polygons, areas, crs) if successful, None otherwise.
    """
    
    # Default detection settings
    params = {
        "method": "hsv",
        "upscale_factor": 4,
        "blur_sigma": 3.0,
        "threshold_value": 0.8,
        "tol": 40
    }
    if detection_params:
        params.update(detection_params)
    
    # 🌐 Source WMS (not edit)
    WMS_URL = 'https://view.eumetsat.int/geoserver/wms'
    TARGET_LAYER = 'mtg_fd:rgb_firetemperature'

    # 🌐 Connect to WMS service
    print("🔌 Connecting to WMS...")
    wms = WebMapService(WMS_URL, version="1.3.0")

    # 🖼️ Download image from WMS
    size = calculate_image_size(bbox)
    img_bytes = get_wms_image(wms, TARGET_LAYER, bbox, date_str, size)

    # 🧠 Process image and get contours
    rgb, transform, crs = load_image(img_bytes)

    # ⛔ Filter for white/false image
    arr = np.array(rgb)
    if arr.size == 0 or np.nanstd(arr) == 0 or np.nanmax(arr) == np.nanmin(arr):
        print(f"⚠️ Blank/uniform image detected at {date_str} → skipped.")
        return 'false_image'
    
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
        
    return polygons, areas, crs