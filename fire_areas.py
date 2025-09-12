from datetime import datetime
import os
from owslib.wms import WebMapService

from fire_utils import (
    calculate_image_size,
    get_wms_image,
    load_image,
    detect_areas,
    calculate_polygon_areas,
    create_geodataframe,
    create_shapefile,
    update_shapefile
)

def fire_areas(bbox:tuple, date_str:str, shapefile_path:str):
    """
    🔥 Wildfire monitoring using WMS images from EUMETSAT

    This script downloads images from:
        WMS_URL:       https://view.eumetsat.int/geoserver/wms
        TARGET_LAYER:  mtg_fd:rgb_firetemperature
        QUICK GUIDE:   https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide

    Then it detects burned areas, converts them to polygons, and updates a shapefile with their temporal evolution.

    Parameters:
    bbox (tuple):   Bounding box as 4 values: (LON_MIN, LAT_MIN, LON_MAX, LAT_MAX)
    date_str (str):   Date and time in format: 'YYYY-MM-DDTHH:MM:SSZ'
    shapefile_path (str):  Path to the output shapefile
    """
    
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
    contours, adjusted_transform = detect_areas(rgb, transform, points=False)
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