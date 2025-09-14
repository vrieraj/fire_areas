import cv2
from datetime import timedelta
import geopandas as gpd
import pandas as pd
import numpy as np
from pyproj import Geod
from rasterio.io import MemoryFile
from rasterio.transform import xy
from shapely.geometry import Polygon
from shapely.ops import unary_union

def generate_datetimes(start, end, step_minutes):
    """
    Genera una lista de fechas a intervalos de 10 minutos entre `start` y `end`.
    """
    current = start
    times = []
    while current <= end:
        times.append(current.isoformat() + 'Z')  # Formato ISO con 'Z'
        current += timedelta(minutes=step_minutes)
    return times

## BBOX -> GRID ##

def compute_grid_for_bbox(bbox: tuple, pixel_size_m: float = 500.0, base_px: int = 500):
    lon_min, lat_min, lon_max, lat_max = bbox
    geod = Geod(ellps="WGS84")

    # dimensiones del bbox en metros
    _, _, width_m = geod.inv(lon_min, (lat_min+lat_max)/2, lon_max, (lat_min+lat_max)/2)
    _, _, height_m = geod.inv((lon_min+lon_max)/2, lat_min, (lon_min+lon_max)/2, lat_max)

    sub_width_m = base_px * pixel_size_m
    sub_height_m = base_px * pixel_size_m

    n_cols = max(1, int(round(width_m / sub_width_m)))
    n_rows = max(1, int(round(height_m / sub_height_m)))

    return n_rows, n_cols

def split_bbox(bbox, n_rows, n_cols):
    xmin, ymin, xmax, ymax = bbox
    dx = (xmax - xmin) / n_cols
    dy = (ymax - ymin) / n_rows

    sub_boxes = []
    for i in range(n_rows):
        for j in range(n_cols):
            x0 = xmin + j * dx
            y0 = ymin + i * dy
            x1 = x0 + dx
            y1 = y0 + dy
            sub_boxes.append((x0, y0, x1, y1))
    return sub_boxes

## WMS IMAGE DOWNLOAD UTILITIES ##

def calculate_image_size(bbox:tuple, pixel_size_m:float=500.0):
    """
    Calculate the aspect ratio of the image based in bbox.

    Parameters:
    bbox (tuple): bounding box of the area of interest in format (lon_min, lat_min, lon_max, lat_max)
    base_size (int): width of the WMS image in pixels (default 300)

    Returns:
    tuple: (width, height) in pixels.
    """
    lon_min, lat_min, lon_max, lat_max = bbox
    geod = Geod(ellps="WGS84")

    _, _, width_m = geod.inv(lon_min, (lat_min+lat_max)/2,
                             lon_max, (lat_min+lat_max)/2)

    _, _, height_m = geod.inv((lon_min+lon_max)/2, lat_min,
                              (lon_min+lon_max)/2, lat_max)

    width_px = int(round(width_m / pixel_size_m))
    height_px = int(round(height_m / pixel_size_m))

    return (width_px, height_px)

def get_wms_image(wms:str, target_layer:str, bbox:tuple, time:str, size:tuple, epsg='EPSG:4326', format='image/geotiff'):
    """
    Request an image from a WMS (Web Map Service) server using the GetMap request.

    Arguments:
    - wms (str): URL of the Web Map Service.
    - target_layer (str): Name of the target layer to request from the WMS.
    - bbox (tuple): Bounding box in the format (lon_min, lat_min, lon_max, lat_max).
    - time (str): Timestamp for the requested data in the format 'YYYY-MM-DDTHH:MM:SSZ'.
    - size (tuple): Output image size in pixels as (width_px, height_px).
    - epsg (str): Coordinate reference system identifier (default is 'EPSG:4326').
    - format (str): Image output format (default is 'image/geotiff').

    Returns:
    - bytes: The raw image data returned by the WMS server using the GetMap request.
    """

    print(f"📥 Request image for: {time}")
    try:
        img = wms.getmap(
            layers=[target_layer],
            styles=[''],
            srs=epsg,
            bbox=bbox,
            time=time,
            size=size,
            format=format,
            transparent=True
        )
    except Exception as error:
        print(f"❌ Request error for {time}:\n{error}")

    print(f"✅ Image for {time} download succesfull.")
    return img

def load_image(img_bytes):
    """
    Load an image from WMS binary data and return its RGB array, affine transform, and CRS.

    Arguments:
    - img_bytes (bytes): Binary image data returned by a WMS GetMap request (e.g., GeoTIFF format).

    Returns:
    - rgb (np.ndarray): 3D NumPy array representing the RGB image (uint8).
    - transform (Affine): Affine transformation mapping pixel coordinates to spatial coordinates.
    - crs (CRS): Coordinate Reference System of the image.
    """
    with MemoryFile(img_bytes) as memfile:
        with memfile.open() as dataset:
            r = dataset.read(1)
            g = dataset.read(2)
            b = dataset.read(3)
            rgb = np.dstack((r, g, b)).astype(np.uint8)
            transform = dataset.transform
            crs = dataset.crs
    return rgb, transform, crs

## DETECTION AND CALCULATION OF AREAS OF INTEREST ##

def detect_areas(rgb: np.ndarray, transform, points=False, upscale_factor=4, blur_sigma=4.0, threshold_value=0.8):
    """
    Detect areas from an RGB image using HSV color thresholding, with subpixel interpolation via blurring
    and/or resizing (bicubic interpolation). Returns either contours or geo-referenced points.

    Args:
        rgb (np.ndarray): RGB image (H, W, 3)
        transform (Affine): Affine transform of original image
        points (bool): Return list of geocoordinates if True
        upscale_factor (int): Scaling factor to simulate subpixel resolution
        blur_sigma (float): Sigma value for Gaussian blur
        threshold_value (float): Threshold value (0–1) for interpolated mask

    Returns:
        If points=True: List of (lon, lat) coordinates
        If points=False: Tuple (contours, adjusted_transform)
    """
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

    # Create color masks
    mask_white = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 50, 255]))
    mask_yellow = cv2.inRange(hsv, np.array([20, 100, 100]), np.array([40, 255, 255]))
    mask_orange = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([25, 255, 255]))

    # Combine masks and clean
    mask = cv2.bitwise_or(mask_white, mask_yellow)
    mask = cv2.bitwise_or(mask, mask_orange)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Step 1: Convert to float32 and normalize
    mask_f = mask.astype(np.float32) / 255.0

    # Step 2: Upscale to simulate subpixels
    if upscale_factor > 1:
        mask_f = cv2.resize(mask_f, None, fx=upscale_factor, fy=upscale_factor, interpolation=cv2.INTER_CUBIC)

    # Step 3: Apply Gaussian blur to generate soft edges
    mask_f = cv2.GaussianBlur(mask_f, (0, 0), sigmaX=blur_sigma, sigmaY=blur_sigma)

    # Step 4: Threshold to simulate soft boundary
    _, mask_thresh = cv2.threshold(mask_f, threshold_value, 1.0, cv2.THRESH_BINARY)

    # Step 5: Convert back to uint8 for contour detection
    mask_uint8 = (mask_thresh * 255).astype(np.uint8)

    if points:
        ys, xs = np.where(mask_uint8 > 0)
        adjusted_transform = transform * transform.scale(1 / upscale_factor, 1 / upscale_factor)
        geo_coords = [xy(adjusted_transform, y, x, offset='center') for y, x in zip(ys, xs)]
        return geo_coords

    # Step 6: Get contours from smooth mask
    contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    # Step 7: Adjust transform for upscaled image
    adjusted_transform = transform * transform.scale(1 / upscale_factor, 1 / upscale_factor)

    return contours, adjusted_transform

def calculate_polygon_areas(contours, transform, min_area_ha:float=1.0, simplify_tolerance:float=0.001):
    """
    Convert pixel-based contours into georeferenced polygons, simplify geometry, and calculate area in hectares.

    Arguments:
    - contours (List[np.ndarray]): List of OpenCV contours (pixel coordinates) from binary masks.
    - transform (Affine): Affine transform used to convert pixel coordinates to geographic (lon, lat).
    - min_area_ha (float): Minimum area (in hectares) to retain a polygon. Smaller polygons are discarded.
    - simplify_tolerance (float): Simplification tolerance in degrees. For example, 0.001 ≈ 100 meters.

    Returns:
    - polygons (List[shapely.Polygon]): Valid, simplified polygons in geographic coordinates.
    - areas (List[float]): Corresponding areas for each polygon in hectares (ha).
    """

    polygons = []
    areas = []
    geod = Geod(ellps="WGS84")

    for contour in contours:
        coords_pix = contour[:, 0, :]
        coords_geo = [xy(transform, int(y), int(x)) for x, y in coords_pix]

        # Ensure that contour is closed
        if coords_geo[0] != coords_geo[-1]:
            coords_geo.append(coords_geo[0])

        poly = Polygon(coords_geo)

        if not poly.is_valid or poly.is_empty:
            continue

        # 🎯 SIMPLIFY poligon
        poly_simple = poly.simplify(simplify_tolerance, preserve_topology=True)

        if not poly_simple.is_valid or poly_simple.is_empty:
            continue

        # Calculate area
        area_m2, _ = geod.geometry_area_perimeter(poly_simple)
        area_ha = abs(area_m2) / 10_000  # m² → ha

        if area_ha >= min_area_ha:
            polygons.append(poly_simple)
            areas.append(area_ha)

    return polygons, areas

## SHAPEFILE WORKFLOW ##

def create_geodataframe(polygons, areas, crs, time):
    """
    Create a GeoDataFrame from a polygons list.

    Returns:
    - gdf(gpd.GeoDataFrame): geodataframe with the attributes 'time' and 'area'
    """
    gdf = gpd.GeoDataFrame(geometry=polygons, crs=crs)
    gdf["time"] = time
    gdf["area"] = areas
    return gdf

def create_shapefile(new_gdf:gpd.GeoDataFrame, shapefile_path:str):
    """
    Create a shapefile with the new polygons detected. 

    Arguments:
    - new_gdf(gpd.GeoDataFrame): geodataframe from the function 'create_geodataframe(polygons, areas, crs, time)'
    - shapefile_path(str): path to the new shapefile

    Output:
    - The shapefile at `shapefile_path` is created in-place with the new entries.
    - Console messages summarize the actions taken.
    """
    new_gdf = new_gdf.copy()
    new_gdf["fire"] = 1
    new_gdf["time_area"] = new_gdf["area"].round(2)
    new_gdf["acc_area"] = new_gdf["area"].round(2)
    new_gdf.to_file(shapefile_path)
    print(f"📁 Shapefile creado: {shapefile_path}")

def update_shapefile(new_gdf:gpd.GeoDataFrame, shapefile_path:str):
    """
    Updates a wildfire shapefile with newly detected polygons, preserving temporal history.

    For each new polygon in `new_gdf`:
    - If it overlaps with an existing fire (same 'fire' ID), it is merged with the last known geometry.
    - If there is no overlap, a new fire is created with a new 'fire' ID.
    - 'time_area' stores the area (in hectares) of the newly added geometry (excluding overlaps).
    - 'acc_area' is the accumulated burned area for that fire up to the current timestamp.
    - Previous fire records are preserved to maintain a temporal history (no deletions).

    Arguments:
    - new_gdf (gpd.GeoDataFrame): GeoDataFrame containing new polygons to add. Must include 'geometry' and 'time' columns.
    - shapefile_path (str): Path to the existing shapefile to be updated.

    Notes:
    - Geometries are simplified via unary union when overlapping.
    - Areas are calculated geodetically using the WGS84 ellipsoid.
    - If the shapefile does not contain a 'fire' column, it will be created or renamed from 'id'.

    Output:
    - The shapefile at `shapefile_path` is updated in-place with the new entries.
    - Console messages summarize the actions taken.
    """

    existing_gdf = gpd.read_file(shapefile_path)
    updated_gdf = existing_gdf.copy()
    geod = Geod(ellps="WGS84")

    # 🔧 Corregir nombre si 'fire' no existe
    if 'fire' not in existing_gdf.columns:
        if 'id' in existing_gdf.columns:
            existing_gdf = existing_gdf.rename(columns={"id": "fire"})
        else:
            existing_gdf["fire"] = 1

    # Inicializar siguiente ID disponible
    next_fire_id = existing_gdf["fire"].max() + 1

    for idx, new_row in new_gdf.iterrows():
        new_geom = new_row.geometry
        time_tag = new_row["time"]

        if new_geom.is_empty or not new_geom.is_valid:
            print(f"⚠️ Invalid geometry or empty in index {idx}. Skipped.")
            continue

        found_overlap = False

        # 🔍 Buscar incendios existentes que solapen
        for fire_id in existing_gdf["fire"].unique():
            fire_history = updated_gdf[updated_gdf["fire"] == fire_id]
            last_record = fire_history.sort_values("time").iloc[-1]
            fire_geom = last_record.geometry

            if new_geom.intersects(fire_geom):
                # 🔁 Fusionar geometrías
                combined_geom = unary_union([fire_geom, new_geom])

                # Área del nuevo polígono
                time_area_m2, _ = geod.geometry_area_perimeter(new_geom)
                time_area_ha = round(abs(time_area_m2) / 10_000, 2)

                # Nueva área acumulada
                combined_area_m2, _ = geod.geometry_area_perimeter(combined_geom)
                acc_area_ha = round(abs(combined_area_m2) / 10_000, 2)

                # Obtener área acumulada anterior
                prev_acc_area = last_record["acc_area"]
                if np.isclose(prev_acc_area, acc_area_ha, atol=0.01):
                    print(f"⚠️ Ignored fire={fire_id} in {time_tag}: no changes in area.")
                    found_overlap = True
                    break

                new_entry = gpd.GeoDataFrame({
                    "time": [time_tag],
                    "fire": [fire_id],
                    "geometry": [combined_geom],
                    "time_area": [time_area_ha],
                    "acc_area": [acc_area_ha]
                }, crs=existing_gdf.crs)

                updated_gdf = pd.concat([updated_gdf, new_entry], ignore_index=True)
                print(f"🔁 Fire={fire_id} updated | time_area={time_area_ha:.2f} ha | acc_area={acc_area_ha:.2f} ha")
                found_overlap = True
                break

        if not found_overlap:
            # ➕ Crear nuevo incendio
            time_area_m2, _ = geod.geometry_area_perimeter(new_geom)
            time_area_ha = abs(time_area_m2) / 10_000

            new_entry = gpd.GeoDataFrame({
                "time": [time_tag],
                "fire": [next_fire_id],
                "geometry": [new_geom],
                "time_area": [time_area_ha],
                "acc_area": [time_area_ha]
            }, crs=existing_gdf.crs)

            updated_gdf = pd.concat([updated_gdf, new_entry], ignore_index=True)
            print(f"➕ New fire added: fire={next_fire_id} | time_area={time_area_ha:.2f} ha")
            next_fire_id += 1

    # 🧹 Reordenar columnas
    ordered_cols = ["fire", "time", "time_area", "acc_area", "geometry"]
    for col in ordered_cols:
        if col not in updated_gdf.columns:
            updated_gdf[col] = None

    updated_gdf = updated_gdf[ordered_cols]

    # 💾 Guardar shapefile
    updated_gdf.to_file(shapefile_path)
    print(f"✅ Shapefile updated: {shapefile_path}")