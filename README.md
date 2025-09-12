# Wildfire Monitoring using EUMETSAT WMS Images

🔥 This project provides scripts to monitor wildfires by downloading and processing WMS images from EUMETSAT. It detects burned areas, converts them into polygons, and updates a shapefile to track their temporal evolution.

---

## Overview

The main script downloads satellite imagery from the EUMETSAT Web Map Service (WMS) and processes the data to identify and map wildfire-affected areas. This tool is designed to be integrated into GIS software workflows for wildfire monitoring and analysis.

---

## Features

- Downloads Fire Temperature RGB images from EUMETSAT's WMS endpoint.
- Detects burned areas from the imagery (resolution 500 m/pixel).
- Converts detected burned regions into polygons and exports to a shapefile.
- Updates an existing shapefile to reflect the temporal changes in wildfire extent.

---

## Data Source

- **WMS URL:** `https://view.eumetsat.int/geoserver/wms`
- **Target Layer:** `mtg_fd:rgb_firetemperature`
- **Quick Guide:** [EUMETSAT Fire Temperature RGB Quick Guide](https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide)


