import sys
import json
from datetime import datetime
from .config import CONFIG

# 尝试导入 psutil 用于资源监控
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

def get_system_resources():
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
        resources["cpu_percent"] = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        resources["memory_used_mb"] = memory.used / (1024 * 1024)
        resources["memory_total_mb"] = memory.total / (1024 * 1024)
        resources["memory_available_mb"] = memory.available / (1024 * 1024)
        resources["memory_percent"] = memory.percent
        for drive in ['C:\\', 'D:\\']:
            try:
                usage = psutil.disk_usage(drive)
                resources[f"disk_{drive[0].lower()}"] = {
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "percent": usage.percent
                }
            except: pass
    except: pass
    return resources

def dev_log(message: str, level: str = "INFO"):
    if CONFIG.get("debug_log", False):
        try:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            log_line = f"[{ts}][{level}] {message}\n"
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write(log_line.encode('utf-8'))
                sys.stdout.buffer.flush()
            else:
                print(log_line, end='', flush=True)
        except Exception:
            try:
                print(f"[{ts}][{level}] {message}", flush=True)
            except: pass

def mask_secret(secret: str) -> str:
    if not secret: return ""
    if len(secret) <= 10: return "*" * len(secret)
    return f"{secret[:6]}...{secret[-4:]}"

def summarize_payload_for_log(payload: dict) -> dict:
    summary = {
        "model": payload.get("model"),
        "max_tokens": payload.get("max_tokens"),
        "temperature": payload.get("temperature"),
        "stream": payload.get("stream", False),
        "enable_thinking": payload.get("enable_thinking"),
        "messages": []
    }
    for msg in payload.get("messages", []):
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            summary["messages"].append({"role": role, "content_preview": content[:500]})
        elif isinstance(content, list):
            parts = []
            for part in content:
                ptype = part.get("type")
                if ptype == "text":
                    parts.append({"type": "text", "text_preview": part.get("text", "")[:300]})
                elif ptype == "image_url":
                    parts.append({"type": "image_url", "url_prefix": part.get("image_url", {}).get("url", "")[:40]})
            summary["messages"].append({"role": role, "content_parts": parts})
    return summary
