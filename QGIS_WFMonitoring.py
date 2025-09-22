import os
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateTimeEdit,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QFrame,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QWidget,
)
from qgis.utils import iface
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

# --- Clase para el panel desplegable ---
class CollapsiblePanel(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Usamos un QLabel que actúa como un botón para el colapso
        self.toggle_label = QLabel(title)
        self.toggle_label.setStyleSheet("padding: 5px; font-weight: bold;")
        self.toggle_label.mousePressEvent = lambda event: self.toggle_content()

        self.content_area = QFrame()
        self.content_area.setContentsMargins(10, 0, 0, 0) # Margen para indentar
        self.content_area.setVisible(False) # Oculto por defecto

        self.layout.addWidget(self.toggle_label)
        self.layout.addWidget(self.content_area)

    def setContentLayout(self, layout):
        self.content_area.setLayout(layout)

    def toggle_content(self):
        is_hidden = not self.content_area.isVisible()
        self.content_area.setVisible(is_hidden)
        if is_hidden:
            self.toggle_label.setText("▲ Advance —")
        else:
            self.toggle_label.setText("▼ Advance —")


class FireMonitorWidget(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("🔥 EUMETSAT Wildfire Monitoring – Fire Temperature RGB")
        self.setWindowFlags(
            Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint
        )
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # --- Coordenadas ---
        self.label_bbox = QLabel("Current extent:")
        self.coords_label = QLabel("")
        self.layout.addWidget(self.label_bbox)
        self.layout.addWidget(self.coords_label)
        # LÍNEA CORREGIDA: Habilitar la conexión con el lienzo del mapa para que el BBox se actualice
        iface.mapCanvas().extentsChanged.connect(self.update_bbox_labels)

        # --- Selectores de fecha/hora ---
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

        # --- Selector de archivo ---
        self.file_label = QLabel("Output file:")
        self.file_input = QLineEdit()
        self.file_button = QPushButton("Browse...")
        self.file_button.clicked.connect(self.select_output_file)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(self.file_button)

        self.layout.addWidget(self.file_label)
        self.layout.addLayout(file_layout)

        # --- Panel desplegable "Advance" ---
        advanced_layout = QVBoxLayout()
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        
        def add_param_row(parent_layout, bold_text, description, widget):
            row = QVBoxLayout()
            labels_layout = QHBoxLayout()
            label_bold = QLabel(f"<b>{bold_text}</b>")
            label_desc = QLabel(description)
            label_desc.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            labels_layout.addWidget(label_bold)
            labels_layout.addWidget(label_desc, 1)
            row.addLayout(labels_layout)
            row.addWidget(widget)
            parent_layout.addLayout(row)

        self.method_box = QComboBox()
        self.method_box.addItems(["hsv", "rgb", "combined"])
        add_param_row(advanced_layout, "Method", "Detection type: RGB, HSV, or both (default=hsv)", self.method_box)

        self.upscale_spin = QSpinBox()
        self.upscale_spin.setRange(1, 10)
        self.upscale_spin.setValue(4)
        add_param_row(advanced_layout, "Upscale factor", "Controls subpixel simulation (default=4)", self.upscale_spin)

        self.blur_spin = QDoubleSpinBox()
        self.blur_spin.setRange(0.1, 10.0)
        self.blur_spin.setSingleStep(0.1)
        self.blur_spin.setValue(3.0)
        add_param_row(advanced_layout, "Blur sigma", "Controls edge smoothing (default=3.0)", self.blur_spin)

        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.0, 1.0)
        self.thresh_spin.setSingleStep(0.05)
        self.thresh_spin.setValue(0.8)
        add_param_row(advanced_layout, "Threshold value", "Sets fire detection sensitivity (default=0.8)", self.thresh_spin)

        self.tol_spin = QSpinBox()
        self.tol_spin.setRange(0, 255)
        self.tol_spin.setValue(40)
        add_param_row(advanced_layout, "RGB tolerance", "Tolerance for RGB matching (default=40)", self.tol_spin)

        self.min_area_spin = QDoubleSpinBox()
        self.min_area_spin.setRange(0.1, 100.0)
        self.min_area_spin.setSingleStep(0.1)
        self.min_area_spin.setValue(1.0)
        add_param_row(advanced_layout, "Min area (ha)", "Minimum polygon area retained (default=1 ha)", self.min_area_spin)

        self.collapsible_widget = CollapsiblePanel("▼ Advance —")
        self.collapsible_widget.setContentLayout(advanced_layout)
        self.layout.addWidget(self.collapsible_widget)

        # --- Botones de acción ---
        btn_layout = QHBoxLayout()

        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(self.show_about)

        self.run_button = QPushButton("Run")
        self.run_button.setStyleSheet("background-color: #ff944d; font-weight: bold;")
        self.run_button.clicked.connect(self.run_script)

        btn_layout.addWidget(self.about_button)
        btn_layout.addWidget(self.run_button)
        self.layout.addLayout(btn_layout)

        # Espaciador para empujar los botones hacia abajo
        self.layout.addStretch()

        # Bbox inicial
        self.update_bbox_labels()

    # --- Métodos de la clase principal ---
    def run_script(self):
        if not self.file_input.text().strip():
            QMessageBox.warning(self, "Error", "Please select an output file.")
            return

        bbox = get_current_bbox()
        start = self.start_dt.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        end = self.end_dt.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        shapefile_path = self.file_input.text().strip()

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
        
        layer_name = os.path.splitext(os.path.basename(shapefile_path))[0]
        
        if os.path.exists(shapefile_path):
            iface.addVectorLayer(shapefile_path, layer_name, "ogr")
            QMessageBox.information(self, "Success", f"Layer '{layer_name}' added to QGIS.")
        else:
            QMessageBox.warning(self, "Warning", "No wildfires were detected in the area for the date range.")

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

    def select_output_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", "Shapefiles (*.shp)"
        )
        if path:
            if not path.lower().endswith(".shp"):
                path += ".shp"
            self.file_input.setText(path)

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