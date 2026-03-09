import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFileDialog, QFontComboBox, QSpinBox, QColorDialog, QFormLayout, QMessageBox
import json
import base64
from PyQt6.QtCore import Qt, QRect, QEvent
from PyQt6.QtGui import QPixmap, QPainter, QImage, QPainterPath, QPen, QColor, QFont, QBrush, QFontMetrics

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("FFR Map Preview Generator")
        self.resize(800, 800)

        # Main layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)

        # Image preview area
        self.image_preview = QLabel("Image Preview Area")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("QLabel { background-color : lightgray; }")
        self.image_preview.setMinimumSize(1, 1) # Allows the window to shrink below the image's original dimensions
        self.image_preview.installEventFilter(self)
        
        self.label_positions = {}
        self.drawn_text_rects = {}
        self.dragging_label = None
        self.drag_offset = (0, 0)
        
        main_layout.addWidget(self.image_preview, stretch=1)

        # Font settings controls
        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(self.refresh_image)
        
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(1, 100)
        self.size_spinbox.setValue(70)
        self.size_spinbox.valueChanged.connect(self.refresh_image)
        
        self.text_color_button = QPushButton("Text Color")
        self.text_color = QColor(Qt.GlobalColor.white)
        self.text_color_button.setStyleSheet(f"background-color: {self.text_color.name()}")
        self.text_color_button.clicked.connect(self.select_text_color)
        
        self.outline_color_button = QPushButton("Outline Color")
        self.outline_color = QColor(Qt.GlobalColor.black)
        self.outline_color_button.setStyleSheet(f"background-color: {self.outline_color.name()}")
        self.outline_color_button.clicked.connect(self.select_outline_color)
        
        self.outline_size_spinbox = QSpinBox()
        self.outline_size_spinbox.setRange(0, 20)
        self.outline_size_spinbox.setValue(12)
        self.outline_size_spinbox.valueChanged.connect(self.refresh_image)

        self.line_size_spinbox = QSpinBox()
        self.line_size_spinbox.setRange(0, 50)
        self.line_size_spinbox.setValue(8)
        self.line_size_spinbox.valueChanged.connect(self.refresh_image)

        font_layout1 = QHBoxLayout()
        font_layout1.addWidget(QLabel("Label font:"))
        font_layout1.addWidget(self.font_combo, stretch=1)
        font_layout1.addWidget(QLabel("Size:"))
        font_layout1.addWidget(self.size_spinbox)
        
        font_layout2 = QHBoxLayout()
        font_layout2.addWidget(QLabel("Outline Size:"))
        font_layout2.addWidget(self.outline_size_spinbox)
        font_layout2.addWidget(QLabel("Line Width:"))
        font_layout2.addWidget(self.line_size_spinbox)
        font_layout2.addWidget(self.text_color_button)
        font_layout2.addWidget(self.outline_color_button)
        font_layout2.addStretch()
        
        main_layout.addLayout(font_layout1)
        main_layout.addLayout(font_layout2)

        # Buttons layout
        button_layout = QHBoxLayout()
        
        self.load_button = QPushButton("Load JSON")
        self.load_button.clicked.connect(self.load_json)
        
        self.save_button = QPushButton("Save PNG")
        self.save_button.clicked.connect(self.save_png)
        
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.save_button)
        
        main_layout.addLayout(button_layout)

        self.text_mapping = {
            "BahamutCave1": "Bahamut",
            "Cardia1": "Cardia",
            "Cardia2": "Cardia",
            "Cardia4": "Cardia",
            "Cardia5": "Cardia",
            "Cardia6": "Cardia",
            "CastleOrdeals1": "Ordeals",
            "Coneria": "Coneria",
            "ConeriaCastle1": "Coneria Castle",
            "CrescentLake": "Crescent Lake",
            "DwarfCave": "Dwarf Cave",
            "EarthCave1": "Earth Cave",
            "Elfland": "Elfland",
            "ElflandCastle": "Elfland Castle",
            "Gaia": "Gaia",
            "GurguVolcano1": "Volcano",
            "IceCave1": "Ice Cave",
            "Lefein": "Lefein",
            "MarshCave1": "Marsh Cave",
            "MatoyasCave": "Matoya",
            "Melmond": "Melmond",
            "MirageTower1": "Mirage",
            "NorthwestCastle": "Northwest Castle",
            "Onrac": "Onrac",
            "Pravoka": "Pravoka",
            "SardasCave": "Sarda",
            "TempleOfFiends1": "ToF",
            "TitansTunnelEast": "Titans East",
            "TitansTunnelWest": "Titans West",
            "Waterfall": "Waterfall",
            "BridgeLocation": "Bridge",
            "CanalLocation": "Canal"
        }

        # Load tiles
        self.tiles = []
        self.load_tiles("maptiles.png")
        
    def select_text_color(self):
        color = QColorDialog.getColor(self.text_color, self, "Select Text Color")
        if color.isValid():
            self.text_color = color
            self.text_color_button.setStyleSheet(f"background-color: {self.text_color.name()}")
            self.refresh_image()
            
    def select_outline_color(self):
        color = QColorDialog.getColor(self.outline_color, self, "Select Outline Color")
        if color.isValid():
            self.outline_color = color
            self.outline_color_button.setStyleSheet(f"background-color: {self.outline_color.name()}")
            self.refresh_image()

    def load_tiles(self, filename):
        pixmap = QPixmap(filename)
        if pixmap.isNull():
            print(f"Failed to load image: {filename}")
            return
        
        width = pixmap.width()
        height = pixmap.height()
        
        # Split into 16x16 tiles (top to bottom, left to right)
        for y in range(0, height, 16):
            for x in range(0, width, 16):
                # Ensure we don't grab partial tiles off the edge
                if x + 16 <= width and y + 16 <= height:
                    tile = pixmap.copy(x, y, 16, 16)
                    self.tiles.append(tile)
        print(f"Successfully loaded {len(self.tiles)} tiles from {filename}.")

    def get_coords_from_data(self, map_data, oasis_coord=None):
        """
        Extracts all labelable coordinates from map data into a consistent dictionary.
        """
        coords = {}
        if 'OverworldCoordinates' in map_data:
            coords.update(map_data['OverworldCoordinates'])
        
        if 'BridgeLocation' in map_data:
            coords['BridgeLocation'] = map_data['BridgeLocation']
        if 'CanalLocation' in map_data:
            coords['CanalLocation'] = map_data['CanalLocation']
            
        if oasis_coord:
            coords['Oasis'] = oasis_coord
        elif hasattr(self, 'oasis_coord') and self.oasis_coord:
             coords['Oasis'] = self.oasis_coord
             
        return coords

    def load_json(self):
        """
        Event handler for the Load JSON button.
        """
        filename, _ = QFileDialog.getOpenFileName(self, "Open JSON Map File", "", "JSON Files (*.json)")
        if not filename:
            return
            
        try:
            with open(filename, 'r') as f:
                new_map_data = json.load(f)
            
            preserve = False
            if hasattr(self, 'map_data') and self.label_positions:
                reply = QMessageBox.question(
                    self, 
                    'Preserve Labels?', 
                    'Would you like to keep your manual label placements for locations that haven\'t moved?',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                    QMessageBox.StandardButton.Yes
                )
                if reply == QMessageBox.StandardButton.Yes:
                    preserve = True
            
            if preserve:
                # Compare old coords with new coords
                old_coords = self.get_coords_from_data(self.map_data)
                # We don't have the new oasis_coord yet until generate_image runs, 
                # but we can check the rest. Actually, oasis is usually fixed.
                new_coords = self.get_coords_from_data(new_map_data)
                
                new_label_positions = {}
                for name, pos in self.label_positions.items():
                    if name in old_coords and name in new_coords:
                        old_pos = old_coords[name]
                        new_pos = new_coords[name]
                        # Check if location is exactly the same
                        if old_pos.get('X') == new_pos.get('X') and old_pos.get('Y') == new_pos.get('Y'):
                            new_label_positions[name] = pos
                
                self.label_positions = new_label_positions
            else:
                self.label_positions.clear()

            self.map_data = new_map_data
            self.drawn_text_rects.clear()
            print(f"Successfully loaded JSON metadata from {filename}!")
            self.generate_image()
        except Exception as e:
            print(f"Error loading JSON file: {e}")

    def generate_image(self):
        """
        Generates the map image from the loaded JSON data and tiles.
        """
        if not hasattr(self, 'map_data') or 'DecompressedMapRows' not in self.map_data:
            print("No map data or 'DecompressedMapRows' found in JSON.")
            return

        map_rows = self.map_data['DecompressedMapRows']
        if not map_rows:
            return

        # Decode base64 to get byte arrays for each row
        decoded_rows = [base64.b64decode(row) for row in map_rows]
        
        # Calculate image dimensions
        height_tiles = len(decoded_rows)
        width_tiles = len(decoded_rows[0]) if height_tiles > 0 else 0
        
        img_width = width_tiles * 16
        img_height = height_tiles * 16
        
        # Create a new blank QPixmap to draw on
        result_pixmap = QPixmap(img_width, img_height)
        result_pixmap.fill(Qt.GlobalColor.transparent) # Fill transparent initially
        
        painter = QPainter(result_pixmap)
        
        self.oasis_coord = None
        for y, row_bytes in enumerate(decoded_rows):
            for x, tile_index in enumerate(row_bytes):
                if tile_index < len(self.tiles):
                    tile_pixmap = self.tiles[tile_index]
                    painter.drawPixmap(x * 16, y * 16, tile_pixmap)
                    
                    # Store first instance of Oasis tile (0x36 = 54)
                    if self.oasis_coord is None and tile_index == 0x36:
                        self.oasis_coord = {"X": x, "Y": y}
                else:
                    print(f"Warning: Tile index {tile_index} out of bounds (max {len(self.tiles) - 1})")
                    
        painter.end()
        
        # Store for saving later and text overlays
        self.base_pixmap = result_pixmap
        self.refresh_image()
        print("Base Image generated.")

    def refresh_image(self, *args):
        """
        Refreshes the image preview by drawing text over the base map.
        """
        if not hasattr(self, 'base_pixmap') or not hasattr(self, 'map_data'):
            return

        # Copy the base pixmap
        result_pixmap = self.base_pixmap.copy()
        painter = QPainter(result_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        font = self.font_combo.currentFont()
        font.setPointSize(self.size_spinbox.value())
        
        outline_size = self.outline_size_spinbox.value()
        
        outline_pen = QPen(self.outline_color, outline_size)
        outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        text_brush = QBrush(self.text_color)

        coords = self.get_coords_from_data(self.map_data)

        if coords:
            font_metrics = QFontMetrics(font)
            
            # Sort coordinates by Y, then X to preserve relative placement
            sorted_coords = sorted(coords.items(), key=lambda item: (item[1].get('Y', 0), item[1].get('X', 0)))
            
            self.drawn_text_rects.clear()
            drawn_rects = []
            
            # 1. Pre-calculate rects for PRESERVED labels so auto-layout avoids them
            for name, pos in sorted_coords:
                if name in self.label_positions:
                    display_name = getattr(self, 'text_mapping', {}).get(name, name) if hasattr(self, 'text_mapping') else name
                    x_offset, y_offset = self.label_positions[name]
                    text_width = font_metrics.horizontalAdvance(display_name)
                    text_height = font_metrics.height()
                    
                    preserved_rect = QRect(
                        int(x_offset + text_width * 0.1), 
                        int(y_offset - font_metrics.ascent() + text_height * 0.2), 
                        int(text_width * 0.8), 
                        int(text_height * 0.6)
                    )
                    drawn_rects.append(preserved_rect)

            # 2. Calculate layout for NEW or RESET labels
            for name, pos in sorted_coords:
                if name not in self.label_positions:
                    display_name = getattr(self, 'text_mapping', {}).get(name, name) if hasattr(self, 'text_mapping') else name
                    
                    target_x = float(pos.get('X', 0) * 16) + 8
                    target_y = float(pos.get('Y', 0) * 16) + 8
                    
                    text_width = font_metrics.horizontalAdvance(display_name)
                    text_height = font_metrics.height()
                    
                    x_offset = target_x - (text_width / 2.0)
                    y_offset = target_y + (font_metrics.ascent() / 2.0) + 48 # Nudge further away from target
                    
                    overlap = True
                    max_iterations = 100
                    iterations = 0
                    
                    while overlap and iterations < max_iterations:
                        current_rect = QRect(
                            int(x_offset + text_width * 0.1), 
                            int(y_offset - font_metrics.ascent() + text_height * 0.2), 
                            int(text_width * 0.8), 
                            int(text_height * 0.6)
                        )
                        
                        overlap = False
                        for prev_rect in drawn_rects:
                            if current_rect.intersects(prev_rect):
                                overlap = True
                                y_offset += max(2.0, text_height * 0.1)
                                break
                        
                        iterations += 1
                    
                    self.label_positions[name] = (x_offset, y_offset)
                    drawn_rects.append(current_rect)

            line_thickness = self.line_size_spinbox.value()
            line_pen = QPen(self.text_color, line_thickness)
            line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

            # 2. Second Pass: Draw connecting lines (so they appear under text)
            if line_thickness > 0:
                outline_thickness = 4
                outline_pen = QPen(Qt.GlobalColor.black, line_thickness + outline_thickness * 2)
                outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                
                for name, pos in sorted_coords:
                    if name in self.label_positions:
                        display_name = getattr(self, 'text_mapping', {}).get(name, name) if hasattr(self, 'text_mapping') else name
                        target_x = float(pos.get('X', 0) * 16) + 8
                        target_y = float(pos.get('Y', 0) * 16) + 8
                        
                        x_offset, y_offset = self.label_positions[name]
                        text_width = font_metrics.horizontalAdvance(display_name)
                        tx = int(x_offset + text_width / 2.0)
                        ty = int(y_offset - font_metrics.ascent() + font_metrics.height() / 2.0)
                        
                        # Draw outline
                        painter.setPen(outline_pen)
                        painter.drawLine(int(target_x), int(target_y), tx, ty)
                        
                        # Draw main line
                        painter.setPen(line_pen)
                        painter.drawLine(int(target_x), int(target_y), tx, ty)
            
            # 3. Third Pass: Draw text with outlines
            for name, pos in sorted_coords:
                if name in self.label_positions:
                    display_name = getattr(self, 'text_mapping', {}).get(name, name) if hasattr(self, 'text_mapping') else name
                    x_offset, y_offset = self.label_positions[name]
                    
                    # Store exact bounding box for mouse hit testing
                    text_width = font_metrics.horizontalAdvance(display_name)
                    text_rect = QRect(
                        int(x_offset),
                        int(y_offset - font_metrics.ascent()),
                        int(text_width),
                        int(font_metrics.height())
                    )
                    self.drawn_text_rects[name] = text_rect

                    path = QPainterPath()
                    path.addText(x_offset, y_offset, font, display_name)
                    
                    if outline_size > 0:
                        painter.strokePath(path, outline_pen)
                        
                    painter.fillPath(path, text_brush)

        if 'StartingLocation' in self.map_data:
            start_pos = self.map_data['StartingLocation']
            start_x = float(start_pos.get('X', 0) * 16)
            start_y = float(start_pos.get('Y', 0) * 16)
            start_img = QPixmap("start.png")
            if not start_img.isNull():
                scaled_start = start_img.scaled(start_img.width() * 5, start_img.height() * 5, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                painter.drawPixmap(int(start_x + 8 - scaled_start.width() / 2), int(start_y + 8 - scaled_start.height() / 2), scaled_start)

        if 'AirShipLocation' in self.map_data:
            airship_pos = self.map_data['AirShipLocation']
            airship_x = float(airship_pos.get('X', 0) * 16)
            airship_y = float(airship_pos.get('Y', 0) * 16)
            airship_img = QPixmap("airship.png")
            if not airship_img.isNull():
                scaled_airship = airship_img.scaled(airship_img.width() * 5, airship_img.height() * 5, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                painter.drawPixmap(int(airship_x + 8 - scaled_airship.width() / 2), int(airship_y + 8 - scaled_airship.height() / 2), scaled_airship)

        # if 'BridgeLocation' in self.map_data:
        #     bridge_pos = self.map_data['BridgeLocation']
        #     bridge_x = float(bridge_pos.get('X', 0) * 16)
        #     bridge_y = float(bridge_pos.get('Y', 0) * 16)
        #     bridge_img = QPixmap("bridge.png")
        #     if not bridge_img.isNull():
        #         scaled_bridge = bridge_img.scaled(bridge_img.width() * 5, bridge_img.height() * 5, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        #         painter.drawPixmap(int(bridge_x + 8 - scaled_bridge.width() / 2), int(bridge_y + 8 - scaled_bridge.height() / 2), scaled_bridge)

        # if 'CanalLocation' in self.map_data:
        #     canal_pos = self.map_data['CanalLocation']
        #     canal_x = float(canal_pos.get('X', 0) * 16)
        #     canal_y = float(canal_pos.get('Y', 0) * 16)
        #     canal_img = QPixmap("canal.png")
        #     if not canal_img.isNull():
        #         scaled_canal = canal_img.scaled(canal_img.width() * 5, canal_img.height() * 5, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        #         painter.drawPixmap(int(canal_x + 8 - scaled_canal.width() / 2), int(canal_y + 8 - scaled_canal.height() / 2), scaled_canal)

        painter.end()
        self.generated_pixmap = result_pixmap

        # Scale to fit preview area if needed, keeping aspect ratio
        scaled_pixmap = result_pixmap.scaled(
            self.image_preview.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_preview.setPixmap(scaled_pixmap)

    def save_png(self):
        """
        Event handler for the Save PNG button.
        """
        if not hasattr(self, 'generated_pixmap') or self.generated_pixmap is None:
            print("No generated image to save.")
            return

        filename, _ = QFileDialog.getSaveFileName(self, "Save PNG File", "", "PNG Files (*.png)")
        if not filename:
            return

        if not filename.endswith('.png'):
            filename += '.png'

        if self.generated_pixmap.save(filename, "PNG"):
            print(f"Successfully saved image to {filename}")
        else:
            print(f"Failed to save image to {filename}")

    def resizeEvent(self, event):
        """
        Handle window resize to dynamically scale the preview image.
        """
        super().resizeEvent(event)
        if hasattr(self, 'generated_pixmap') and not self.generated_pixmap.isNull():
            scaled_pixmap = self.generated_pixmap.scaled(
                self.image_preview.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_preview.setPixmap(scaled_pixmap)

    def map_to_pixmap_coords(self, mx, my):
        if not hasattr(self, 'generated_pixmap') or self.generated_pixmap.isNull():
            return mx, my
        
        label_w = self.image_preview.width()
        label_h = self.image_preview.height()
        orig_w = self.generated_pixmap.width()
        orig_h = self.generated_pixmap.height()
        
        scale = min(label_w / orig_w, label_h / orig_h)
        
        rendered_w = orig_w * scale
        rendered_h = orig_h * scale
        
        offset_x = (label_w - rendered_w) / 2
        offset_y = (label_h - rendered_h) / 2
        
        px = (mx - offset_x) / scale
        py = (my - offset_y) / scale
        return px, py

    def eventFilter(self, obj, event):
        if obj == self.image_preview and hasattr(self, 'generated_pixmap') and not self.generated_pixmap.isNull():
            if event.type() == QEvent.Type.MouseButtonPress:
                pos = event.pos()
                px, py = self.map_to_pixmap_coords(pos.x(), pos.y())
                for name, rect in reversed(list(self.drawn_text_rects.items())):
                    if rect.contains(int(px), int(py)):
                        self.dragging_label = name
                        lx, ly = self.label_positions[name]
                        self.drag_offset = (lx - px, ly - py)
                        return True
            elif event.type() == QEvent.Type.MouseMove and self.dragging_label is not None:
                pos = event.pos()
                px, py = self.map_to_pixmap_coords(pos.x(), pos.y())
                name = self.dragging_label
                ox, oy = self.drag_offset
                self.label_positions[name] = (px + ox, py + oy)
                self.refresh_image()
                return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self.dragging_label is not None:
                    self.dragging_label = None
                    return True
        return super().eventFilter(obj, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
