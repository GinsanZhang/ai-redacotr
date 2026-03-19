import sys
from PyQt6.QtWidgets import QApplication
from .main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("截图打码助手")

    window = MainWindow()
    window._screenshot_signal.connect(window.start_capture)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
