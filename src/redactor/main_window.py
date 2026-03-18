import time
import cv2
from PIL import ImageGrab
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QFileDialog,
    QStatusBar, QFrame, QSizePolicy, QCheckBox, QComboBox,
    QSlider, QMessageBox, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QShortcut

from .config import CONFIG, STYLESHEET
from .ui import AnnotationCanvas, ScreenshotSelector, pil_to_cv

ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
ORIENTATION_HORIZONTAL = Qt.Orientation.Horizontal
IMAGE_FORMAT_RGB888 = QImage.Format.Format_RGB888

class MainWindow(QMainWindow):
    _screenshot_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.worker, self.current_cv = None, None
        self._setup_ui()
        self._setup_hotkey()

    def _setup_ui(self):
        self.setWindowTitle("截图打码助手")
        self.setMinimumSize(960, 680)
        self.resize(1100, 760)
        self.setStyleSheet(STYLESHEET)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.canvas = AnnotationCanvas()
        self.canvas.regions_changed.connect(self._on_regions_changed)
        
        layout.addWidget(self._make_toolbar())
        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(ALIGN_CENTER)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: #0d0d12; }")
        self.scroll.setWidget(self.canvas)
        body.addWidget(self.scroll, 1)
        body.addWidget(self._make_right_panel(), 0)
        layout.addLayout(body, 1)
        
        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar { background: #0d0d12; color: #4a5568; font-size: 12px; padding: 4px 12px; }")
        self.setStatusBar(self.status)
        self.status.showMessage("就绪  |  Ctrl+Shift+S 截图")

    def _make_toolbar(self):
        bar = QWidget()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)
        
        logo = QLabel("🔒 截图打码")
        logo.setObjectName("logo")
        layout.addWidget(logo)
        layout.addStretch()
        
        for text, func, obj_name in [
            ("📷  区域截图", self.start_capture, "btnPrimary"),
            ("🖥  全屏截图", self.capture_fullscreen, "btnSecondary"),
            ("📁  打开图片", self.open_image, "btnSecondary")
        ]:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(func)
            layout.addWidget(btn)
        
        layout.addSpacing(16)
        
        self.btn_add_mode = QPushButton("✏  添加模式")
        self.btn_add_mode.setCheckable(True)
        self.btn_add_mode.setChecked(True)
        self.btn_add_mode.setObjectName("btnMode")
        self.btn_add_mode.clicked.connect(lambda: self._set_mode("add"))
        layout.addWidget(self.btn_add_mode)
        
        self.btn_del_mode = QPushButton("🗑  删除模式")
        self.btn_del_mode.setCheckable(True)
        self.btn_del_mode.setObjectName("btnMode")
        self.btn_del_mode.clicked.connect(lambda: self._set_mode("delete"))
        layout.addWidget(self.btn_del_mode)
        
        layout.addSpacing(16)
        
        for text, func, obj_name in [
            ("↩  撤销", self.canvas.undo_last, "btnSecondary"),
            ("🗑  清空", self.canvas.clear_all, "btnDanger")
        ]:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(func)
            layout.addWidget(btn)
            
        layout.addSpacing(16)
        
        self.btn_save = QPushButton("💾  保存图片")
        self.btn_save.setObjectName("btnSuccess")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_image)
        layout.addWidget(self.btn_save)
        
        self.btn_copy = QPushButton("📋  复制")
        self.btn_copy.setObjectName("btnSuccess")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.btn_copy)
        
        return bar

    def _make_right_panel(self):
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        layout.addWidget(self._section("打码样式"))
        self.style_combo = QComboBox()
        self.style_combo.addItems(["高斯模糊 (blur)", "像素马赛克 (pixel)", "纯黑遮罩 (block)"])
        self.style_combo.setObjectName("combo")
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)
        
        layout.addWidget(QLabel("模糊强度", objectName="smallLabel"))
        self.strength_slider = QSlider(ORIENTATION_HORIZONTAL)
        self.strength_slider.setRange(5, 50)
        self.strength_slider.setValue(CONFIG["mosaic_strength"])
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        layout.addWidget(self.strength_slider)
        
        layout.addWidget(self._section("AI 识别"))
        self.ai_checkbox = QCheckBox("启用 AI 识别姓名/地址")
        self.ai_checkbox.setObjectName("checkbox")
        self.ai_checkbox.setChecked(CONFIG["ai_enabled"])
        self.ai_checkbox.toggled.connect(lambda v: CONFIG.update({"ai_enabled": v}))
        layout.addWidget(self.ai_checkbox)
        
        layout.addWidget(self._section("处理进度"))
        self.progress_bar = QProgressBar(objectName="progressBar")
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("等待处理", objectName="smallLabel", wordWrap=True)
        layout.addWidget(self.progress_label)
        
        layout.addWidget(self._section("识别统计"))
        self.stats_label = QLabel("尚未处理图片", objectName="statsLabel", wordWrap=True)
        layout.addWidget(self.stats_label)
        
        self.timing_label = QLabel("阶段耗时：-", objectName="smallLabel", wordWrap=True)
        layout.addWidget(self.timing_label)
        
        layout.addStretch()
        layout.addWidget(QLabel(
            "快捷键\nCtrl+Shift+S 截图\nCtrl+Z 撤销\nCtrl+S 保存\nCtrl+C 复制",
            objectName="helpText"
        ))
        return panel

    def _section(self, title):
        lbl = QLabel(title)
        lbl.setObjectName("sectionTitle")
        return lbl

    def _setup_hotkey(self):
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.start_capture)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.canvas.undo_last)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_image)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.copy_to_clipboard)
        try:
            import keyboard
            keyboard.add_hotkey(CONFIG["hotkey"], self._screenshot_signal.emit)
        except: pass

    def start_capture(self):
        self.hide()
        QTimer.singleShot(200, self._do_area_capture)

    def _do_area_capture(self):
        self.selector = ScreenshotSelector(ImageGrab.grab())
        self.selector.captured.connect(self._on_captured)
        self.show()

    def capture_fullscreen(self):
        self.hide()
        QTimer.singleShot(300, lambda: (self._on_captured(ImageGrab.grab()), self.show()))

    def _on_captured(self, img):
        self.show()
        self._process_image(pil_to_cv(img))

    def open_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "打开图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if p:
            img = cv2.imread(p)
            if img is not None: self._process_image(img)

    def _process_image(self, image_cv):
        from .ui import ProcessWorker
        self.current_cv = image_cv
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.stats_label.setText("处理中...")
        self.progress_bar.setValue(0)
        self.canvas.load_image(image_cv, [])
        self.worker = ProcessWorker(image_cv)
        self.worker.signals.progress.connect(self.progress_label.setText)
        self.worker.signals.progress_value.connect(self.progress_bar.setValue)
        self.worker.signals.finished.connect(self._on_process_finished)
        self.worker.signals.error.connect(self._on_process_error)
        self.worker.start()

    def _on_process_finished(self, ocr, hits, timings):
        self.canvas.load_image(self.current_cv, hits)
        self.btn_save.setEnabled(True)
        self.btn_copy.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_label.setText("处理完成")
        self.stats_label.setText(f"文字块: {len(ocr)}\n命中: {len(hits)}\n合计打码: {len(hits)}")
        self.timing_label.setText(f"耗时: {timings.get('总耗时', 0):.2f}s")
        self.status.showMessage("处理完成")

    def _on_process_error(self, msg):
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("处理失败")
        self.stats_label.setText("识别失败，请检查 Key、网络或服务权限")
        self.timing_label.setText("阶段耗时：-")
        self.status.showMessage(f"错误: {msg}")

    def _on_regions_changed(self):
        self.status.showMessage(f"当前打码区域：{len(self.canvas.regions)} 处")

    def save_image(self):
        res = self.canvas.get_result_image()
        if res is not None:
            p, _ = QFileDialog.getSaveFileName(self, "保存图片", f"redacted_{int(time.time())}.png", "PNG (*.png);;JPG (*.jpg)")
            if p: cv2.imwrite(p, res); self.status.showMessage(f"已保存: {p}")

    def copy_to_clipboard(self):
        res = self.canvas.get_result_image()
        if res is not None:
            rgb = cv2.cvtColor(res, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            QApplication.clipboard().setImage(QImage(rgb.data, w, h, ch * w, IMAGE_FORMAT_RGB888))
            self.status.showMessage("已复制到剪贴板")

    def _set_mode(self, mode):
        self.canvas.set_mode(mode)
        self.btn_add_mode.setChecked(mode == "add")
        self.btn_del_mode.setChecked(mode == "delete")

    def _on_style_changed(self, idx):
        CONFIG["mosaic_style"] = ["blur", "pixel", "block"][idx]
        self.canvas._render()

    def _on_strength_changed(self, v):
        CONFIG["mosaic_strength"] = v
        self.canvas._render()
