import os
import sys

# 基础配置
_LLM_KEY = os.getenv("LLM_API_KEY", "")
CONFIG = {
    "llm_api_url": os.getenv("LLM_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "llm_api_key": _LLM_KEY,  # 强烈建议通过环境变量 LLM_API_KEY 设置
    "llm_model": os.getenv("LLM_MODEL", "Pro/moonshotai/Kimi-K2.5"),
    "llm_timeout": int(os.getenv("LLM_TIMEOUT", "180")),
    "llm_retries": int(os.getenv("LLM_RETRIES", "2")),
    "cloud_vision_api_url": os.getenv("CLOUD_VISION_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "cloud_vision_api_key": os.getenv("CLOUD_VISION_API_KEY", _LLM_KEY),
    "cloud_vision_model": os.getenv("CLOUD_VISION_MODEL", "Qwen/Qwen3-VL-32B-Instruct"),
    "cloud_vision_timeout": int(os.getenv("CLOUD_VISION_TIMEOUT", "180")),
    "cloud_vision_retries": int(os.getenv("CLOUD_VISION_RETRIES", "1")),
    "cloud_image_max_side": 1800,
    "mosaic_style": "blur",   # blur | block | pixel
    "mosaic_strength": 20,    # 马赛克强度
    "ai_enabled": True,       # 是否启用AI识别
    "deep_ai_enabled": False,  # 是否启用深度AI识别（默认关闭，快速模式）
    "hotkey": "ctrl+shift+s",
    "debug_log": os.getenv("DEBUG_LOG", "1") == "1",
    "debug_log_request_body": os.getenv("DEBUG_LOG_REQUEST_BODY", "1") == "1",
    "debug_log_max_chars": int(os.getenv("DEBUG_LOG_MAX_CHARS", "2000")),
}

# 敏感信息正则规则
PATTERNS = {
    "手机号":         r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "身份证":         r"\d{17}[\dXx]",
    "银行卡":         r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{0,4}(?!\d)",
    "邮箱":           r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "IP地址":         r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "统一社会信用代码": r"[0-9A-HJ-NP-RT-Y]{18}",
    "护照":           r"[EeGg]\d{8}",
    "车牌":           r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏琼宁夏][A-Z][A-HJ-NP-Z0-9]{5,6}",
}

VALID_LABELS = [
    "姓名", "名字", "名称", "手机号", "手机号码", "电话", "联系电话", "手机",
    "地址", "住址", "居住地址", "家庭地址", "身份证号", "身份证号码", "身份证", "证件号",
    "银行卡", "银行卡号", "银行账号", "卡号", "邮箱", "电子邮箱", "email", "邮件",
    "职位", "职务", "职称", "岗位", "公司", "企业", "单位", "组织",
    "护照", "护照号", "驾驶证", "行驶证",
    "name", "phone", "mobile", "tel", "address", "id", "card", "email", "mail",
    "company", "position", "title", "passport", "license",
]
LABEL_DELIMITERS = ['：', ': ', ':', ' - ', '-', '——', '—', ' ', '  ']

# UI 样式表
STYLESHEET = """
QMainWindow, QWidget {
    background: #0d0d12;
    color: #e2e8f0;
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 13px;
}
#toolbar {
    background: #13131f;
    border-bottom: 1px solid #1e2030;
}
#logo {
    font-size: 16px;
    font-weight: bold;
    color: #e2e8f0;
    letter-spacing: 1px;
}
#rightPanel {
    background: #13131f;
    border-left: 1px solid #1e2030;
    border-radius: 0;
}
#sectionTitle {
    font-size: 11px;
    color: #4a5568;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding-top: 4px;
}
#smallLabel { color: #64748b; font-size: 11px; }
#statsLabel {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.8;
    background: #0d0d12;
    border-radius: 8px;
    padding: 10px;
}
#helpText {
    color: #374151;
    font-size: 11px;
    line-height: 1.8;
}
QPushButton#btnPrimary {
    background: #3b5bdb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#btnPrimary:hover { background: #2f4cbf; }
QPushButton#btnSecondary {
    background: #1e2030;
    color: #94a3b8;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton#btnSecondary:hover { background: #252840; color: #e2e8f0; }
QPushButton#btnMode {
    background: transparent;
    color: #64748b;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton#btnMode:checked {
    background: #1e3a5f;
    color: #60a5fa;
    border-color: #3b82f6;
}
QPushButton#btnMode:hover { color: #e2e8f0; }
QPushButton#btnDanger {
    background: transparent;
    color: #64748b;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton#btnDanger:hover { background: #2d1515; color: #f87171; border-color: #f87171; }
QPushButton#btnSuccess {
    background: #064e3b;
    color: #34d399;
    border: 1px solid #065f46;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#btnSuccess:hover { background: #065f46; }
QPushButton#btnSuccess:disabled { background: #1a2020; color: #2d4a3a; border-color: #1a2020; }
QPushButton#btnRecognize {
    background: #1e3a5f;
    color: #60a5fa;
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#btnRecognize:hover { background: #2563eb; color: white; }
QPushButton#btnRecognize:disabled { background: #1a2020; color: #4a5568; border-color: #2d3148; }
QComboBox#combo {
    background: #1e2030;
    color: #94a3b8;
    border: 1px solid #2d3148;
    border-radius: 8px;
    padding: 6px 10px;
}
QComboBox#combo::drop-down { border: none; }
QComboBox#combo QAbstractItemView {
    background: #1e2030;
    color: #94a3b8;
    selection-background-color: #2d3148;
}
QSlider::groove:horizontal {
    height: 4px; background: #2d3148; border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px;
    background: #3b5bdb; border-radius: 7px;
    margin: -5px 0;
}
QSlider::sub-page:horizontal { background: #3b5bdb; border-radius: 2px; }
QProgressBar#progressBar {
    border: 1px solid #2d3148;
    border-radius: 6px;
    background: #1e2030;
    color: #94a3b8;
    text-align: center;
    height: 16px;
}
QProgressBar#progressBar::chunk {
    background: #3b5bdb;
    border-radius: 6px;
}
QCheckBox#checkbox { color: #94a3b8; spacing: 8px; }
QCheckBox#checkbox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #2d3148; border-radius: 4px;
    background: #1e2030;
}
QCheckBox#checkbox::indicator:checked {
    background: #3b5bdb; border-color: #3b5bdb;
}
QScrollBar:vertical {
    width: 6px; background: transparent;
}
QScrollBar::handle:vertical {
    background: #2d3148; border-radius: 3px; min-height: 20px;
}
"""
