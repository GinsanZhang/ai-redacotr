import base64
import re
import json
import time
import cv2
import numpy as np
import requests
from .config import CONFIG, PATTERNS, VALID_LABELS, LABEL_DELIMITERS
from .utils import dev_log, mask_secret, summarize_payload_for_log

# 支持enable_thinking的模型列表
VLM_MODELS_SUPPORT_THINKING = [
    "Pro/zai-org/GLM-5",
    "Pro/zai-org/GLM-4.7",
    "deepseek-ai/DeepSeek-V3.2",
    "Pro/deepseek-ai/DeepSeek-V3.2",
    "zai-org/GLM-4.6",
    "Qwen/Qwen3-8B",
    "Qwen/Qwen3-14B",
    "Qwen/Qwen3-32B",
    "Qwen/Qwen3-30B-A3B",
    "tencent/Hunyuan-A13B-Instruct",
    "zai-org/GLM-4.5V",
    "deepseek-ai/DeepSeek-V3.1-Terminus",
    "Pro/deepseek-ai/DeepSeek-V3.1-Terminus",
    "Qwen/Qwen3.5-397B-A17B",
    "Qwen/Qwen3.5-122B-A10B",
    "Qwen/Qwen3.5-35B-A3B",
    "Qwen/Qwen3.5-27B",
    "Qwen/Qwen3.5-9B",
    "Qwen/Qwen3.5-4B",
]


def split_label_value(text: str) -> tuple:
    """Intelligently split text into label and value parts.
    
    Uses smart delimiter detection: finds known labels followed by any separator
    (colon, space, dash, etc.) without relying on a fixed delimiter list.
    
    Returns:
        tuple: (label_part, value_part, has_label) where has_label is bool indicating
               if a valid label was found at the start of text.
    """
    text_stripped = text.strip()
    
    for label in VALID_LABELS:
        # Check if text starts with this label (case insensitive)
        if text_stripped.lower().startswith(label.lower()):
            # Find where the label ends
            label_end = len(label)
            
            # Skip any separator characters (colon, space, dash, etc.)
            separator_chars = {'：', ':', ' ', '-', '—', '──', '→', '›', '»', '|', '/', '\\', '·', '•'}
            value_start = label_end
            
            # Skip consecutive separator characters
            while value_start < len(text_stripped) and text_stripped[value_start] in separator_chars:
                value_start += 1
            
            # If we found a separator and there's content after it
            if value_start > label_end and value_start < len(text_stripped):
                value = text_stripped[value_start:].strip()
                if value:  # Ensure there's actual value content
                    return text_stripped[:label_end], value, True
    
    return "", text, False


def calculate_sensitive_bbox(full_bbox: list, full_text: str, sensitive_text: str) -> list:
    """Calculate the precise bounding box for sensitive text within a larger text block.
    
    Uses character-level positioning to determine the sub-region containing only
    the sensitive text portion.
    
    Args:
        full_bbox: [x1, y1, x2, y2] of the entire text block
        full_text: Complete text content of the block
        sensitive_text: The sensitive portion that needs mosaic
        
    Returns:
        list: [x1, y1, x2, y2] bounding box for sensitive text only
    """
    x1, y1, x2, y2 = full_bbox
    
    # If sensitive text equals full text, return full bbox
    if sensitive_text == full_text:
        return [x1, y1, x2, y2]
    
    # Handle edge cases
    if not sensitive_text or not full_text:
        return [x1, y1, x2, y2]
    
    # Find position of sensitive text in full text
    try:
        sensitive_start = full_text.index(sensitive_text)
        sensitive_end = sensitive_start + len(sensitive_text)
    except ValueError:
        # Sensitive text not found in full text, use full bbox as fallback
        return [x1, y1, x2, y2]
    
    total_chars = len(full_text)
    if total_chars == 0:
        return [x1, y1, x2, y2]
    
    # Calculate proportional position (left-to-right reading assumption)
    # This assumes characters are roughly equally spaced
    char_width = (x2 - x1) / total_chars
    
    # Calculate new bbox
    new_x1 = x1 + int(sensitive_start * char_width)
    new_x2 = x1 + int(sensitive_end * char_width)
    
    # Add small padding for better visual coverage
    padding = max(2, int(char_width * 0.5))
    new_x1 = max(x1, new_x1 - padding)
    new_x2 = min(x2, new_x2 + padding)
    
    # Ensure minimum width
    if new_x2 - new_x1 < 5:
        new_x2 = new_x1 + 5
    
    return [new_x1, y1, new_x2, y2]

def request_chat_stream_content(api_url: str, api_key: str, payload: dict, timeout: int, stage: str, progress_cb=None):
    body = dict(payload)
    body["stream"] = True
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if CONFIG.get("debug_log_request_body", False):
        payload_summary = summarize_payload_for_log(body)
        payload_log = json.dumps(payload_summary, ensure_ascii=False)
        if len(payload_log) > CONFIG.get("debug_log_max_chars", 2000):
            payload_log = payload_log[:CONFIG.get("debug_log_max_chars", 2000)] + "...(truncated)"
        dev_log(f"{stage}请求参数 url={api_url} timeout={timeout}s auth={mask_secret(api_key)} body={payload_log}")
    
    start = time.time()
    resp = requests.post(api_url, headers=headers, json=body, timeout=timeout, stream=True)
    dev_log(f"{stage}流式请求返回 status={resp.status_code}")
    if resp.status_code != 200:
        # 打印错误响应体方便调试
        try:
            error_body = resp.text
            if len(error_body) > 500:
                error_body = error_body[:500] + "...(truncated)"
            dev_log(f"{stage}错误响应体: {error_body}")
        except:
            pass
        return "", resp.status_code
    
    parts, chunk_count, char_count = [], 0, 0
    for line in resp.iter_lines():
        if not line: continue
        try: line_str = line.decode("utf-8").strip()
        except: continue
        if not line_str.startswith("data:"): continue
        data_str = line_str[5:].strip()
        if data_str == "[DONE]": break
        try: packet = json.loads(data_str)
        except: continue
        choice = (packet.get("choices") or [{}])[0]
        delta = choice.get("delta", {}).get("content") or choice.get("message", {}).get("content")
        if delta:
            parts.append(delta)
            chunk_count += 1
            char_count += len(delta)
            if chunk_count % 10 == 0: dev_log(f"{stage}流式接收中 chunks={chunk_count} chars={char_count}")
            if progress_cb and chunk_count % 15 == 0: progress_cb(f"{stage}流式接收中，已接收 {char_count} 字符...")
    
    content = "".join(parts).strip()
    if content:
        dev_log(f"{stage}流式完成 chunks={chunk_count} chars={len(content)} elapsed={time.time() - start:.2f}s")
        preview = content if len(content) < 1000 else content[:1000] + "...(truncated)"
        dev_log(f"{stage}完整返回内容预览: {preview}")
        return content, 200
    
    # 回退普通请求
    body.pop("stream", None)
    resp2 = requests.post(api_url, headers=headers, json=body, timeout=timeout)
    if resp2.status_code != 200: return "", resp2.status_code
    content2 = resp2.json()["choices"][0]["message"]["content"].strip()
    return content2, 200

def detect_by_rules(ocr_blocks: list) -> list:
    hits = []
    for block in ocr_blocks:
        text = block["text"]
        full_bbox = block["bbox"]
        
        # Check for label:value format and calculate precise sensitive bbox
        label_part, value_part, has_label = split_label_value(text)
        
        # First check patterns in the value part if label exists
        if has_label and value_part:
            for label, pattern in PATTERNS.items():
                match = re.search(pattern, value_part)
                if match:
                    # Calculate bbox for just the sensitive value
                    sensitive_bbox = calculate_sensitive_bbox(full_bbox, text, value_part)
                    hits.append({
                        "bbox": full_bbox,
                        "sensitive_bbox": sensitive_bbox,
                        "label": label,
                        "text": text,
                        "source": "rule"
                    })
                    break
            else:
                # No pattern matched in value, but has label - mosaic the value part only
                sensitive_bbox = calculate_sensitive_bbox(full_bbox, text, value_part)
                hits.append({
                    "bbox": full_bbox,
                    "sensitive_bbox": sensitive_bbox,
                    "label": label_part,
                    "text": text,
                    "source": "rule"
                })
        else:
            # No label:value format, check full text with patterns
            for label, pattern in PATTERNS.items():
                if re.search(pattern, text):
                    hits.append({
                        "bbox": full_bbox,
                        "sensitive_bbox": full_bbox,
                        "label": label,
                        "text": text,
                        "source": "rule"
                    })
                    break
    return hits

def detect_by_ai(ocr_blocks: list, progress_cb=None) -> list:
    if not CONFIG["ai_enabled"] or not ocr_blocks or not CONFIG["llm_api_key"]: return []
    
    # 根据深度模式配置参数
    is_deep_mode = CONFIG.get("deep_ai_enabled", False)
    if is_deep_mode:
        # 深度模式：更保守的参数，追求准确性
        timeout = CONFIG.get("llm_timeout", 180)
        retries = CONFIG.get("llm_retries", 2)
        temperature = 0.1
    else:
        # 快速模式：更快的响应，可能牺牲一些准确性
        timeout = 40  # 快速模式40秒超时
        retries = 1   # 快速模式只重试1次
        temperature = 0.3  # 稍微高的temperature可能更快响应
    
    items = [{"id": i, "text": b["text"]} for i, b in enumerate(ocr_blocks)]
    prompt = f"""你是一个隐私保护专家。请从以下 OCR 文字块中识别个人隐私或敏感信息。
待分析数据：{json.dumps(items, ensure_ascii=False)}
识别范围：姓名、详细地址、职位、社交账号、企业名称等。
过滤规则：手机号、身份证等已由规则处理，请忽略。不要标记公共按钮。
输出要求：返回 JSON: {{"sensitive": [{{"id": 0, "reason": "姓名"}}]}}。"""

    for attempt in range(retries + 1):
        try:
            content, status_code = request_chat_stream_content(
                CONFIG["llm_api_url"], CONFIG["llm_api_key"],
                {"model": CONFIG["llm_model"], "messages": [{"role": "user", "content": prompt}], "temperature": temperature},
                timeout, "AI分析", progress_cb
            )
            if status_code == 200:
                s, e = content.find('{'), content.rfind('}') + 1
                if s != -1:
                    data = json.loads(content[s:e])
                    hits = []
                    for item in data.get("sensitive", []):
                        idx = item.get("id")
                        if 0 <= idx < len(ocr_blocks):
                            hits.append({"bbox": ocr_blocks[idx]["bbox"], "label": item.get("reason", "AI识别"), "text": ocr_blocks[idx]["text"], "source": "ai"})
                    return hits
        except Exception as e: dev_log(f"AI分析异常: {e}", "ERROR")
    return []

def detect_by_vlm(image: np.ndarray, progress_cb=None, include_sensitive=False, vlm_mode: str = "fast"):
    """
    使用VLM(视觉语言模型)进行OCR识别
    
    参数:
        image: OpenCV图像
        progress_cb: 进度回调函数
        include_sensitive: 是否同时识别敏感信息，默认False
        vlm_mode: VLM识别模式 "fast"|"deep"，默认"fast"
            - fast: 温度0.0，关闭深度思考，识别更快
            - deep: 温度0.3，开启深度思考，识别更准
    
    返回:
        include_sensitive=False时: list - OCR结果列表
        include_sensitive=True时: dict - {"ocr_blocks": [...], "sensitive_hits": [...]}
    """
    if not CONFIG["vlm_api_key"]:
        raise RuntimeError("未配置VLM API Key，请设置 LLM_API_KEY 或 VLM_API_KEY")
    h, w = image.shape[:2]
    scale = min(1.0, 1800.0 / max(h, w))
    resized = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 1.0 else image
    ok, buf = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok: 
        return [] if not include_sensitive else {"ocr_blocks": [], "sensitive_hits": []}
    
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    
    # 根据模式设置temperature
    if vlm_mode == "fast":
        temperature = 0.0  # 快速模式：确定输出，更快
    else:
        temperature = 0.3  # 深度模式：更灵活，更准确
    
    # 根据参数选择Prompt
    if include_sensitive:
        prompt = """你是一个高精度的 OCR 助手和隐私保护专家。

请识别图片中所有的文字块，并判断哪些是敏感信息。

敏感信息类型包括：
- 姓名（人名）
- 详细地址
- 手机号
- 身份证号
- 银行卡号
- 邮箱
- 职位/职称
- 企业名称
- 其他个人隐私

重要：bbox 坐标必须是基于图片尺寸归一化到 [0, 1000] 范围内的整数。

对于敏感信息，如果包含标签（如"姓名：张三"），需要返回两个坐标：
- bbox: 整个文字块的坐标
- sensitive_bbox: 仅敏感值部分的坐标（如"张三"的位置）

输出格式：
{
  "blocks": [
    {
      "text": "识别文字",
      "bbox": [xmin, ymin, xmax, ymax],
      "is_sensitive": true/false,
      "sensitive_type": "姓名/地址/手机号等",
      "sensitive_bbox": [xmin, ymin, xmax, ymax]  // 仅当is_sensitive为true时，返回敏感值部分的精确坐标
    }
  ]
}"""
    else:
        prompt = "你是一个高精度的 OCR 助手。请识别图片中所有的文字块。重要：bbox 坐标必须是基于图片尺寸归一化到 [0, 1000] 范围内的整数。格式：{\"blocks\":[{\"text\":\"...\",\"bbox\":[xmin,ymin,xmax,ymax]}]}"
    
    # 构建请求体（使用模型默认参数，不手动调整）
    body = {
        "model": CONFIG["vlm_model"],
        "messages": [{"role": "user", "content": [{"type":"text", "text":prompt}, {"type":"image_url", "image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}],
    }
    
    # enable_thinking仅在深度模式且模型支持时才传递
    if vlm_mode == "deep" and CONFIG["vlm_model"] in VLM_MODELS_SUPPORT_THINKING:
        body["enable_thinking"] = True
    
    content, status_code = request_chat_stream_content(
        CONFIG["vlm_api_url"], CONFIG["vlm_api_key"],
        body, CONFIG["vlm_timeout"], "VLM识别", progress_cb
    )
    if status_code != 200:
        if status_code == 401:
            raise RuntimeError("VLM识别鉴权失败(401)，请检查 API Key 是否正确或权限是否开通")
        if status_code == 403:
            raise RuntimeError("VLM识别无权限访问(403)，请检查账号权限或模型权限")
        raise RuntimeError(f"VLM识别请求失败，HTTP {status_code}")

    s, e = content.find('{'), content.rfind('}') + 1
    if s == -1:
        raise RuntimeError("VLM识别返回内容缺少 JSON 数据")
    try:
        data = json.loads(content[s:e])
    except Exception:
        raise RuntimeError("VLM识别返回格式无法解析，请稍后重试")
    
    blocks = data.get("blocks", [])
    
    if include_sensitive:
        # 新模式：同时返回OCR结果和敏感信息
        ocr_blocks = []
        sensitive_hits = []
        
        for b in blocks:
            text_raw, bbox = str(b.get("text", "")), b.get("bbox", [])
            if not text_raw or len(bbox) != 4: 
                continue
            
            text = bytes(text_raw, "utf-8").decode("unicode_escape").strip() if "\\u" in text_raw else text_raw.strip()
            nx1, ny1, nx2, ny2 = [float(v) for v in bbox]
            x1, y1 = int(nx1 * w / 1000.0), int(ny1 * h / 1000.0)
            x2, y2 = int(nx2 * w / 1000.0), int(ny2 * h / 1000.0)
            
            pixel_bbox = [max(0, x1), max(0, y1), min(w, x2), min(h, y2)]
            
            # 添加到OCR结果
            ocr_blocks.append({
                "text": text, 
                "bbox": pixel_bbox, 
                "conf": float(b.get("conf", 1.0))
            })
            
            # 如果是敏感信息，加入hits
            if b.get("is_sensitive", False):
                # 优先使用视觉模型返回的敏感值坐标
                model_sensitive_bbox = b.get("sensitive_bbox")
                if model_sensitive_bbox and len(model_sensitive_bbox) == 4:
                    # 转换归一化坐标到像素坐标
                    sx1, sy1, sx2, sy2 = [float(v) for v in model_sensitive_bbox]
                    sensitive_bbox = [
                        max(0, int(sx1 * w / 1000.0)),
                        max(0, int(sy1 * h / 1000.0)),
                        min(w, int(sx2 * w / 1000.0)),
                        min(h, int(sy2 * h / 1000.0))
                    ]
                else:
                    # 回退到智能分隔符估算
                    label_part, value_part, has_label = split_label_value(text)
                    if has_label and value_part:
                        sensitive_bbox = calculate_sensitive_bbox(pixel_bbox, text, value_part)
                    else:
                        sensitive_bbox = pixel_bbox
                
                sensitive_hits.append({
                    "bbox": pixel_bbox,
                    "sensitive_bbox": sensitive_bbox,
                    "label": b.get("sensitive_type", "敏感信息"),
                    "text": text,
                    "source": "ai"
                })
        
        return {"ocr_blocks": ocr_blocks, "sensitive_hits": sensitive_hits}
    else:
        # 原模式：仅返回OCR结果
        out = []
        for b in blocks:
            text_raw, bbox = str(b.get("text", "")), b.get("bbox", [])
            if not text_raw or len(bbox) != 4: 
                continue
            text = bytes(text_raw, "utf-8").decode("unicode_escape").strip() if "\\u" in text_raw else text_raw.strip()
            nx1, ny1, nx2, ny2 = [float(v) for v in bbox]
            x1, y1 = int(nx1 * w / 1000.0), int(ny1 * h / 1000.0)
            x2, y2 = int(nx2 * w / 1000.0), int(ny2 * h / 1000.0)
            out.append({
                "text": text, 
                "bbox": [max(0, x1), max(0, y1), min(w, x2), min(h, y2)], 
                "conf": float(b.get("conf", 1.0))
            })
        return out

def apply_mosaic(image: np.ndarray, bbox: list, style: str = "blur", strength: int = 20, sensitive_bbox: list = None) -> np.ndarray:
    # Use sensitive_bbox if provided (for precise mosaic), otherwise use full bbox
    if sensitive_bbox is not None:
        x1, y1, x2, y2 = sensitive_bbox
    else:
        x1, y1, x2, y2 = bbox
    
    p = 4
    x1, y1 = max(0, x1 - p), max(0, y1 - p)
    x2, y2 = min(image.shape[1], x2 + p), min(image.shape[0], y2 + p)
    if x2 <= x1 or y2 <= y1: return image
    
    region = image[y1:y2, x1:x2]
    if style == "blur":
        k = max(strength | 1, 21)
        image[y1:y2, x1:x2] = cv2.GaussianBlur(region, (k, k), 0)
    elif style == "pixel":
        h, w = region.shape[:2]
        block = max(strength // 3, 8)
        small = cv2.resize(region, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_LINEAR)
        image[y1:y2, x1:x2] = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    elif style == "block":
        image[y1:y2, x1:x2] = 0
    return image