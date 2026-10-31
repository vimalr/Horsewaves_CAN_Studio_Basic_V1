import sys, time, threading, urllib.request
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtWebEngineWidgets import QWebEngineView

URL = "http://127.0.0.1:5173"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Horsewaves CAN Studio Basic")
        self.resize(1440, 900)
        self.view = QWebEngineView()
        self.setCentralWidget(self.view)
        self.view.load(QUrl(URL))
        self.statusBar().showMessage("Horsewaves CAN Studio • Web UI desktop shell")

app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())
