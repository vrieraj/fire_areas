from qgis.utils import iface
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QDateTimeEdit,
    QPushButton, QLineEdit, QFileDialog, QHBoxLayout, QMessageBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QTabWidget
)
from PyQt5.QtCore import QDateTime, Qt
import os
import sys

# import from fire_areas
from fire_areas import process_fire_grid


def get_current_bbox():
    """Get bbox of current QGIS canvas, rounded to 4 decimals."""
    extent = iface.mapCanvas().extent()
    return (
        round(extent.xMinimum(), 4),
        round(extent.yMinimum(), 4),
        round(extent.xMaximum(), 4),
        round(extent.yMaximum(), 4),
    )


class FireMonitorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("🔥 EUMETSAT Wildfire Monitoring – Fire Temperature RGB")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # --- Coordinates ---
        self.label_bbox = QLabel("Current extent:")
        self.coords_label = QLabel("")
        self.layout.addWidget(self.label_bbox)
        self.layout.addWidget(self.coords_label)
        iface.mapCanvas().extentsChanged.connect(self.update_bbox_labels)

        # --- Date/time selectors ---
        self.start_dt = QDateTimeEdit()
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setCalendarPopup(True)
        self.start_dt.setDateTime(QDateTime.currentDateTime())
        self.start_dt.setMaximumDateTime(QDateTime.currentDateTime())

        self.end_dt = QDateTimeEdit()
        self.end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setCalendarPopup(True)
        self.end_dt.setDateTime(QDateTime.currentDateTime())
        self.end_dt.setMaximumDateTime(QDateTime.currentDateTime())

        dt_layout = QHBoxLayout()
        dt_layout.addWidget(QLabel("Start:"))
        dt_layout.addWidget(self.start_dt)
        dt_layout.addWidget(QLabel("End:"))
        dt_layout.addWidget(self.end_dt)
        self.layout.addLayout(dt_layout)

        self.start_dt.dateTimeChanged.connect(self.validate_datetimes)
        self.end_dt.dateTimeChanged.connect(self.validate_datetimes)

        # --- Folder selector ---
        self.folder_label = QLabel("Output folder:")
        self.folder_input = QLineEdit()
        self.folder_button = QPushButton("Browse...")
        self.folder_button.clicked.connect(self.select_output_folder)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_button)
        self.layout.addWidget(self.folder_label)
        self.layout.addLayout(folder_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(self.show_about)

        self.custom_button = QPushButton("Custom")
        self.custom_button.clicked.connect(self.show_custom_tab)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self.run_script)

        btn_layout.addWidget(self.about_button)
        btn_layout.addWidget(self.custom_button)
        btn_layout.addWidget(self.run_button)
        self.layout.addLayout(btn_layout)

        # --- Tabs for Custom and Terminal ---
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        self.tabs.hide()  # hidden until user opens custom or runs script

                # --- Custom parameters tab ---
        self.custom_panel = QWidget()
        custom_layout = QVBoxLayout()

        def add_param_row(bold_text, description, widget):
            row = QVBoxLayout()

            # labels in one line: left (bold) + right (normal)
            labels_layout = QHBoxLayout()
            label_bold = QLabel(f"<b>{bold_text}</b>")
            label_desc = QLabel(description)
            label_desc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            labels_layout.addWidget(label_bold)
            labels_layout.addWidget(label_desc, 1)  # stretch to push right
            row.addLayout(labels_layout)

            # widget input below
            row.addWidget(widget)
            custom_layout.addLayout(row)

        # Method
        self.method_box = QComboBox()
        self.method_box.addItems(["hsv", "rgb", "combined"])
        add_param_row("Method", "Detection type: RGB, HSV, or both (default=hsv)", self.method_box)

        # Upscale factor
        self.upscale_spin = QSpinBox()
        self.upscale_spin.setRange(1, 10)
        self.upscale_spin.setValue(4)
        add_param_row("Upscale factor", "Controls subpixel simulation (default=4)", self.upscale_spin)

        # Blur sigma
        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.1, 10.0)
        self.blur_spin.setSingleStep(0.1)
        self.blur_spin.setValue(3.0)
        add_param_row("Blur sigma", "Controls edge smoothing (default=3.0)", self.blur_spin)

        # Threshold value
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 1.0)
        self.thresh_spin.setSingleStep(0.05)
        self.thresh_spin.setValue(0.7)
        add_param_row("Threshold value", "Sets fire detection sensitivity (default=0.7)", self.thresh_spin)

        # RGB tolerance
        self.tol_spin = QSpinBox()
        self.tol_spin.setRange(0, 255)
        self.tol_spin.setValue(40)
        add_param_row("RGB tolerance", "Tolerance for RGB matching (default=40)", self.tol_spin)

        # Min area (ha)
        self.min_area_spin = QDoubleSpinBox()
        self.min_area_spin.setRange(0.1, 100.0)
        self.min_area_spin.setSingleStep(0.1)
        self.min_area_spin.setValue(1.0)
        add_param_row("Min area (ha)", "Minimum polygon area retained (default=1 ha)", self.min_area_spin)

        self.custom_panel.setLayout(custom_layout)
        self.tabs.addTab(self.custom_panel, "Custom parameters")

        # --- Terminal tab ---
        self.terminal_panel = QTextEdit()
        self.terminal_panel.setReadOnly(True)
        self.tabs.addTab(self.terminal_panel, "Terminal")

        # redirect stdout to QTextEdit
        self.stdout_backup = sys.stdout
        sys.stdout = self

        # Initial bbox
        self.update_bbox_labels()

    # --- Redirect prints to terminal widget ---
    def write(self, text):
        if self.terminal_panel.isVisible():
            self.terminal_panel.append(text.strip())
        self.stdout_backup.write(text)

    def flush(self):
        pass

    # --- Show tabs ---
    def show_custom_tab(self):
        self.tabs.show()
        self.tabs.setCurrentWidget(self.custom_panel)

    def run_script(self):
        self.tabs.show()
        self.tabs.setCurrentWidget(self.terminal_panel)
        self.terminal_panel.clear()

        bbox = get_current_bbox()
        start = self.start_dt.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        end = self.end_dt.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        folder = self.folder_input.text()

        if not folder:
            QMessageBox.warning(self, "Error", "Please select an output folder.")
            return

        shapefile_path = os.path.join(folder, "wildfires.shp")

        detection_params = {
            "method": self.method_box.currentText(),
            "upscale_factor": self.upscale_spin.value(),
            "blur_sigma": self.blur_spin.value(),
            "threshold_value": self.thresh_spin.value(),
            "tol": self.tol_spin.value(),
            "min_area_ha": self.min_area_spin.value()
        }

        print(f"🚀 Running fire detection for {bbox} from {start} to {end}")
        process_fire_grid(bbox, start, end, shapefile_path, detection_params=detection_params)
        iface.addVectorLayer(shapefile_path, "Wildfires", "ogr")

    # --- Other methods ---
    def update_bbox_labels(self):
        lon_min, lat_min, lon_max, lat_max = get_current_bbox()
        self.coords_label.setText(
            f"lon min: {lon_min}   lat min: {lat_min}   "
            f"lon max: {lon_max}   lat max: {lat_max}"
        )

    def validate_datetimes(self):
        now = QDateTime.currentDateTime()
        start = self.start_dt.dateTime()
        end = self.end_dt.dateTime()
        if start > now:
            self.start_dt.setDateTime(now)
        if end > now:
            self.end_dt.setDateTime(now)
        if end < start:
            self.end_dt.setDateTime(start)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.folder_input.setText(folder)

    def show_about(self):
        text = (
            "<b>EUMETSAT Fire Temperature RGB – Wildfire Monitoring</b><br><br>"
            "Images are provided through <a href='https://view.eumetsat.int/'>EUMETSAT View</a> "
            "and can also be accessed via WMS in QGIS: "
            "<a href='https://user.eumetsat.int/resources/user-guides/eumet-view-web-map-service-access-through-qgis'>"
            "WMS access guide</a>.<br><br>"
            "<b>Main use and benefits:</b><br>"
            "- Useful for fire monitoring during both day and night, even for fires smaller than the pixel size.<br>"
            "- Provides qualitative information on fire intensity (temperature): cooler fires appear red, hotter fires yellow to white.<br>"
            "- During the day, ice and water clouds are visible: ice in green shades, water in blue.<br><br>"
            "<b>Limitations:</b><br>"
            "- Fires only visible in cloud-free areas.<br>"
            "- Smoke usually not detected (unless very thick).<br>"
            "- Burnt areas not well represented.<br>"
            "- Clouds are not visible at night.<br>"
            "- Dry/hot surfaces may appear as red (false alarms possible).<br>"
            "- Red channel saturates at relatively low temperatures.<br><br>"
            "See the <a href='https://user.eumetsat.int/resources/user-guides/fire-temperature-rgb-quick-guide'>"
            "Quick Guide</a> for full details."
        )
        QMessageBox.information(self, "About", text)


# Launch widget
widget = FireMonitorWidget()
widget.show()