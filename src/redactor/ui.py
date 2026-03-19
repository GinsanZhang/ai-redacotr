import cv2
import time
import numpy as np
from PIL import Image, ImageGrab
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QFileDialog,
    QStatusBar, QFrame, QSizePolicy, QCheckBox, QComboBox,
    QSlider, QMessageBox, QProgressBar
)
from PyQt6.QtCore import (
    Qt, QRect, QPoint, QSize, pyqtSignal, QObject,
    QThread, QTimer, QRectF
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QBrush, QColor,
    QImage, QCursor, QFont, QKeySequence
)
from .config import CONFIG, STYLESHEET
from .utils import dev_log
from .core import detect_by_rules, detect_by_ai, detect_by_cloud_vision, apply_mosaic

MOUSE_LEFT = Qt.MouseButton.LeftButton
CURSOR_CROSS = Qt.CursorShape.CrossCursor
CURSOR_FORBIDDEN = Qt.CursorShape.ForbiddenCursor
PEN_DASH_LINE = Qt.PenStyle.DashLine
GLOBAL_WHITE = Qt.GlobalColor.white
GLOBAL_TRANSPARENT = Qt.GlobalColor.transparent
WINDOW_FRAMELESS = Qt.WindowType.FramelessWindowHint
WINDOW_TOPMOST = Qt.WindowType.WindowStaysOnTopHint
WINDOW_TOOL = Qt.WindowType.Tool
WIDGET_TRANSLUCENT = Qt.WidgetAttribute.WA_TranslucentBackground
KEY_ESCAPE = Qt.Key.Key_Escape
IMAGE_FORMAT_RGB888 = QImage.Format.Format_RGB888
PAINTER_ANTIALIAS = QPainter.RenderHint.Antialiasing
PAINTER_CLEAR = QPainter.CompositionMode.CompositionMode_Clear
PAINTER_SOURCE_OVER = QPainter.CompositionMode.CompositionMode_SourceOver

def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

class ProcessSignals(QObject):
    progress, progress_value, finished, error = pyqtSignal(str), pyqtSignal(int), pyqtSignal(list, list, dict), pyqtSignal(str)

class ProcessWorker(QThread):
    def __init__(self, image_cv: np.ndarray):
        super().__init__()
        self.image_cv, self.signals = image_cv, ProcessSignals()
    def run(self):
        try:
            timings, total_start = {}, time.time()
            self.signals.progress_value.emit(5)
            self.signals.progress.emit("云端视觉识别中...")
            s1 = time.time()
            ocr = detect_by_cloud_vision(self.image_cv, self.signals.progress.emit)
            timings["云端视觉"] = time.time() - s1
            self.signals.progress_value.emit(55)
            self.signals.progress.emit("规则匹配中...")
            s2 = time.time()
            rules = detect_by_rules(ocr)
            timings["规则匹配"] = time.time() - s2
            self.signals.progress_value.emit(75)
            self.signals.progress.emit("AI分析中...")
            s3 = time.time()
            rule_texts = {h["text"] for h in rules}
            rem = [b for b in ocr if b["text"] not in rule_texts]
            ai = detect_by_ai(rem, self.signals.progress.emit)
            timings["AI分析"] = time.time() - s3
            timings["总耗时"] = time.time() - total_start
            self.signals.progress_value.emit(100)
            self.signals.progress.emit("处理完成")
            self.signals.finished.emit(ocr, rules + ai, timings)
        except Exception as e:
            self.signals.error.emit(str(e))

class AnnotationCanvas(QLabel):
    regions_changed = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.original_cv, self.display_scale, self.regions = None, 1.0, []
        self.drag_start, self.drag_current, self.hover_region, self.mode = None, None, None, "add"
        self.setMouseTracking(True)
        self.setCursor(QCursor(CURSOR_CROSS))
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def load_image(self, image_cv: np.ndarray, hits: list):
        self.original_cv = image_cv.copy()
        self.regions = [{"bbox": h["bbox"], "label": h["label"], "source": h.get("source","rule")} for h in hits]
        self._fit_and_render()

    def _fit_and_render(self):
        if self.original_cv is None: return
        h, w = self.original_cv.shape[:2]
        self.display_scale = min((self.width() or 900) / w, (self.height() or 600) / h, 1.0)
        self._render()

    def _render(self):
        if self.original_cv is None: return
        img = self.original_cv.copy()
        for r in self.regions:
            img = apply_mosaic(img, r["bbox"], CONFIG["mosaic_style"], CONFIG["mosaic_strength"])
        h, w = img.shape[:2]
        nw, nh = int(w * self.display_scale), int(h * self.display_scale)
        disp = cv2.resize(img, (nw, nh))
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        pix = QPixmap.fromImage(QImage(rgb.data, nw, nh, 3 * nw, IMAGE_FORMAT_RGB888))
        ptr = QPainter(pix)
        ptr.setRenderHint(PAINTER_ANTIALIAS)
        for i, r in enumerate(self.regions):
            x1, y1, x2, y2 = [int(c * self.display_scale) for c in r["bbox"]]
            col = QColor(255, 80, 80, 180) if r.get("source") != "ai" else QColor(255, 160, 0, 180)
            if i == self.hover_region: col = QColor(255, 50, 50, 220)
            ptr.setPen(QPen(col, 2))
            ptr.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 30)))
            ptr.drawRect(x1, y1, x2 - x1, y2 - y1)
            lbl = r.get("label", "")
            if lbl:
                ptr.setPen(QPen(GLOBAL_WHITE))
                ptr.setBrush(QBrush(col))
                fm = ptr.fontMetrics()
                tw, th = fm.horizontalAdvance(lbl) + 8, fm.height() + 4
                ptr.drawRect(x1, max(0, y1 - th), tw, th)
                ptr.drawText(x1 + 4, max(th, y1) - 3, lbl)
        if self.drag_start and self.drag_current:
            x1, y1 = min(self.drag_start.x(), self.drag_current.x()), min(self.drag_start.y(), self.drag_current.y())
            x2, y2 = max(self.drag_start.x(), self.drag_current.x()), max(self.drag_start.y(), self.drag_current.y())
            ptr.setPen(QPen(QColor(100, 200, 255), 2, PEN_DASH_LINE))
            ptr.setBrush(QBrush(QColor(100, 200, 255, 40)))
            ptr.drawRect(x1, y1, x2 - x1, y2 - y1)
        ptr.end()
        self.setPixmap(pix)

    def mousePressEvent(self, e):
        if self.original_cv is None: return
        if e.button() == MOUSE_LEFT:
            hit = self._find_region_at(e.pos())
            if self.mode == "delete" and hit is not None:
                self.regions.pop(hit)
                self.hover_region = None
                self._render()
                self.regions_changed.emit()
            else:
                self.drag_start = self.drag_current = e.pos()

    def mouseMoveEvent(self, e):
        if self.original_cv is None: return
        if self.drag_start:
            self.drag_current = e.pos()
            self._render()
        else:
            hit = self._find_region_at(e.pos())
            if hit != self.hover_region:
                self.hover_region = hit
                self.setCursor(QCursor(CURSOR_FORBIDDEN if (hit is not None and self.mode == "delete") else CURSOR_CROSS))
                self._render()

    def mouseReleaseEvent(self, e):
        if self.original_cv is None or not self.drag_start: return
        if e.button() == MOUSE_LEFT and self.mode == "add":
            end = e.pos()
            x1, y1 = min(self.drag_start.x(), end.x()), min(self.drag_start.y(), end.y())
            x2, y2 = max(self.drag_start.x(), end.x()), max(self.drag_start.y(), end.y())
            if (x2 - x1) > 5 and (y2 - y1) > 5:
                s = self.display_scale
                self.regions.append({"bbox": [int(x1/s), int(y1/s), int(x2/s), int(y2/s)], "label": "手动", "source": "manual"})
                self.regions_changed.emit()
        self.drag_start = self.drag_current = None
        self._render()

    def _find_region_at(self, pt):
        s = self.display_scale
        ox, oy = pt.x() / s, pt.y() / s
        for i, r in enumerate(self.regions):
            x1, y1, x2, y2 = r["bbox"]
            if x1 <= ox <= x2 and y1 <= oy <= y2: return i
        return None

    def undo_last(self):
        if self.regions: self.regions.pop(); self._render(); self.regions_changed.emit()
    def clear_all(self):
        self.regions.clear(); self._render(); self.regions_changed.emit()
    def set_mode(self, mode):
        self.mode = mode
        self.setCursor(QCursor(CURSOR_FORBIDDEN if mode == "delete" else CURSOR_CROSS))
    def resizeEvent(self, e): super().resizeEvent(e); self._fit_and_render()
    def get_result_image(self):
        if self.original_cv is None: return None
        img = self.original_cv.copy()
        for r in self.regions: img = apply_mosaic(img, r["bbox"], CONFIG["mosaic_style"], CONFIG["mosaic_strength"])
        return img

class ScreenshotSelector(QWidget):
    captured = pyqtSignal(object)
    def __init__(self, full_screenshot):
        super().__init__()
        self.full_screenshot, self.drag_start, self.drag_current = full_screenshot, None, None
        self.setWindowFlags(WINDOW_FRAMELESS | WINDOW_TOPMOST | WINDOW_TOOL)
        self.setAttribute(WIDGET_TRANSLUCENT)
        self.setCursor(QCursor(CURSOR_CROSS))
        self.showFullScreen()
    def paintEvent(self, e):
        ptr = QPainter(self)
        ptr.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.drag_start and self.drag_current:
            x1, y1 = min(self.drag_start.x(), self.drag_current.x()), min(self.drag_start.y(), self.drag_current.y())
            x2, y2 = max(self.drag_start.x(), self.drag_current.x()), max(self.drag_start.y(), self.drag_current.y())
            ptr.setCompositionMode(PAINTER_CLEAR)
            ptr.fillRect(x1, y1, x2-x1, y2-y1, GLOBAL_TRANSPARENT)
            ptr.setCompositionMode(PAINTER_SOURCE_OVER)
            ptr.setPen(QPen(QColor(100, 200, 255), 2))
            ptr.drawRect(x1, y1, x2-x1, y2-y1)
            ptr.setPen(QPen(GLOBAL_WHITE))
            ptr.drawText(x1+4, y1-6, f"{x2-x1} × {y2-y1}")
    def mousePressEvent(self, e):
        if e.button() == MOUSE_LEFT: self.drag_start = self.drag_current = e.pos()
    def mouseMoveEvent(self, e): self.drag_current = e.pos(); self.update()
    def mouseReleaseEvent(self, e):
        if e.button() == MOUSE_LEFT and self.drag_start:
            end = e.pos()
            x1, y1 = min(self.drag_start.x(), end.x()), min(self.drag_start.y(), end.y())
            x2, y2 = max(self.drag_start.x(), end.x()), max(self.drag_start.y(), end.y())
            self.close()
            
            # 处理 High DPI 屏幕下的坐标缩放
            # ImageGrab.grab() 返回的是物理像素，而 Qt 坐标是逻辑像素
            try:
                dpr = QApplication.primaryScreen().devicePixelRatio()
            except:
                dpr = 1.0
                
            px1, py1 = int(x1 * dpr), int(y1 * dpr)
            px2, py2 = int(x2 * dpr), int(y2 * dpr)
            
            if (px2 - px1) > 10 and (py2 - py1) > 10:
                self.captured.emit(self.full_screenshot.crop((px1, py1, px2, py2)))
            else:
                self.captured.emit(self.full_screenshot)
    def keyPressEvent(self, e):
        if e.key() == KEY_ESCAPE: self.close()
