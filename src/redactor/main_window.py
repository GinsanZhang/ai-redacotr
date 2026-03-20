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

from .config import CONFIG, STYLESHEET, save_user_settings, get_model_supports_thinking
from .ui import AnnotationCanvas, ScreenshotSelector, pil_to_cv

ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
ORIENTATION_HORIZONTAL = Qt.Orientation.Horizontal
IMAGE_FORMAT_RGB888 = QImage.Format.Format_RGB888

class MainWindow(QMainWindow):
    _screenshot_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.worker, self.current_cv = None, None
        self.elapsed_timer = None
        self.recognition_start_time = None
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
            ("📷 截图", self.start_capture, "btnPrimary"),
            ("🖥 全屏", self.capture_fullscreen, "btnSecondary"),
            ("📁 打开", self.open_image, "btnSecondary")
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
        
        self.btn_save = QPushButton("💾 保存")
        self.btn_save.setObjectName("btnSuccess")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_image)
        layout.addWidget(self.btn_save)
        
        self.btn_copy = QPushButton("📋  复制")
        self.btn_copy.setObjectName("btnSuccess")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        layout.addWidget(self.btn_copy)
        
        layout.addSpacing(16)
        
        self.btn_recognize = QPushButton("🔍 识别")
        self.btn_recognize.setObjectName("btnRecognize")
        self.btn_recognize.setEnabled(False)
        self.btn_recognize.clicked.connect(self._start_recognition)
        layout.addWidget(self.btn_recognize)
        
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
        
        # 视觉识别模式章节
        layout.addWidget(self._section("视觉识别模式"))
        self.vlm_mode_combo = QComboBox()
        self.vlm_mode_combo.setObjectName("combo")
        self.vlm_mode_combo.addItem("🚀 快速", "fast")
        self.vlm_mode_combo.addItem("🔍 深度", "deep")
        vlm_mode_idx = 0 if CONFIG.get("vlm_mode", "fast") == "fast" else 1
        self.vlm_mode_combo.setCurrentIndex(vlm_mode_idx)
        self.vlm_mode_combo.setToolTip(
            "🚀 快速：关闭VLM深度思考，OCR速度更快\n"
            "🔍 深度：开启VLM深度思考，识别更精准\n"
            "\n不同模式主要影响识别速度和精度：\n"
            "- 快速：图片处理快，API返回快\n"
            "- 深度：思考更多时间，识别更准但速度较慢\n"
        )
        self.vlm_mode_combo.currentIndexChanged.connect(self._on_vlm_mode_changed)
        layout.addWidget(self.vlm_mode_combo)
        
        # VLM模型下拉框
        layout.addWidget(QLabel("VLM模型", objectName="smallLabel"))
        self.vlm_model_combo = QComboBox()
        self.vlm_model_combo.setObjectName("combo")
        for model in CONFIG.get("vlm_models", []):
            self.vlm_model_combo.addItem(model["name"], model["id"])
        idx = self.vlm_model_combo.findData(CONFIG["vlm_model"])
        if idx >= 0:
            self.vlm_model_combo.setCurrentIndex(idx)
        self.vlm_model_combo.currentIndexChanged.connect(self._on_vlm_model_changed)
        layout.addWidget(self.vlm_model_combo)
        
        # 敏感信息识别章节
        layout.addWidget(self._section("敏感信息识别"))
        self.rule_checkbox = QCheckBox("启用规则匹配")
        self.rule_checkbox.setObjectName("checkbox")
        self.rule_checkbox.setChecked(_get_user_setting("rule_enabled", True))
        self.rule_checkbox.setToolTip(
            "基于正则表达式识别格式清晰的敏感信息\n"
            "- 手机号、身份证号等，速度极快\n"
            "- 对格式清晰的信息准确率很高\n"
        )
        self.rule_checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.rule_checkbox)
        
        self.llm_checkbox = QCheckBox("启用LLM语义识别")
        self.llm_checkbox.setObjectName("checkbox")
        self.llm_checkbox.setChecked(_get_user_setting("llm_enabled", False))
        self.llm_checkbox.setToolTip(
            "使用LLM进行语义分析识别敏感信息\n"
            "- 识别姓名、地址等需要理解的敏感信息\n"
            "- 准确率更高，但会增加识别时间\n"
        )
        self.llm_checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.llm_checkbox)
        
        # LLM模型下拉框
        layout.addWidget(QLabel("LLM模型", objectName="smallLabel"))
        self.llm_model_combo = QComboBox()
        self.llm_model_combo.setObjectName("combo")
        for model in CONFIG.get("llm_models", []):
            self.llm_model_combo.addItem(model["name"], model["id"])
        idx = self.llm_model_combo.findData(CONFIG["llm_model"])
        if idx >= 0:
            self.llm_model_combo.setCurrentIndex(idx)
        self.llm_model_combo.currentIndexChanged.connect(self._on_llm_model_changed)
        layout.addWidget(self.llm_model_combo)
        
        # 处理进度章节
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
        self.current_cv = image_cv
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.canvas.clear_all()
        self.canvas.load_image(image_cv, [])
        self.stats_label.setText("已加载图片，点击「开始识别」进行识别")
        self.progress_label.setText("等待识别")
        self.progress_bar.setValue(0)
        self.timing_label.setText("阶段耗时：-")
        self.btn_recognize.setEnabled(True)
        self.btn_recognize.setText("🔍 识别")
        self.status.showMessage("图片已加载，点击「开始识别」进行识别")

    def _start_recognition(self):
        if self.current_cv is None:
            return
        from .ui import ProcessWorker
        self.btn_recognize.setEnabled(False)
        self.btn_recognize.setText("识别中...")
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.stats_label.setText("处理中...")
        self.progress_bar.setValue(0)
        self.timing_label.setText("耗时: 0.0s")
        self.recognition_start_time = time.time()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)
        self.elapsed_timer.start(100)
        self.worker = ProcessWorker(self.current_cv)
        self.worker.signals.progress.connect(self.progress_label.setText)
        self.worker.signals.progress_value.connect(self.progress_bar.setValue)
        self.worker.signals.finished.connect(self._on_process_finished)
        self.worker.signals.error.connect(self._on_process_error)
        self.worker.start()

    def _update_elapsed_time(self):
        if self.recognition_start_time:
            elapsed = time.time() - self.recognition_start_time
            self.timing_label.setText(f"耗时: {elapsed:.1f}s")

    def _on_process_finished(self, ocr, hits, timings):
        if self.elapsed_timer:
            self.elapsed_timer.stop()
            self.elapsed_timer = None
        self.canvas.load_image(self.current_cv, hits)
        self.btn_save.setEnabled(True)
        self.btn_copy.setEnabled(True)
        self.btn_recognize.setEnabled(True)
        self.btn_recognize.setText("🔍 识别")
        self.progress_bar.setValue(100)
        self.progress_label.setText("处理完成")
        self.stats_label.setText(f"文字块: {len(ocr)}\n命中: {len(hits)}\n合计打码: {len(hits)}")
        self.timing_label.setText(f"耗时: {timings.get('总耗时', 0):.2f}s")
        self.status.showMessage("处理完成")

    def _on_process_error(self, msg):
        if self.elapsed_timer:
            self.elapsed_timer.stop()
            self.elapsed_timer = None
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.btn_recognize.setEnabled(True)
        self.btn_recognize.setText("🔍 识别")
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

    def _on_vlm_mode_changed(self, idx):
        mode = self.vlm_mode_combo.currentData()
        CONFIG["vlm_mode"] = mode
        self._save_user_settings()

    def _on_vlm_model_changed(self, idx):
        model_id = self.vlm_model_combo.currentData()
        CONFIG["vlm_model"] = model_id
        self._save_user_settings()
        self.status.showMessage(f"VLM模型已切换为: {self.vlm_model_combo.currentText()}")

    def _on_llm_model_changed(self, idx):
        model_id = self.llm_model_combo.currentData()
        CONFIG["llm_model"] = model_id
        self._save_user_settings()
        self.status.showMessage(f"LLM模型已切换为: {self.llm_model_combo.currentText()}")

    def _on_checkbox_changed(self):
        self._save_user_settings()

    def _save_user_settings(self):
        settings = {
            "vlm_model": CONFIG["vlm_model"],
            "llm_model": CONFIG["llm_model"],
            "vlm_mode": CONFIG.get("vlm_mode", "fast"),
            "rule_enabled": self.rule_checkbox.isChecked(),
            "llm_enabled": self.llm_checkbox.isChecked()
        }
        save_user_settings(settings)

def _get_user_setting(key, default):
    from .config import load_user_settings
    return load_user_settings().get(key, default)
