"""agent_ui.py - PyQt5 based UI for Lab Guardian Agent."""

import sys
import os
from datetime import datetime, timezone
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, QTabWidget,
    QGroupBox, QFormLayout, QMessageBox, QDialog, QInputDialog,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QStatusBar, QFrame, QSplitter, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
from PyQt5.QtGui import QFont, QColor, QIcon
import logging

log = logging.getLogger("lab_guardian.ui")

SECRET_KEY = "80085"


class SecretKeyDialog(QDialog):
    """Dialog to enter secret key for ending session."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("End Exam Session")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Warning icon and message
        warning_label = QLabel("⚠️ End Exam Session")
        warning_label.setFont(QFont("Arial", 16, QFont.Bold))
        warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_label)
        
        lbl = QLabel("Enter the secret key to end the exam session:")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        
        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText("Enter secret key...")
        self.key_input.setMinimumHeight(40)
        self.key_input.setFont(QFont("Arial", 12))
        layout.addWidget(self.key_input)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("End Session")
        self.btn_ok.setMinimumHeight(40)
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setMinimumHeight(40)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.btn_ok.clicked.connect(self.verify_key)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Enter key triggers OK
        self.key_input.returnPressed.connect(self.verify_key)
    
    def verify_key(self):
        if self.key_input.text() == SECRET_KEY:
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Key", "The secret key is incorrect!")
            self.key_input.clear()


class StatusIndicator(QWidget):
    """Custom status indicator widget."""
    
    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Arial", 12))
        self.dot.setStyleSheet("color: gray;")
        
        self.label = QLabel(label)
        self.label.setFont(QFont("Arial", 10))
        
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
    
    def set_status(self, status, color):
        """Set status with color: green, red, yellow."""
        color_map = {
            "green": "#10b981",
            "red": "#ef4444",
            "yellow": "#f59e0b",
            "gray": "#6b7280"
        }
        self.dot.setStyleSheet(f"color: {color_map.get(color, 'gray')};")


class AgentMainWindow(QMainWindow):
    """Main window for Lab Guardian Agent."""
    
    # Signals for background updates
    update_processes = pyqtSignal(list)
    update_browser = pyqtSignal(list)
    update_terminal = pyqtSignal(list)
    update_devices = pyqtSignal(list)
    
    def __init__(self, local_db):
        super().__init__()
        self.local_db = local_db
        self.exam_started = False
        self.exam_start_time = None
        self.roll_no = None
        self.lab_no = None
        self.session_id = None
        self.internet_connected = False
        self.sync_enabled = False
        
        self.setup_ui()
        self.setup_status_bar()
        self.start_internet_checker()
        
        # Connect signals
        self.update_processes.connect(self.on_processes_update)
        self.update_browser.connect(self.on_browser_update)
        self.update_terminal.connect(self.on_terminal_update)
        self.update_devices.connect(self.on_devices_update)
    
    def setup_ui(self):
        self.setWindowTitle("Lab Guardian - Exam Monitoring Agent")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(self.get_stylesheet())
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        
        # ===== HEADER =====
        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_layout = QHBoxLayout(header_frame)
        
        title = QLabel("🛡️ Lab Guardian Exam Agent")
        title.setFont(QFont("Arial", 20, QFont.Bold))
        header_layout.addWidget(title)
        
        # Status indicators in header
        self.indicator_monitoring = StatusIndicator("Monitoring")
        self.indicator_internet = StatusIndicator("Internet")
        self.indicator_sync = StatusIndicator("Sync")
        
        header_layout.addWidget(self.indicator_monitoring)
        header_layout.addWidget(self.indicator_internet)
        header_layout.addWidget(self.indicator_sync)
        
        main_layout.addWidget(header_frame)
        
        # ===== CONFIGURATION PANEL =====
        self.config_group = QGroupBox("📝 Exam Configuration")
        self.config_group.setObjectName("configBox")
        config_layout = QFormLayout()
        config_layout.setSpacing(10)
        
        # Roll Number Input
        self.roll_input = QLineEdit()
        self.roll_input.setPlaceholderText("Enter your roll number (e.g., CS2021001)")
        self.roll_input.setMinimumHeight(40)
        self.roll_input.setFont(QFont("Arial", 12))
        config_layout.addRow("Roll Number:", self.roll_input)
        
        # Lab Number Dropdown
        self.lab_combo = QComboBox()
        self.lab_combo.setMinimumHeight(40)
        self.lab_combo.setFont(QFont("Arial", 12))
        for i in range(1, 13):
            lab_code = f"L{i:02d}"
            self.lab_combo.addItem(lab_code)
        config_layout.addRow("Lab Number:", self.lab_combo)
        
        # Start Button
        self.start_btn = QPushButton("🚀 Start Exam Session")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.start_btn.clicked.connect(self.start_exam)
        config_layout.addRow("", self.start_btn)
        
        self.config_group.setLayout(config_layout)
        main_layout.addWidget(self.config_group)
        
        # ===== SESSION INFO PANEL (Hidden initially) =====
        self.session_group = QGroupBox("📊 Session Information")
        self.session_group.setObjectName("sessionBox")
        self.session_group.setVisible(False)
        
        session_layout = QHBoxLayout()
        
        info_layout = QFormLayout()
        self.status_roll = QLabel("-")
        self.status_roll.setFont(QFont("Arial", 11, QFont.Bold))
        info_layout.addRow("Roll Number:", self.status_roll)
        
        self.status_lab = QLabel("-")
        self.status_lab.setFont(QFont("Arial", 11, QFont.Bold))
        info_layout.addRow("Lab Number:", self.status_lab)
        
        self.status_start_time = QLabel("-")
        info_layout.addRow("Started At:", self.status_start_time)
        
        self.status_duration = QLabel("00:00:00")
        self.status_duration.setFont(QFont("Arial", 12, QFont.Bold))
        self.status_duration.setObjectName("durationLabel")
        info_layout.addRow("Duration:", self.status_duration)
        
        session_layout.addLayout(info_layout)
        session_layout.addStretch()
        
        # End Session Button
        self.end_btn = QPushButton("🔒 End Session")
        self.end_btn.setMinimumWidth(150)
        self.end_btn.setMinimumHeight(50)
        self.end_btn.setFont(QFont("Arial", 12, QFont.Bold))
        self.end_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        self.end_btn.clicked.connect(self.end_session)
        session_layout.addWidget(self.end_btn)
        
        self.session_group.setLayout(session_layout)
        main_layout.addWidget(self.session_group)
        
        # Duration timer
        self.duration_timer = QTimer()
        self.duration_timer.timeout.connect(self.update_duration)
        
        # ===== MONITORING TABS =====
        self.tab_widget = QTabWidget()
        self.tab_widget.setVisible(False)
        self.tab_widget.setMinimumHeight(400)
        
        # Processes Tab
        self.process_table = self.create_activity_table([
            "Count", "Process Name", "CPU %", "Memory (MB)", "Risk", "Status"
        ])
        self.tab_widget.addTab(self.process_table, "📊 Processes")
        
        # Browser History Tab
        self.browser_table = self.create_activity_table([
            "URL", "Title", "Browser", "Visits", "Last Visited"
        ])
        self.tab_widget.addTab(self.browser_table, "🌐 Browser History")
        
        # Terminal Tab
        self.terminal_table = self.create_activity_table([
            "Tool", "Command/Connection", "Risk", "Type", "Time"
        ])
        self.tab_widget.addTab(self.terminal_table, "💻 Terminal Activity")
        
        # Devices Tab
        self.devices_table = self.create_activity_table([
            "Device Name", "Type", "Risk", "Status", "Connected At"
        ])
        self.tab_widget.addTab(self.devices_table, "🔌 USB Devices")
        
        main_layout.addWidget(self.tab_widget)
    
    def setup_status_bar(self):
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready to start exam session")
    
    def get_stylesheet(self):
        return """
            QMainWindow {
                background-color: #f3f4f6;
            }
            QGroupBox {
                background-color: white;
                border: 2px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            #header {
                background-color: #0a2540;
                color: white;
                padding: 15px;
                border-radius: 8px;
            }
            #configBox, #sessionBox {
                background-color: white;
            }
            QLineEdit, QComboBox {
                padding: 8px;
                border: 2px solid #d1d5db;
                border-radius: 5px;
                background-color: white;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #2563eb;
            }
            QPushButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
            QTableWidget {
                background-color: white;
                alternate-background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 5px;
                gridline-color: #e5e7eb;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #0a2540;
                color: white;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                border-radius: 5px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e5e7eb;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: #0a2540;
                color: white;
            }
            #durationLabel {
                color: #2563eb;
                font-size: 14px;
            }
        """
    
    def create_activity_table(self, columns):
        """Create a styled table for activity display."""
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        return table
    
    def start_internet_checker(self):
        """Start timer to check internet connectivity."""
        self.internet_timer = QTimer()
        self.internet_timer.timeout.connect(self.check_internet)
        self.internet_timer.start(10000)  # Check every 10 seconds
        self.check_internet()
    
    def check_internet(self):
        """Check if internet is available."""
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self.internet_connected = True
            self.indicator_internet.set_status("Internet", "green")
        except OSError:
            self.internet_connected = False
            self.indicator_internet.set_status("Internet", "red")
    
    def start_exam(self):
        """Start the exam session."""
        self.roll_no = self.roll_input.text().strip()
        self.lab_no = self.lab_combo.currentText()
        
        if not self.roll_no:
            QMessageBox.warning(self, "Missing Information", "Please enter your roll number!")
            return
        
        # Generate session ID from roll_no and timestamp
        import uuid
        self.session_id = str(uuid.uuid4())
        
        # Create exam session in local DB
        self.exam_start_time = self.local_db.create_exam_session(
            self.session_id, self.roll_no, self.lab_no
        )
        
        self.exam_started = True
        
        # Update UI
        self.config_group.setVisible(False)
        self.session_group.setVisible(True)
        self.tab_widget.setVisible(True)
        
        self.status_roll.setText(self.roll_no)
        self.status_lab.setText(self.lab_no)
        self.status_start_time.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        # Start duration timer
        self.duration_timer.start(1000)
        
        # Update monitoring status
        self.indicator_monitoring.set_status("Monitoring", "green")
        
        self.statusBar.showMessage(f"Exam session started for {self.roll_no} in {self.lab_no}")
        
        log.info(f"Exam started: {self.session_id}, {self.roll_no}, {self.lab_no}")
        
        # Emit signal to start monitors (will be connected by dispatcher)
        if hasattr(self, 'on_exam_started'):
            self.on_exam_started(self.session_id, self.roll_no, self.lab_no)
    
    def end_session(self):
        """End the exam session with secret key verification."""
        dialog = SecretKeyDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # End session in local DB
            self.local_db.end_exam_session(self.session_id)
            
            self.exam_started = False
            self.duration_timer.stop()
            
            self.indicator_monitoring.set_status("Monitoring", "gray")
            
            QMessageBox.information(
                self,
                "Session Ended",
                f"Exam session ended successfully.\n\n"
                f"Roll Number: {self.roll_no}\n"
                f"Lab: {self.lab_no}\n"
                f"Duration: {self.status_duration.text()}\n\n"
                f"All data has been saved locally."
            )
            
            self.statusBar.showMessage("Exam session ended")
            log.info(f"Exam ended: {self.session_id}")
            
            # Close the application
            self.close()
    
    def update_duration(self):
        """Update the session duration display."""
        if self.exam_start_time:
            elapsed = datetime.now(timezone.utc).timestamp() - self.exam_start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            self.status_duration.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def on_processes_update(self, processes):
        """Update process table with grouped process data.
        
        Groups processes by name, showing aggregated stats:
        - Count: number of instances
        - CPU %: sum of all instances
        - Memory: sum of all instances
        - Risk: highest risk level among instances
        """
        self.process_table.setRowCount(0)
        
        # Group processes by name
        grouped = {}
        for proc in processes:
            name = proc.get('process_name', 'Unknown')
            # Check if any instance is incognito
            is_incognito = proc.get('is_incognito', False) or proc.get('category') == 'incognito'
            
            if name not in grouped:
                grouped[name] = {
                    'count': 0,
                    'cpu_percent': 0.0,
                    'memory_mb': 0.0,
                    'risk_level': 'low',
                    'status': 'running',
                    'has_incognito': False
                }
            
            g = grouped[name]
            g['count'] += 1
            g['cpu_percent'] += proc.get('cpu_percent', 0)
            g['memory_mb'] += proc.get('memory_mb', 0)
            
            # Track if any instance is incognito
            if is_incognito:
                g['has_incognito'] = True
            
            # Keep highest risk level
            risk = proc.get('risk_level', 'normal')
            if risk == 'high' or g['risk_level'] == 'high':
                g['risk_level'] = 'high'
            elif risk == 'medium' or g['risk_level'] == 'medium':
                g['risk_level'] = 'medium'
            else:
                g['risk_level'] = risk
        
        # Sort by risk level (high first), then by CPU usage
        risk_order = {'high': 0, 'medium': 1, 'low': 2, 'normal': 3}
        sorted_processes = sorted(
            grouped.items(),
            key=lambda x: (risk_order.get(x[1]['risk_level'], 3), -x[1]['cpu_percent'])
        )
        
        for name, data in sorted_processes:
            row = self.process_table.rowCount()
            self.process_table.insertRow(row)
            
            # Count with instance indicator
            count_text = str(data['count']) if data['count'] == 1 else f"{data['count']}"
            self.process_table.setItem(row, 0, QTableWidgetItem(count_text))
            
            # Show incognito indicator in process name
            display_name = name
            if data.get('has_incognito'):
                display_name = f"{name} 🔒 (Private/Incognito)"
            self.process_table.setItem(row, 1, QTableWidgetItem(display_name))
            self.process_table.setItem(row, 2, QTableWidgetItem(f"{data['cpu_percent']:.1f}%"))
            self.process_table.setItem(row, 3, QTableWidgetItem(f"{data['memory_mb']:.1f}"))
            
            risk = data['risk_level']
            risk_item = QTableWidgetItem(risk.upper())
            if risk == 'high':
                risk_item.setForeground(QColor("#ef4444"))
            elif risk == 'medium':
                risk_item.setForeground(QColor("#f59e0b"))
            self.process_table.setItem(row, 4, risk_item)
            
            status_text = "Running" if data['count'] > 0 else "Stopped"
            self.process_table.setItem(row, 5, QTableWidgetItem(status_text))
    
    def on_browser_update(self, urls):
        """Update browser history table."""
        self.browser_table.setRowCount(0)
        
        for url_data in urls:
            row = self.browser_table.rowCount()
            self.browser_table.insertRow(row)
            
            self.browser_table.setItem(row, 0, QTableWidgetItem(url_data.get('url', '')))
            self.browser_table.setItem(row, 1, QTableWidgetItem(url_data.get('title', '')))
            self.browser_table.setItem(row, 2, QTableWidgetItem(url_data.get('browser', '')))
            self.browser_table.setItem(row, 3, QTableWidgetItem(str(url_data.get('visit_count', 0))))
            
            last_visited = url_data.get('last_visited')
            if last_visited:
                dt = datetime.fromtimestamp(last_visited)
                self.browser_table.setItem(row, 4, QTableWidgetItem(dt.strftime("%H:%M:%S")))
    
    def on_terminal_update(self, events):
        """Update terminal events table."""
        self.terminal_table.setRowCount(0)
        
        for event in events:
            row = self.terminal_table.rowCount()
            self.terminal_table.insertRow(row)
            
            self.terminal_table.setItem(row, 0, QTableWidgetItem(event.get('tool', '')))
            
            if event.get('full_command'):
                self.terminal_table.setItem(row, 1, QTableWidgetItem(event.get('full_command', '')))
            else:
                remote = f"{event.get('remote_ip', '')}:{event.get('remote_port', '')}"
                self.terminal_table.setItem(row, 1, QTableWidgetItem(remote))
            
            risk = event.get('risk_level', 'medium')
            risk_item = QTableWidgetItem(risk.upper())
            if risk == 'high':
                risk_item.setForeground(QColor("#ef4444"))
            elif risk == 'medium':
                risk_item.setForeground(QColor("#f59e0b"))
            self.terminal_table.setItem(row, 2, risk_item)
            
            self.terminal_table.setItem(row, 3, QTableWidgetItem(event.get('event_type', '')))
            
            detected_at = event.get('detected_at')
            if detected_at:
                dt = datetime.fromtimestamp(detected_at)
                self.terminal_table.setItem(row, 4, QTableWidgetItem(dt.strftime("%H:%M:%S")))
    
    def on_devices_update(self, devices):
        """Update devices table."""
        self.devices_table.setRowCount(0)
        
        for device in devices:
            row = self.devices_table.rowCount()
            self.devices_table.insertRow(row)
            
            self.devices_table.setItem(row, 0, QTableWidgetItem(device.get('readable_name', '')))
            self.devices_table.setItem(row, 1, QTableWidgetItem(device.get('device_type', '')))
            
            risk = device.get('risk_level', 'normal')
            risk_item = QTableWidgetItem(risk.upper())
            if risk == 'high':
                risk_item.setForeground(QColor("#ef4444"))
            self.devices_table.setItem(row, 2, risk_item)
            
            status = "Disconnected" if device.get('disconnected_at') else "Connected"
            self.devices_table.setItem(row, 3, QTableWidgetItem(status))
            
            connected_at = device.get('connected_at')
            if connected_at:
                dt = datetime.fromtimestamp(connected_at)
                self.devices_table.setItem(row, 4, QTableWidgetItem(dt.strftime("%H:%M:%S")))
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.exam_started:
            reply = QMessageBox.question(
                self,
                'Confirm Exit',
                'Exam session is still running. Are you sure you want to exit?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.local_db.close()
                event.accept()
            else:
                event.ignore()
        else:
            self.local_db.close()
            event.accept()


def run_agent_ui(local_db):
    """Start the PyQt5 application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = AgentMainWindow(local_db)
    window.show()
    
    sys.exit(app.exec_())
