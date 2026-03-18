import sys
import ctypes
from PyQt5.QtWidgets import QApplication
from .main_window import MainWindow

def main():
    # Windows DPI 适配
    try:
        if not ctypes.windll.shcore.SetProcessDpiAwareness(2):
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except: pass

    app = QApplication(sys.argv)
    app.setApplicationName("截图打码助手")

    window = MainWindow()
    window._screenshot_signal.connect(window.start_capture)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
