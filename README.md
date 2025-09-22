# Wildfire Monitoring using EUMETSAT WMS Images

🔥🗺️ This project provides tools to monitor wildfires using Fire Temperature RGB satellite images from EUMETSAT WMS.

The detection process includes options for RGB, HSV, or combined masks, Gaussian blurring for soft boundaries, and optional upscaling to simulate subpixel resolution. Detected burned areas are converted into polygons that can be integrated into GIS workflows for mapping and analysis.

The repository includes a Jupyter Notebook for quick testing, as well as scripts to run the detection directly in QGIS and to install required dependencies for QGIS integration.

---

## Features

- Downloads Fire Temperature RGB images from EUMETSAT's WMS endpoint.
- Detects burned areas from the imagery (resolution 500 m/pixel).
- Converts detected burned regions into polygons and exports to a shapefile.
- Updates an existing shapefile to reflect the temporal changes in wildfire extent.
- Includes a QGIS widget for interactive use.

---

## Data Source

- **WMS URL:** `https://view.eumetsat.int/geoserver/wms`
- **Target Layer:** `mtg_fd:rgb_firetemperature`
- **Quick Guide:** [EUMETSAT Fire Temperature RGB Quick Guide](https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide)

---

## QGIS Integration

Two helper scripts are provided for use inside QGIS:
```bash
QGIS_install_requirements.py
QGIS_WFMonitoring.py
```
### Installation

1. Open an **OSGeo4W Shell** (for Windows users).  
2. Navigate to the project directory containing the scripts:  
   ```bash
   cd r'C:\Users\...\fire_areas'

3. Run the installer script to ensure dependencies are available:
   ```bash
   python QGIS_install_requirements.py

### Usage in QGIS

1. Open the **QGIS Python Console**.  
2. Load the script file `QGIS_WFMonitoring.py` directly into the console (menu → “Open Script…” or drag-and-drop).  
3. Press the **▶️ Run Script** button in the console.  

4. A custom window will appear with:
- Current canvas extent (lon/lat).  
- Date/time selectors.  
- Output folder selector.
- 'Advanced' options for tunning parameters.
- Buttons: **About** and **Run**.  

5. After execution, results are automatically added to the QGIS map (TOC).

💡 You can also add the [EUMETSAT WMS directly in QGIS](https://user.eumetsat.int/resources/user-guides/eumet-view-web-map-service-access-through-qgis)
 to visually contrast the polygons with the satellite images.

---

## Main Use and Benefits

- Useful for fire monitoring during both day and night, even for fires smaller than the pixel size.
- Provides qualitative information on fire intensity (temperature): cooler fires appear more red, hotter fires appear yellow to white.
- During the day, ice and water clouds are seen in the image in different colours (green for ice, blue for water).

## Limitations

- Fires are seen only in cloud-free areas.
- Smoke is usually not detectable with this RGB (unless very thick with larger particles).
- Burnt areas are not well represented.
- Clouds are not seen at night.
- Dry regions and hot land surfaces may both appear in red hues.
- Red component can saturate at a relatively low temperature → false alarms may appear as red pixels.

📖 More details in the [EUMETSAT Fire Temperature RGB Quick Guide](https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide)

---

## Acknowledgements

This project has been developed as part of a **Short-Term Scientific Mission (STSM)** within the framework of the [NERO – European Network for Earth Observation in Science and Innovation](https://nero-network.eu/).  

Special thanks to:  
- The **NERO programme**, for supporting scientific exchange and collaboration.  
- **EUMETSAT** for providing open access to satellite imagery and the Fire Temperature RGB product.  
- The **QGIS community**, whose open-source ecosystem allows seamless integration of satellite-based fire monitoring tools.  
- All contributors and colleagues who provided feedback, testing, and insights during the development of the wildfire monitoring workflow.  

This work highlights the importance of collaboration between Earth Observation scientists, developers, and the open-source GIS community to deliver practical tools for wildfire detection and monitoring.
