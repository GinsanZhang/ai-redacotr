"""
截图敏感信息自动打码工具
依赖安装：pip install PyQt5 pillow opencv-python requests keyboard pyperclip

运行：python redactor.py
快捷键：Ctrl+Shift+S 截图并处理
"""

import sys
import os
import base64
import re
import json
import time
import traceback
import ctypes
from typing import Optional
from datetime import datetime

# 尝试导入 psutil 用于资源监控
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("警告: psutil 未安装，资源监控功能不可用。安装命令: pip install psutil")

# 解决 Windows 高 DPI 屏幕截图缩放偏移问题
try:
    # 优先尝试使用 2 (Per Monitor DPI Aware V2)，这是最新的标准
    # 如果失败，则尝试 1 (Process DPI Aware)
    if not ctypes.windll.shcore.SetProcessDpiAwareness(2):
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        # 兼容旧版本 Windows
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import cv2
import numpy as np
import requests
from PIL import Image, ImageFilter, ImageGrab
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea, QFileDialog,
    QStatusBar, QFrame, QSizePolicy, QCheckBox, QComboBox,
    QSlider, QMessageBox, QShortcut, QProgressBar
)
from PyQt5.QtCore import (
    Qt, QRect, QPoint, QSize, pyqtSignal, QObject,
    QThread, QTimer, QRectF
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QPen, QBrush, QColor,
    QImage, QCursor, QFont, QKeySequence,
    QPainterPath
)

# 解决 Windows 控制台乱码问题
if sys.platform.startswith('win'):
    try:
        # Python 3.7+ 推荐方式
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        else:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

# ============================================================
# 资源监控工具
# ============================================================
def get_system_resources():
    """获取系统资源使用情况
    
    Returns:
        dict: 包含CPU、内存、磁盘使用信息的字典
    """
    resources = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cpu_percent": None,
        "memory_used_mb": None,
        "memory_total_mb": None,
        "memory_available_mb": None,
        "memory_percent": None,
        "disk_c": None,
        "disk_d": None,
    }
    
    if not PSUTIL_AVAILABLE:
        return resources
    
    try:
        # CPU 使用率
        resources["cpu_percent"] = psutil.cpu_percent(interval=1)
        
        # 内存信息
        memory = psutil.virtual_memory()
        resources["memory_used_mb"] = memory.used / (1024 * 1024)
        resources["memory_total_mb"] = memory.total / (1024 * 1024)
        resources["memory_available_mb"] = memory.available / (1024 * 1024)
        resources["memory_percent"] = memory.percent
        
        # 磁盘空间
        try:
            disk_c = psutil.disk_usage('C:\\')
            resources["disk_c"] = {
                "total_gb": disk_c.total / (1024**3),
                "used_gb": disk_c.used / (1024**3),
                "free_gb": disk_c.free / (1024**3),
                "percent": disk_c.percent
            }
        except Exception as e:
            resources["disk_c"] = {"error": str(e)}
        
        try:
            disk_d = psutil.disk_usage('D:\\')
            resources["disk_d"] = {
                "total_gb": disk_d.total / (1024**3),
                "used_gb": disk_d.used / (1024**3),
                "free_gb": disk_d.free / (1024**3),
                "percent": disk_d.percent
            }
        except Exception as e:
            resources["disk_d"] = {"error": str(e)}
            
    except Exception as e:
        resources["error"] = f"获取资源信息失败: {e}"
    
    return resources


def print_resource_status(context=""):
    """打印当前系统资源状态
    
    Args:
        context: 上下文描述，用于标记当前状态
    """
    resources = get_system_resources()
    
    print("\n" + "="*60)
    if context:
        print(f"资源监控 [{context}]")
    print(f"时间: {resources['timestamp']}")
    print("-"*60)
    
    if resources.get("error"):
        print(f"错误: {resources['error']}")
    elif not PSUTIL_AVAILABLE:
        print("psutil 未安装，无法获取资源信息")
    else:
        print(f"CPU 使用率: {resources['cpu_percent']:.1f}%")
        print(f"内存使用: {resources['memory_used_mb']:.0f} MB / {resources['memory_total_mb']:.0f} MB "
              f"({resources['memory_percent']:.1f}%)")
        print(f"内存可用: {resources['memory_available_mb']:.0f} MB")
        
        if resources["disk_c"] and "error" not in resources["disk_c"]:
            c = resources["disk_c"]
            print(f"C盘: {c['used_gb']:.1f} GB / {c['total_gb']:.1f} GB ({c['percent']}%)")
        
        if resources["disk_d"] and "error" not in resources["disk_d"]:
            d = resources["disk_d"]
            print(f"D盘: {d['used_gb']:.1f} GB / {d['total_gb']:.1f} GB ({d['percent']}%)")
    
    print("="*60 + "\n")


# ============================================================
# 配置
# ============================================================
CONFIG = {
    "llm_api_url": os.getenv("LLM_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "llm_api_key": os.getenv("LLM_API_KEY", "sk-klbzmupcizqrqdymzdadfmuflyhygkfqhqpwnujlgsbxfrmh"),
    "llm_model": os.getenv("LLM_MODEL", "Pro/moonshotai/Kimi-K2.5"),
    "llm_timeout": int(os.getenv("LLM_TIMEOUT", "180")),
    "llm_retries": int(os.getenv("LLM_RETRIES", "2")),
    "cloud_vision_api_url": os.getenv("CLOUD_VISION_API_URL", "https://api.siliconflow.cn/v1/chat/completions"),
    "cloud_vision_api_key": os.getenv("CLOUD_VISION_API_KEY", os.getenv("LLM_API_KEY", "sk-klbzmupcizqrqdymzdadfmuflyhygkfqhqpwnujlgsbxfrmh")),
    "cloud_vision_model": os.getenv("CLOUD_VISION_MODEL", "Qwen/Qwen3-VL-32B-Instruct"),
    "cloud_vision_timeout": int(os.getenv("CLOUD_VISION_TIMEOUT", "180")),
    "cloud_vision_retries": int(os.getenv("CLOUD_VISION_RETRIES", "1")),
    "cloud_image_max_side": 1800,
    "mosaic_style": "blur",   # blur | block | pixel
    "mosaic_strength": 20,    # 马赛克强度
    "ai_enabled": True,       # 是否启用AI识别
    "hotkey": "ctrl+shift+s",
    "debug_log": os.getenv("DEBUG_LOG", "1") == "1",
    "debug_log_request_body": os.getenv("DEBUG_LOG_REQUEST_BODY", "1") == "1",
    "debug_log_max_chars": int(os.getenv("DEBUG_LOG_MAX_CHARS", "2000")),
}


def dev_log(message: str, level: str = "INFO"):
    if CONFIG.get("debug_log", False):
        try:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            log_line = f"[{ts}][{level}] {message}\n"
            # 优先使用 stdout.buffer.write 确保 UTF-8 输出到终端
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write(log_line.encode('utf-8'))
                sys.stdout.buffer.flush()
            else:
                print(log_line, end='', flush=True)
        except Exception:
            try:
                # 最后的兜底方案
                print(f"[{ts}][{level}] {message}", flush=True)
            except Exception:
                pass


def mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 10:
        return "*" * len(secret)
    return f"{secret[:6]}...{secret[-4:]}"


def summarize_payload_for_log(payload: dict) -> dict:
    summary = {
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "temperature": payload.get("temperature"),
        "stream": payload.get("stream", False),
        "messages": []
    }
    for msg in payload.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            summary["messages"].append({
                "role": role,
                "content_length": len(content),
                "content_preview": content[:500]
            })
            continue
        if isinstance(content, list):
            parts = []
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    text = part.get("text", "")
                    parts.append({
                        "type": "text",
                        "text_length": len(text),
                        "text_preview": text[:300]
                    })
                elif ptype == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    parts.append({
                        "type": "image_url",
                        "url_length": len(url),
                        "url_prefix": url[:40]
                    })
                else:
                    parts.append({"type": ptype})
            summary["messages"].append({"role": role, "content_parts": parts})
            continue
        summary["messages"].append({"role": role, "content_type": str(type(content))})
    return summary


def request_chat_stream_content(api_url: str, api_key: str, payload: dict, timeout: int, stage: str, progress_cb=None):
    body = dict(payload)
    body["stream"] = True
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    if CONFIG.get("debug_log_request_body", False):
        payload_summary = summarize_payload_for_log(body)
        payload_log = json.dumps(payload_summary, ensure_ascii=False)
        if len(payload_log) > CONFIG.get("debug_log_max_chars", 2000):
            payload_log = payload_log[:CONFIG.get("debug_log_max_chars", 2000)] + "...(truncated)"
        dev_log(f"{stage}请求参数 url={api_url} timeout={timeout}s auth={mask_secret(api_key)} body={payload_log}")
    start = time.time()
    resp = requests.post(
        api_url,
        headers=headers,
        json=body,
        timeout=timeout,
        stream=True
    )
    dev_log(f"{stage}流式请求返回 status={resp.status_code}")
    if resp.status_code != 200:
        return "", resp.status_code
    parts = []
    chunk_count = 0
    char_count = 0
    for line in resp.iter_lines():
        if not line:
            continue
        try:
            line_str = line.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        if not line_str.startswith("data:"):
            continue
        data_str = line_str[5:].strip()
        if data_str == "[DONE]":
            break
        try:
            packet = json.loads(data_str)
        except Exception:
            continue
        choice = (packet.get("choices") or [{}])[0]
        delta = choice.get("delta", {}).get("content")
        if delta is None:
            delta = choice.get("message", {}).get("content")
        if delta:
            parts.append(delta)
            chunk_count += 1
            char_count += len(delta)
            if chunk_count % 10 == 0:
                dev_log(f"{stage}流式接收中 chunks={chunk_count} chars={char_count}")
            if progress_cb and chunk_count % 15 == 0:
                progress_cb(f"{stage}流式接收中，已接收 {char_count} 字符...")
    content = "".join(parts).strip()
    if content:
        dev_log(f"{stage}流式完成 chunks={chunk_count} chars={len(content)} elapsed={time.time() - start:.2f}s")
        # 如果返回内容太长，日志中只打印预览，避免控制台由于超长非 ASCII 内容导致的潜在乱码/卡顿
        preview = content if len(content) < 1000 else content[:1000] + "...(truncated)"
        dev_log(f"{stage}完整返回内容预览: {preview}")
        return content, 200
    dev_log(f"{stage}流式内容为空，回退普通响应解析", "WARN")
    body.pop("stream", None)
    resp2 = requests.post(
        api_url,
        headers=headers,
        json=body,
        timeout=timeout
    )
    if resp2.status_code != 200:
        return "", resp2.status_code
    content2 = resp2.json()["choices"][0]["message"]["content"].strip()
    dev_log(f"{stage}普通响应回退成功 chars={len(content2)} elapsed={time.time() - start:.2f}s")
    return content2, 200

# ============================================================
# 敏感信息正则规则
# ============================================================
PATTERNS = {
    "手机号":         r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "身份证":         r"\d{17}[\dXx]",
    "银行卡":         r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{0,4}(?!\d)",
    "邮箱":           r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    "IP地址":         r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "统一社会信用代码": r"[0-9A-HJ-NP-RT-Y]{18}",
    "护照":           r"[EeGg]\d{8}",
    "车牌":           r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤川青藏琼宁夏][A-Z][A-HJ-NP-Z0-9]{5,6}",
}

# ============================================================
# 敏感信息检测
# ============================================================
def detect_by_rules(ocr_blocks: list) -> list:
    """正则规则匹配，返回需要打码的 bbox 列表"""
    hits = []
    for block in ocr_blocks:
        text = block["text"]
        for label, pattern in PATTERNS.items():
            if re.search(pattern, text):
                hits.append({
                    "bbox": block["bbox"],
                    "label": label,
                    "text": text,
                    "source": "rule"
                })
                break
    return hits


def detect_by_ai(ocr_blocks: list, progress_cb=None) -> list:
    """AI识别姓名/地址等非标准敏感信息"""
    if not CONFIG["ai_enabled"] or not ocr_blocks or not CONFIG["llm_api_key"]:
        dev_log(f"AI识别跳过，ai_enabled={CONFIG['ai_enabled']} blocks={len(ocr_blocks)} has_key={bool(CONFIG['llm_api_key'])}")
        return []

    # 构造发给AI的文字列表
    items = [{"id": i, "text": b["text"]} for i, b in enumerate(ocr_blocks)]
    prompt = f"""你是一个隐私保护专家。请从以下截图中 OCR 识别出的文字块列表中，识别出所有涉及个人隐私或敏感信息的项。

待分析数据（JSON格式）：
{json.dumps(items, ensure_ascii=False, indent=2)}

识别范围：
- 姓名（包括真实姓名、昵称）
- 详细地址（家庭住址、公司精确地址）
- 职位/头衔（可能泄露身份的信息）
- 社交账号（微信号、QQ号、钉钉号等）
- 企业/组织名称（如果与个人关联紧密）
- 其他任何可能导致身份追踪或隐私泄露的信息

过滤规则：
1. 手机号、身份证、银行卡、邮箱、IP、车牌等已由规则自动识别，请忽略它们。
2. 常见的公共按钮文字（如“发送”、“确定”、“登录”）不要标记。

输出要求：
- 必须返回纯 JSON 格式，不要包含 Markdown 代码块标记（如 ```json）。
- 格式如下：{{"sensitive": [{{"id": 0, "reason": "姓名"}}, ...]}}
- 如果没有任何敏感信息，返回 {{"sensitive": []}}。"""

    retries = max(0, int(CONFIG.get("llm_retries", 0)))
    dev_log(f"AI识别开始，blocks={len(ocr_blocks)} timeout={CONFIG['llm_timeout']} retries={retries}")
    for attempt in range(retries + 1):
        if progress_cb:
            progress_cb(f"AI分析中... 第 {attempt + 1}/{retries + 1} 次请求")
        try:
            req_start = time.time()
            content, status_code = request_chat_stream_content(
                CONFIG["llm_api_url"],
                CONFIG["llm_api_key"],
                {
                    "model": CONFIG["llm_model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.1,
                },
                CONFIG["llm_timeout"],
                "AI分析",
                progress_cb
            )
            dev_log(f"AI请求完成，attempt={attempt + 1} status={status_code} elapsed={time.time() - req_start:.2f}s")
            if status_code == 200:
                if progress_cb:
                    progress_cb("AI响应已返回，解析结果中...")
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1:
                    data = json.loads(content[start:end])
                    hits = []
                    for item in data.get("sensitive", []):
                        idx = item.get("id")
                        if 0 <= idx < len(ocr_blocks):
                            hits.append({
                                "bbox": ocr_blocks[idx]["bbox"],
                                "label": item.get("reason", "AI识别"),
                                "text": ocr_blocks[idx]["text"],
                                "source": "ai"
                            })
                    if progress_cb:
                        progress_cb(f"AI解析完成，命中 {len(hits)} 处")
                    dev_log(f"AI解析成功，hits={len(hits)}")
                    return hits
                dev_log("AI响应中未找到JSON对象", "WARN")
                return []
            if status_code in (408, 429, 500, 502, 503, 504) and attempt < retries:
                if progress_cb:
                    progress_cb(f"AI服务繁忙(HTTP {status_code})，准备重试...")
                dev_log(f"AI请求可重试状态码={status_code}，sleep={1 + attempt}s", "WARN")
                time.sleep(1 + attempt)
                continue
            print(f"AI识别失败: HTTP {status_code}")
            dev_log(f"AI识别失败，HTTP {status_code}", "ERROR")
            return []
        except requests.exceptions.ReadTimeout as e:
            if attempt < retries:
                if progress_cb:
                    progress_cb("AI请求超时，准备重试...")
                dev_log(f"AI请求超时，attempt={attempt + 1}，sleep={1 + attempt}s", "WARN")
                time.sleep(1 + attempt)
                continue
            print(f"AI识别失败: {e}")
            dev_log(f"AI识别超时失败: {e}", "ERROR")
            return []
        except Exception as e:
            print(f"AI识别失败: {e}")
            dev_log(f"AI识别异常: {type(e).__name__}: {e}", "ERROR")
            return []
    return []


def detect_by_cloud_vision(image: np.ndarray, progress_cb=None) -> list:
    if not CONFIG["cloud_vision_api_key"]:
        dev_log("云端视觉跳过，未配置CLOUD_VISION_API_KEY", "WARN")
        return []
    if progress_cb:
        progress_cb("云端视觉准备中...")
    h, w = image.shape[:2]
    scale = min(1.0, float(CONFIG["cloud_image_max_side"]) / float(max(h, w)))
    if scale < 1.0:
        resized = cv2.resize(image, (int(w * scale), int(h * scale)))
    else:
        resized = image
    rh, rw = resized.shape[:2]
    dev_log(f"云端视觉开始，origin={w}x{h} resized={rw}x{rh} scale={scale:.4f}")
    ok, buf = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        dev_log("云端视觉图片编码失败", "ERROR")
        return []
    if progress_cb:
        progress_cb("云端视觉上传图片中...")
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    # 针对 Qwen-VL 优化的 Prompt，明确要求 0-1000 的归一化坐标
    # 这种坐标系统对 Vision 模型最稳定，不受图片尺寸变化的干扰
    prompt = (
        "你是一个高精度的 OCR 助手。请识别图片中所有的文字块。"
        "对于每个文字块，返回其文本内容和对应的 bbox 坐标。"
        "重要：bbox 坐标必须是基于图片尺寸归一化到 [0, 1000] 范围内的整数。"
        "格式要求：[xmin, ymin, xmax, ymax]。"
        "仅返回如下 JSON 格式，不要包含 Markdown 标记或任何解释文字：\n"
        "{\"blocks\":[{\"text\":\"...\",\"bbox\":[xmin,ymin,xmax,ymax],\"conf\":0.99}]}"
    )
    body = {
        "model": CONFIG["cloud_vision_model"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }],
        "max_tokens": 2000,
        "temperature": 0.0
    }
    retries = max(0, int(CONFIG.get("cloud_vision_retries", 0)))
    resp = None
    for attempt in range(retries + 1):
        if progress_cb:
            progress_cb(f"云端视觉识别中... 第 {attempt + 1}/{retries + 1} 次请求")
        try:
            req_start = time.time()
            content, status_code = request_chat_stream_content(
                CONFIG["cloud_vision_api_url"],
                CONFIG["cloud_vision_api_key"],
                body,
                CONFIG["cloud_vision_timeout"],
                "云端视觉",
                progress_cb
            )
            dev_log(f"云端视觉请求完成，attempt={attempt + 1} status={status_code} elapsed={time.time() - req_start:.2f}s")
            if status_code == 200:
                break
            if status_code in (408, 429, 500, 502, 503, 504) and attempt < retries:
                if progress_cb:
                    progress_cb(f"云端视觉服务繁忙(HTTP {status_code})，准备重试...")
                dev_log(f"云端视觉可重试状态码={status_code}，sleep={1 + attempt}s", "WARN")
                time.sleep(1 + attempt)
                continue
            dev_log(f"云端视觉失败，HTTP {status_code}", "ERROR")
            return []
        except requests.exceptions.ReadTimeout:
            if attempt < retries:
                if progress_cb:
                    progress_cb("云端视觉请求超时，准备重试...")
                dev_log(f"云端视觉请求超时，attempt={attempt + 1}，sleep={1 + attempt}s", "WARN")
                time.sleep(1 + attempt)
                continue
            dev_log("云端视觉请求最终超时", "ERROR")
            return []
        except Exception as e:
            dev_log(f"云端视觉异常: {type(e).__name__}: {e}", "ERROR")
            return []
    if status_code != 200:
        dev_log("云端视觉无可用响应", "ERROR")
        return []
    if progress_cb:
        progress_cb("云端视觉响应已返回，解析结果中...")
    start = content.find("{")
    end = content.rfind("}") + 1
    if start == -1 or end <= 0:
        return []
    payload = content[start:end].strip()
    data = None
    try:
        data = json.loads(payload)
    except Exception:
        normalized = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)", r'\1"\2"\3', payload)
        normalized = normalized.replace("'", '"')
        normalized = re.sub(r",\s*([}\]])", r"\1", normalized)
        try:
            data = json.loads(normalized)
        except Exception:
            blocks = []
            block_pattern = re.finditer(
                r'\{[^{}]*"text"\s*:\s*"(?P<text>(?:\\.|[^"\\])*)"[^{}]*"bbox"\s*:\s*(?P<bbox>\[[^\]]+\]|-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?)'
                r'[^{}]*?(?:"conf"\s*:\s*(?P<conf>-?\d+(?:\.\d+)?))?[^{}]*\}',
                payload,
                flags=re.S
            )
            for match in block_pattern:
                text_raw = match.group("text")
                # 智能解码：如果包含 \u 则尝试 unicode_escape，否则直接使用
                if "\\u" in text_raw:
                    try:
                        text = bytes(text_raw, "utf-8").decode("unicode_escape").strip()
                    except Exception:
                        text = text_raw.strip()
                else:
                    text = text_raw.strip()
                
                bbox_raw = match.group("bbox")
                nums = re.findall(r"-?\d+(?:\.\d+)?", bbox_raw)
                if len(nums) < 4:
                    continue
                conf_raw = match.group("conf")
                conf = float(conf_raw) if conf_raw is not None else 1.0
                blocks.append({
                    "text": text,
                    "bbox": [float(nums[0]), float(nums[1]), float(nums[2]), float(nums[3])],
                    "conf": conf
                })
            if not blocks:
                print(f"云端视觉返回内容无法解析，原始内容片段: {payload[:300]}")
                dev_log(f"云端视觉解析失败，payload_len={len(payload)}", "ERROR")
                return []
            data = {"blocks": blocks}
    blocks = data.get("blocks", [])
    if progress_cb:
        progress_cb(f"云端视觉解析完成，识别 {len(blocks)} 个文字块")
    dev_log(f"云端视觉解析完成，blocks={len(blocks)}")
    
    out = []
    for block in blocks:
        text = str(block.get("text", "")).strip()
        bbox = block.get("bbox", [])
        if not text or len(bbox) != 4:
            continue
        
        # 处理坐标映射：从 [0, 1000] 归一化坐标还原到原图尺寸
        # Qwen-VL 习惯输出 normalized [0, 1000]
        # x1, y1, x2, y2 = bbox
        nx1, ny1, nx2, ny2 = [float(v) for v in bbox]
        
        # 转换逻辑：归一化坐标 * 实际图片尺寸 / 1000
        x1 = int(nx1 * w / 1000.0)
        y1 = int(ny1 * h / 1000.0)
        x2 = int(nx2 * w / 1000.0)
        y2 = int(ny2 * h / 1000.0)

        # 边界修正
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w))
        y2 = max(0, min(y2, h))
        
        if x2 <= x1 or y2 <= y1:
            continue
            
        out.append({
            "text": text,
            "bbox": [x1, y1, x2, y2],
            "conf": float(block.get("conf", 1.0))
        })
    return out


# ============================================================
# 打码工具
# ============================================================
def apply_mosaic(image: np.ndarray, bbox: list, style: str = "blur", strength: int = 20) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    # 边界保护 + 适当扩展
    pad = 4
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(image.shape[1], x2 + pad)
    y2 = min(image.shape[0], y2 + pad)

    if x2 <= x1 or y2 <= y1:
        return image

    region = image[y1:y2, x1:x2]

    if style == "blur":
        k = max(strength | 1, 21)  # 必须是奇数
        blurred = cv2.GaussianBlur(region, (k, k), 0)
        image[y1:y2, x1:x2] = blurred

    elif style == "pixel":
        h, w = region.shape[:2]
        block = max(strength // 3, 8)
        small = cv2.resize(region, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_LINEAR)
        pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        image[y1:y2, x1:x2] = pixelated

    elif style == "block":
        image[y1:y2, x1:x2] = 0  # 纯黑

    return image


def pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def cv_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

def cv_to_qpixmap(img: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


# ============================================================
# 后台处理线程
# ============================================================
class ProcessSignals(QObject):
    progress = pyqtSignal(str)
    progress_value = pyqtSignal(int)
    finished = pyqtSignal(list, list, dict)
    error = pyqtSignal(str)


class ProcessWorker(QThread):
    def __init__(self, image_cv: np.ndarray):
        super().__init__()
        self.image_cv = image_cv
        self.signals = ProcessSignals()

    def run(self):
        try:
            timings = {}
            total_start = time.time()
            dev_log("处理流程开始")
            self.signals.progress_value.emit(5)
            self.signals.progress.emit("云端视觉识别中...")
            stage_start = time.time()
            ocr_blocks = detect_by_cloud_vision(self.image_cv, self.signals.progress.emit)
            timings["云端视觉"] = time.time() - stage_start
            dev_log(f"阶段完成 云端视觉 {timings['云端视觉']:.2f}s blocks={len(ocr_blocks)}")
            self.signals.progress_value.emit(55)
            self.signals.progress.emit(f"识别到 {len(ocr_blocks)} 个文字块，规则匹配中...")

            stage_start = time.time()
            rule_hits = detect_by_rules(ocr_blocks)
            timings["规则匹配"] = time.time() - stage_start
            dev_log(f"阶段完成 规则匹配 {timings['规则匹配']:.2f}s hits={len(rule_hits)}")
            self.signals.progress_value.emit(75)
            self.signals.progress.emit(f"规则命中 {len(rule_hits)} 处，AI分析中...")

            # 排除已被规则命中的块，减少AI token消耗
            rule_hit_texts = {h["text"] for h in rule_hits}
            remaining = [b for b in ocr_blocks if b["text"] not in rule_hit_texts]

            stage_start = time.time()
            ai_hits = detect_by_ai(remaining, self.signals.progress.emit)
            timings["AI分析"] = time.time() - stage_start
            timings["总耗时"] = time.time() - total_start
            dev_log(f"阶段完成 AI分析 {timings['AI分析']:.2f}s hits={len(ai_hits)}")
            dev_log(f"处理流程完成 总耗时 {timings['总耗时']:.2f}s total_hits={len(rule_hits) + len(ai_hits)}")
            self.signals.progress_value.emit(100)
            self.signals.progress.emit(f"AI命中 {len(ai_hits)} 处，处理完成")

            all_hits = rule_hits + ai_hits
            self.signals.finished.emit(ocr_blocks, all_hits, timings)

        except Exception as e:
            dev_log(f"处理流程异常: {type(e).__name__}: {e}", "ERROR")
            self.signals.error.emit(f"处理失败: {traceback.format_exc()}")


# ============================================================
# 图片标注画板
# ============================================================
class AnnotationCanvas(QLabel):
    """支持鼠标拖拽添加打码区域的画板"""

    regions_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.original_cv: Optional[np.ndarray] = None   # 原始图片（CV格式）
        self.display_scale = 1.0                          # 显示缩放比
        self.regions: list[dict] = []                     # [{"bbox":[x1,y1,x2,y2], "label":str}]
        self.drag_start: Optional[QPoint] = None
        self.drag_current: Optional[QPoint] = None
        self.hover_region: Optional[int] = None
        self.selected_region: Optional[int] = None
        self.mode = "add"   # add | delete

        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def load_image(self, image_cv: np.ndarray, hits: list):
        self.original_cv = image_cv.copy()
        self.regions = [{"bbox": h["bbox"], "label": h["label"], "source": h.get("source","rule")} for h in hits]
        self._fit_and_render()

    def _fit_and_render(self):
        if self.original_cv is None:
            return
        h, w = self.original_cv.shape[:2]
        max_w = self.width() or 900
        max_h = self.height() or 600
        self.display_scale = min(max_w / w, max_h / h, 1.0)
        self._render()

    def _render(self):
        if self.original_cv is None:
            return

        img = self.original_cv.copy()

        # 应用所有打码
        for region in self.regions:
            img = apply_mosaic(img, region["bbox"],
                               CONFIG["mosaic_style"], CONFIG["mosaic_strength"])

        # 缩放显示
        h, w = img.shape[:2]
        nw = int(w * self.display_scale)
        nh = int(h * self.display_scale)
        display = cv2.resize(img, (nw, nh))

        # 绘制标注框
        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, nw, nh, 3 * nw, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        for i, region in enumerate(self.regions):
            x1, y1, x2, y2 = [int(c * self.display_scale) for c in region["bbox"]]
            is_hover = i == self.hover_region
            is_ai = region.get("source") == "ai"

            color = QColor(255, 80, 80, 180) if not is_ai else QColor(255, 160, 0, 180)
            if is_hover:
                color = QColor(255, 50, 50, 220)

            pen = QPen(color, 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 30)))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

            # 标签
            label = region.get("label", "")
            if label:
                painter.setPen(QPen(Qt.white))
                painter.setBrush(QBrush(color))
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(label) + 8
                text_h = fm.height() + 4
                painter.drawRect(x1, max(0, y1 - text_h), text_w, text_h)
                painter.setPen(QPen(Qt.white))
                painter.drawText(x1 + 4, max(text_h, y1) - 3, label)

        # 绘制正在拖拽的区域
        if self.drag_start and self.drag_current:
            x1 = min(self.drag_start.x(), self.drag_current.x())
            y1 = min(self.drag_start.y(), self.drag_current.y())
            x2 = max(self.drag_start.x(), self.drag_current.x())
            y2 = max(self.drag_start.y(), self.drag_current.y())
            painter.setPen(QPen(QColor(100, 200, 255), 2, Qt.DashLine))
            painter.setBrush(QBrush(QColor(100, 200, 255, 40)))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        painter.end()
        self.setPixmap(pixmap)

    def _display_to_original(self, pt: QPoint) -> QPoint:
        return QPoint(int(pt.x() / self.display_scale),
                      int(pt.y() / self.display_scale))

    def _find_region_at(self, pt: QPoint) -> Optional[int]:
        op = self._display_to_original(pt)
        for i, region in enumerate(self.regions):
            x1, y1, x2, y2 = region["bbox"]
            if x1 <= op.x() <= x2 and y1 <= op.y() <= y2:
                return i
        return None

    def mousePressEvent(self, event):
        if self.original_cv is None:
            return
        if event.button() == Qt.LeftButton:
            hit = self._find_region_at(event.pos())
            if self.mode == "delete" and hit is not None:
                self.regions.pop(hit)
                self.hover_region = None
                self._render()
                self.regions_changed.emit()
            else:
                self.drag_start = event.pos()
                self.drag_current = event.pos()

    def mouseMoveEvent(self, event):
        if self.original_cv is None:
            return
        if self.drag_start:
            self.drag_current = event.pos()
            self._render()
        else:
            hit = self._find_region_at(event.pos())
            if hit != self.hover_region:
                self.hover_region = hit
                self.setCursor(QCursor(
                    Qt.ForbiddenCursor if (hit is not None and self.mode == "delete")
                    else Qt.CrossCursor
                ))
                self._render()

    def mouseReleaseEvent(self, event):
        if self.original_cv is None or not self.drag_start:
            return
        if event.button() == Qt.LeftButton and self.mode == "add":
            end = event.pos()
            x1 = min(self.drag_start.x(), end.x())
            y1 = min(self.drag_start.y(), end.y())
            x2 = max(self.drag_start.x(), end.x())
            y2 = max(self.drag_start.y(), end.y())
            if (x2 - x1) > 5 and (y2 - y1) > 5:
                ox1 = int(x1 / self.display_scale)
                oy1 = int(y1 / self.display_scale)
                ox2 = int(x2 / self.display_scale)
                oy2 = int(y2 / self.display_scale)
                self.regions.append({"bbox": [ox1, oy1, ox2, oy2], "label": "手动", "source": "manual"})
                self.regions_changed.emit()
        self.drag_start = None
        self.drag_current = None
        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_and_render()

    def get_result_image(self) -> Optional[np.ndarray]:
        if self.original_cv is None:
            return None
        img = self.original_cv.copy()
        for region in self.regions:
            img = apply_mosaic(img, region["bbox"],
                               CONFIG["mosaic_style"], CONFIG["mosaic_strength"])
        return img

    def clear_all(self):
        self.regions.clear()
        self._render()
        self.regions_changed.emit()

    def undo_last(self):
        if self.regions:
            self.regions.pop()
            self._render()
            self.regions_changed.emit()

    def set_mode(self, mode: str):
        self.mode = mode
        self.setCursor(QCursor(
            Qt.ForbiddenCursor if mode == "delete"
            else Qt.CrossCursor
        ))


# ============================================================
# 截图选区窗口
# ============================================================
class ScreenshotSelector(QWidget):
    """全屏半透明遮罩，鼠标拖拽选区截图"""
    captured = pyqtSignal(object)   # PIL Image

    def __init__(self, full_screenshot: Image.Image):
        super().__init__()
        self.full_screenshot = full_screenshot
        self.full_cv = pil_to_cv(full_screenshot)
        self.drag_start = None
        self.drag_current = None

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CrossCursor))
        self.showFullScreen()

    def paintEvent(self, event):
        painter = QPainter(self)
        # 半透明遮罩
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self.drag_start and self.drag_current:
            x1 = min(self.drag_start.x(), self.drag_current.x())
            y1 = min(self.drag_start.y(), self.drag_current.y())
            x2 = max(self.drag_start.x(), self.drag_current.x())
            y2 = max(self.drag_start.y(), self.drag_current.y())
            # 选区挖空
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # 选区边框
            painter.setPen(QPen(QColor(100, 200, 255), 2))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            # 尺寸提示
            painter.setPen(QPen(Qt.white))
            painter.drawText(x1 + 4, y1 - 6,
                             f"{x2-x1} × {y2-y1}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.pos()
            self.drag_current = event.pos()

    def mouseMoveEvent(self, event):
        self.drag_current = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drag_start:
            end = event.pos()
            x1 = min(self.drag_start.x(), end.x())
            y1 = min(self.drag_start.y(), end.y())
            x2 = max(self.drag_start.x(), end.x())
            y2 = max(self.drag_start.y(), end.y())
            self.close()
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                cropped = self.full_screenshot.crop((x1, y1, x2, y2))
                self.captured.emit(cropped)
            else:
                # 选区太小，用全屏
                self.captured.emit(self.full_screenshot)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    _screenshot_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.worker: Optional[ProcessWorker] = None
        self.current_cv: Optional[np.ndarray] = None
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

        # 先创建画板（toolbar 需要引用它）
        self.canvas = AnnotationCanvas()
        self.canvas.regions_changed.connect(self._on_regions_changed)

        # 顶部工具栏
        toolbar = self._make_toolbar()
        layout.addWidget(toolbar)

        # 主体：画板 + 右侧面板
        body = QHBoxLayout()
        body.setContentsMargins(12, 12, 12, 12)
        body.setSpacing(12)

        # 画板滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: #0d0d12; }")
        self.scroll.setWidget(self.canvas)

        body.addWidget(self.scroll, 1)

        # 右侧面板
        right = self._make_right_panel()
        body.addWidget(right, 0)

        layout.addLayout(body, 1)

        # 状态栏
        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar { background: #0d0d12; color: #4a5568; font-size: 12px; padding: 4px 12px; }")
        self.setStatusBar(self.status)
        self.status.showMessage("就绪  |  Ctrl+Shift+S 截图  |  左键拖拽添加打码  |  切换删除模式后点击移除")

    def _make_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("toolbar")
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # Logo
        logo = QLabel("🔒 截图打码")
        logo.setObjectName("logo")
        layout.addWidget(logo)
        layout.addStretch()

        # 截图按钮
        self.btn_capture = QPushButton("📷  区域截图")
        self.btn_capture.setObjectName("btnPrimary")
        self.btn_capture.clicked.connect(self.start_capture)
        layout.addWidget(self.btn_capture)

        self.btn_fullscreen = QPushButton("🖥  全屏截图")
        self.btn_fullscreen.setObjectName("btnSecondary")
        self.btn_fullscreen.clicked.connect(self.capture_fullscreen)
        layout.addWidget(self.btn_fullscreen)

        self.btn_open = QPushButton("📁  打开图片")
        self.btn_open.setObjectName("btnSecondary")
        self.btn_open.clicked.connect(self.open_image)
        layout.addWidget(self.btn_open)

        layout.addSpacing(16)

        # 模式切换
        self.btn_add_mode = QPushButton("✏  添加模式")
        self.btn_add_mode.setObjectName("btnMode")
        self.btn_add_mode.setCheckable(True)
        self.btn_add_mode.setChecked(True)
        self.btn_add_mode.clicked.connect(lambda: self._set_mode("add"))
        layout.addWidget(self.btn_add_mode)

        self.btn_del_mode = QPushButton("🗑  删除模式")
        self.btn_del_mode.setObjectName("btnMode")
        self.btn_del_mode.setCheckable(True)
        self.btn_del_mode.clicked.connect(lambda: self._set_mode("delete"))
        layout.addWidget(self.btn_del_mode)

        layout.addSpacing(16)

        # 撤销/清空
        btn_undo = QPushButton("↩  撤销")
        btn_undo.setObjectName("btnSecondary")
        btn_undo.clicked.connect(self.canvas.undo_last)
        layout.addWidget(btn_undo)

        btn_clear = QPushButton("🗑  清空")
        btn_clear.setObjectName("btnDanger")
        btn_clear.clicked.connect(self.canvas.clear_all)
        layout.addWidget(btn_clear)

        layout.addSpacing(16)

        # 保存
        self.btn_save = QPushButton("💾  保存图片")
        self.btn_save.setObjectName("btnSuccess")
        self.btn_save.clicked.connect(self.save_image)
        self.btn_save.setEnabled(False)
        layout.addWidget(self.btn_save)

        self.btn_copy = QPushButton("📋  复制")
        self.btn_copy.setObjectName("btnSuccess")
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        self.btn_copy.setEnabled(False)
        layout.addWidget(self.btn_copy)

        return bar

    def _make_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("rightPanel")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 打码设置
        sec1 = self._section("打码样式")
        layout.addWidget(sec1)

        self.style_combo = QComboBox()
        self.style_combo.addItems(["高斯模糊 (blur)", "像素马赛克 (pixel)", "纯黑遮罩 (block)"])
        self.style_combo.setObjectName("combo")
        self.style_combo.currentIndexChanged.connect(self._on_style_changed)
        layout.addWidget(self.style_combo)

        strength_label = QLabel("模糊强度")
        strength_label.setObjectName("smallLabel")
        layout.addWidget(strength_label)

        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(5, 50)
        self.strength_slider.setValue(CONFIG["mosaic_strength"])
        self.strength_slider.valueChanged.connect(self._on_strength_changed)
        layout.addWidget(self.strength_slider)

        # AI设置
        sec2 = self._section("AI 识别")
        layout.addWidget(sec2)

        self.ai_checkbox = QCheckBox("启用 AI 识别姓名/地址")
        self.ai_checkbox.setObjectName("checkbox")
        self.ai_checkbox.setChecked(CONFIG["ai_enabled"])
        self.ai_checkbox.toggled.connect(lambda v: CONFIG.update({"ai_enabled": v}))
        layout.addWidget(self.ai_checkbox)

        sec_progress = self._section("处理进度")
        layout.addWidget(sec_progress)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("progressBar")
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("等待处理")
        self.progress_label.setObjectName("smallLabel")
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)

        # 统计信息
        sec3 = self._section("识别统计")
        layout.addWidget(sec3)

        self.stats_label = QLabel("尚未处理图片")
        self.stats_label.setObjectName("statsLabel")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        self.timing_label = QLabel("阶段耗时：-")
        self.timing_label.setObjectName("smallLabel")
        self.timing_label.setWordWrap(True)
        layout.addWidget(self.timing_label)

        layout.addStretch()

        # 快捷键说明
        help_text = QLabel(
            "快捷键\n"
            "Ctrl+Shift+S  截图\n"
            "Ctrl+Z  撤销\n"
            "Ctrl+S  保存\n"
            "Ctrl+C  复制\n\n"
            "左键拖拽  添加打码\n"
            "删除模式下点击  移除"
        )
        help_text.setObjectName("helpText")
        layout.addWidget(help_text)

        return panel

    def _section(self, title: str) -> QLabel:
        lbl = QLabel(title)
        lbl.setObjectName("sectionTitle")
        return lbl

    def _setup_hotkey(self):
        # Qt快捷键
        QShortcut(QKeySequence("Ctrl+Shift+S"), self).activated.connect(self.start_capture)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.canvas.undo_last)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_image)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.copy_to_clipboard)

        # 全局快捷键（后台也能触发）
        try:
            import keyboard
            keyboard.add_hotkey(CONFIG["hotkey"], self._global_hotkey_triggered)
            print(f"全局快捷键已注册: {CONFIG['hotkey']}")
        except Exception as e:
            print(f"全局快捷键注册失败: {e}")
            QMessageBox.warning(
                self, "快捷键冲突",
                f"全局快捷键 {CONFIG['hotkey']} 注册失败，可能被其他软件占用。\n"
                "你可以通过软件界面上的截图按钮进行操作，或者以管理员权限重新运行。"
            )

    def _global_hotkey_triggered(self):
        # keyboard回调在子线程，需要通过信号切回主线程
        self._screenshot_signal.emit()

    # ----------------------------------------------------------
    # 截图
    # ----------------------------------------------------------
    def start_capture(self):
        """区域截图：先隐藏窗口，拉起选区遮罩"""
        self.hide()
        QTimer.singleShot(200, self._do_area_capture)

    def _do_area_capture(self):
        full = ImageGrab.grab()
        self.selector = ScreenshotSelector(full)
        self.selector.captured.connect(self._on_captured)
        self.show()

    def capture_fullscreen(self):
        self.hide()
        QTimer.singleShot(300, lambda: (
            self._on_captured(ImageGrab.grab()),
            self.show()
        ))

    def _on_captured(self, img: Image.Image):
        self.show()
        self._process_image(pil_to_cv(img))

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开图片", "", "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            img = cv2.imread(path)
            if img is not None:
                self._process_image(img)

    # ----------------------------------------------------------
    # 处理
    # ----------------------------------------------------------
    def _process_image(self, image_cv: np.ndarray):
        self.current_cv = image_cv
        self.btn_save.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.stats_label.setText("处理中...")
        self.timing_label.setText("阶段耗时：计算中...")
        self.progress_bar.setValue(0)
        self.progress_label.setText("任务开始")
        self.status.showMessage("云端视觉识别中，请稍候...")

        # 先显示原图
        self.canvas.load_image(image_cv, [])

        # 启动后台处理
        self.worker = ProcessWorker(image_cv)
        self.worker.signals.progress.connect(self._on_worker_progress)
        self.worker.signals.progress_value.connect(self.progress_bar.setValue)
        self.worker.signals.finished.connect(self._on_process_finished)
        self.worker.signals.error.connect(self._on_process_error)
        self.worker.start()

    def _on_worker_progress(self, msg: str):
        dev_log(f"UI进度: {msg}")
        self.progress_label.setText(msg)
        self.status.showMessage(msg)

    def _on_process_finished(self, ocr_blocks: list, hits: list, timings: dict):
        rule_hits = [h for h in hits if h.get("source") == "rule"]
        ai_hits   = [h for h in hits if h.get("source") == "ai"]

        self.canvas.load_image(self.current_cv, hits)
        self.btn_save.setEnabled(True)
        self.btn_copy.setEnabled(True)
        self.progress_bar.setValue(100)
        self.progress_label.setText("全部阶段完成")

        self.stats_label.setText(
            f"文字块：{len(ocr_blocks)} 个\n"
            f"规则命中：{len(rule_hits)} 处\n"
            f"AI命中：{len(ai_hits)} 处\n"
            f"合计打码：{len(hits)} 处\n\n"
            f"可手动拖拽补充\n或切换删除模式移除误判"
        )
        self.timing_label.setText(
            f"阶段耗时：云端 {timings.get('云端视觉', 0):.2f}s | "
            f"规则 {timings.get('规则匹配', 0):.2f}s | "
            f"AI {timings.get('AI分析', 0):.2f}s | "
            f"总计 {timings.get('总耗时', 0):.2f}s"
        )
        self.status.showMessage(
            f"处理完成：{len(hits)} 处敏感信息已打码  |  可手动补充或修正"
        )

    def _on_process_error(self, msg: str):
        self.status.showMessage(f"处理出错: {msg}")
        self.stats_label.setText("处理出错")
        self.progress_label.setText("处理失败")
        print(msg)

    def _on_regions_changed(self):
        count = len(self.canvas.regions)
        self.status.showMessage(f"当前打码区域：{count} 处")

    # ----------------------------------------------------------
    # 导出
    # ----------------------------------------------------------
    def save_image(self):
        result = self.canvas.get_result_image()
        if result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", f"redacted_{int(time.time())}.png",
            "PNG图片 (*.png);;JPEG图片 (*.jpg)"
        )
        if path:
            cv2.imwrite(path, result)
            self.status.showMessage(f"已保存: {path}")

    def copy_to_clipboard(self):
        result = self.canvas.get_result_image()
        if result is None:
            return
        rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        QApplication.clipboard().setImage(qimg)
        self.status.showMessage("已复制到剪贴板")

    # ----------------------------------------------------------
    # 设置
    # ----------------------------------------------------------
    def _set_mode(self, mode: str):
        self.canvas.set_mode(mode)
        self.btn_add_mode.setChecked(mode == "add")
        self.btn_del_mode.setChecked(mode == "delete")

    def _on_style_changed(self, idx: int):
        styles = ["blur", "pixel", "block"]
        CONFIG["mosaic_style"] = styles[idx]
        self.canvas._render()

    def _on_strength_changed(self, val: int):
        CONFIG["mosaic_strength"] = val
        self.canvas._render()


# ============================================================
# 样式表
# ============================================================
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


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("截图打码助手")

    window = MainWindow()
    window._screenshot_signal.connect(window.start_capture)
    window.show()

    sys.exit(app.exec())
