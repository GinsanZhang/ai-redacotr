import os
import sys
import json
from pathlib import Path

def get_config_dir() -> Path:
    return Path(__file__).parent.parent.parent / "config"

def get_default_models_config() -> dict:
    return {
        "vlm_models": {
            "default": "Qwen/Qwen3-VL-32B-Instruct",
            "models": [{"id": "Qwen/Qwen3-VL-32B-Instruct", "name": "Qwen3-VL 32B", "supports_thinking": True}]
        },
        "llm_models": {
            "default": "Pro/moonshotai/Kimi-K2.5",
            "models": [{"id": "Pro/moonshotai/Kimi-K2.5", "name": "Kimi K2.5"}]
        }
    }

def load_models_config() -> dict:
    config_path = get_config_dir() / "models.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return get_default_models_config()

def load_user_settings() -> dict:
    settings_path = get_config_dir() / "user_settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_user_settings(settings: dict):
    config_dir = get_config_dir()
    config_dir.mkdir(exist_ok=True)
    settings_path = config_dir / "user_settings.json"
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

_models_config = load_models_config()
_user_settings = load_user_settings()

_LLM_KEY = os.getenv("LLM_API_KEY", "")

CONFIG = {
    "llm_api_url": os.getenv("LLM_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "llm_api_key": _LLM_KEY,
    "llm_model": _user_settings.get("llm_model") or os.getenv("LLM_MODEL") or _models_config["llm_models"]["default"],
    "llm_timeout": int(os.getenv("LLM_TIMEOUT", "180")),
    "llm_retries": int(os.getenv("LLM_RETRIES", "2")),
    "vlm_api_url": os.getenv("VLM_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "vlm_api_key": os.getenv("VLM_API_KEY", _LLM_KEY),
    "vlm_model": _user_settings.get("vlm_model") or os.getenv("VLM_MODEL") or _models_config["vlm_models"]["default"],
    "vlm_timeout": int(os.getenv("VLM_TIMEOUT", "180")),
    "vlm_retries": int(os.getenv("VLM_RETRIES", "1")),
    "vlm_image_max_side": 1800,
    "vlm_mode": _user_settings.get("vlm_mode", "fast"),
    "mosaic_style": "blur",
    "mosaic_strength": 20,
    "ai_enabled": _user_settings.get("llm_enabled", False),
    "deep_ai_enabled": False,
    "hotkey": "ctrl+shift+s",
    "debug_log": os.getenv("DEBUG_LOG", "1") == "1",
    "debug_log_request_body": os.getenv("DEBUG_LOG_REQUEST_BODY", "1") == "1",
    "debug_log_max_chars": int(os.getenv("DEBUG_LOG_MAX_CHARS", "2000")),
    "vlm_models": _models_config["vlm_models"]["models"],
    "llm_models": _models_config["llm_models"]["models"],
    "vlm_lightweight_model": _models_config["vlm_models"].get("lightweight", "Qwen/Qwen3-VL-8B-Instruct"),
    "parallel_enabled": _models_config.get("parallel_config", {}).get("enabled", True),
    "parallel_config": _models_config.get("parallel_config", {}),
}

def get_model_supports_thinking(model_id: str) -> bool:
    for model in CONFIG.get("vlm_models", []):
        if model["id"] == model_id:
            return model.get("supports_thinking", False)
    return False

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
