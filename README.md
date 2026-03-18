# 截图打码助手 (Screenshot Redactor)

一款基于 PyQt5 和云端视觉模型（SiliconFlow Qwen-VL）的高精度自动截图打码工具。

## ✨ 特性

- **云端识别**: 采用 Qwen-VL-32B-Instruct 大模型，无需本地部署复杂的 OCR 引擎。
- **高精度打码**: 自动识别 PII（个人身份信息），如姓名、地址、手机号、身份证、银行卡等。
- **实时预览**: 流式输出模型分析过程，进度条实时反馈。
- **多种模式**: 支持全局快捷键截图、全屏截图、打开本地图片。
- **手动修正**: 支持手动添加/删除打码区域，支持撤销操作。
- **多端分发**: 一键保存图片或复制到剪贴板。

## 🚀 快速开始

### 1. 环境准备

推荐使用 Anaconda 环境：

```bash
conda create -n redactor python=3.10
conda activate redactor
pip install PyQt5 pillow opencv-python requests keyboard pyperclip
```

### 2. 配置 API Key

本项目使用 [SiliconFlow](https://siliconflow.cn/) 提供的 API。请在 `redactor.py` 顶部或通过环境变量配置：

```python
CONFIG = {
    "llm_api_key": "你的_siliconflow_api_key",
    # 也可以设置环境变量 LLM_API_KEY
}
```

### 3. 运行

直接双击运行 `run.bat` 或在终端执行：

```bash
python redactor.py
```

## ⌨️ 快捷键

- **Ctrl + Shift + S**: 全局截图快捷键。
- **Ctrl + Z**: 撤销上一个手动打码块。
- **Ctrl + S**: 保存处理后的图片。
- **Ctrl + C**: 复制处理后的图片到剪贴板。

## 🛠 技术架构

- **GUI**: PyQt5
- **视觉模型**: Qwen/Qwen3-VL-32B-Instruct (via SiliconFlow)
- **逻辑引擎**: 
  - **规则引擎**: 正则表达式匹配标准格式信息（手机号、身份证等）。
  - **AI 引擎**: LLM 语义识别非标准隐私信息（姓名、地址等）。
- **DPI 适配**: 支持 Windows 高 DPI 屏幕 (Per Monitor DPI Aware V2)。

## 📝 开源协议

MIT License
