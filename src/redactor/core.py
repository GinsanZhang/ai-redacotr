import base64
import re
import json
import time
import cv2
import numpy as np
import requests
from .config import CONFIG, PATTERNS
from .utils import dev_log, mask_secret, summarize_payload_for_log

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
    if resp.status_code != 200: return "", resp.status_code
    
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
        for label, pattern in PATTERNS.items():
            if re.search(pattern, text):
                hits.append({"bbox": block["bbox"], "label": label, "text": text, "source": "rule"})
                break
    return hits

def detect_by_ai(ocr_blocks: list, progress_cb=None) -> list:
    if not CONFIG["ai_enabled"] or not ocr_blocks or not CONFIG["llm_api_key"]: return []
    items = [{"id": i, "text": b["text"]} for i, b in enumerate(ocr_blocks)]
    prompt = f"""你是一个隐私保护专家。请从以下 OCR 文字块中识别个人隐私或敏感信息。
待分析数据：{json.dumps(items, ensure_ascii=False)}
识别范围：姓名、详细地址、职位、社交账号、企业名称等。
过滤规则：手机号、身份证等已由规则处理，请忽略。不要标记公共按钮。
输出要求：返回 JSON: {{"sensitive": [{{"id": 0, "reason": "姓名"}}]}}。"""

    retries = CONFIG.get("llm_retries", 2)
    for attempt in range(retries + 1):
        try:
            content, status_code = request_chat_stream_content(
                CONFIG["llm_api_url"], CONFIG["llm_api_key"],
                {"model": CONFIG["llm_model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.1},
                CONFIG["llm_timeout"], "AI分析", progress_cb
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

def detect_by_cloud_vision(image: np.ndarray, progress_cb=None, include_sensitive=False):
    """
    使用云端多模态模型进行OCR识别
    
    参数:
        image: OpenCV图像
        progress_cb: 进度回调函数
        include_sensitive: 是否同时识别敏感信息，默认False
    
    返回:
        include_sensitive=False时: list - OCR结果列表
        include_sensitive=True时: dict - {"ocr_blocks": [...], "sensitive_hits": [...]}
    """
    if not CONFIG["cloud_vision_api_key"]:
        raise RuntimeError("未配置云端视觉 API Key，请设置 LLM_API_KEY 或 CLOUD_VISION_API_KEY")
    h, w = image.shape[:2]
    scale = min(1.0, 1800.0 / max(h, w))
    resized = cv2.resize(image, (int(w * scale), int(h * scale))) if scale < 1.0 else image
    ok, buf = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok: 
        return [] if not include_sensitive else {"ocr_blocks": [], "sensitive_hits": []}
    
    b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
    
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

输出格式：
{
  "blocks": [
    {
      "text": "识别文字",
      "bbox": [xmin, ymin, xmax, ymax],
      "is_sensitive": true/false,
      "sensitive_type": "姓名/地址/手机号等"
    }
  ]
}"""
    else:
        prompt = "你是一个高精度的 OCR 助手。请识别图片中所有的文字块。重要：bbox 坐标必须是基于图片尺寸归一化到 [0, 1000] 范围内的整数。格式：{\"blocks\":[{\"text\":\"...\",\"bbox\":[xmin,ymin,xmax,ymax]}]}"
    
    body = {
        "model": CONFIG["cloud_vision_model"],
        "messages": [{"role": "user", "content": [{"type":"text", "text":prompt}, {"type":"image_url", "image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}],
        "temperature": 0.0
    }
    
    content, status_code = request_chat_stream_content(
        CONFIG["cloud_vision_api_url"], CONFIG["cloud_vision_api_key"],
        body, CONFIG["cloud_vision_timeout"], "云端视觉", progress_cb
    )
    if status_code != 200:
        if status_code == 401:
            raise RuntimeError("云端视觉鉴权失败(401)，请检查 API Key 是否正确或权限是否开通")
        if status_code == 403:
            raise RuntimeError("云端视觉无权限访问(403)，请检查账号权限或模型权限")
        raise RuntimeError(f"云端视觉请求失败，HTTP {status_code}")

    s, e = content.find('{'), content.rfind('}') + 1
    if s == -1:
        raise RuntimeError("云端视觉返回内容缺少 JSON 数据")
    try:
        data = json.loads(content[s:e])
    except Exception:
        raise RuntimeError("云端视觉返回格式无法解析，请稍后重试")
    
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
                sensitive_hits.append({
                    "bbox": pixel_bbox,
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

def apply_mosaic(image: np.ndarray, bbox: list, style: str = "blur", strength: int = 20) -> np.ndarray:
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