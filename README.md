# 截图打码助手 (Screenshot Redactor)

一款基于 PyQt6 和云端多模态大模型的高精度自动截图打码工具。

## ✨ 特性

- **云端识别**: 采用 Qwen-VL-32B-Instruct 大模型进行 OCR，无需本地部署。
- **双模式识别**: 
  - **快速模式**（默认）：OCR 同时识别敏感信息，30-60秒完成
  - **深度模式**：额外进行 AI 语义分析，60-150秒，识别更精准
- **手动触发**: 截图后不自动识别，用户点击"识别"按钮后才开始，可控更灵活
- **高精度打码**: 自动识别 PII（个人身份信息），如姓名、地址、手机号、身份证、银行卡等
- **实时预览**: 流式输出模型分析过程，进度条实时反馈
- **多种截图**: 支持全局快捷键截图、全屏截图、打开本地图片
- **手动修正**: 支持手动添加/删除打码区域，支持撤销操作
- **多端分发**: 一键保存图片或复制到剪贴板

## 🚀 快速开始

### 1. 环境准备

推荐使用 Anaconda 环境：

```bash
conda create -n redactor python=3.10
conda activate redactor
pip install -r requirements.txt
```

### 2. 配置 API Key

本项目使用 [SiliconFlow](https://siliconflow.cn/) 提供的 API。通过环境变量配置：

```bash
# Windows
set LLM_API_KEY=your_api_key_here

# Linux/Mac
export LLM_API_KEY=your_api_key_here
```

或在项目根目录创建 `.env` 文件：

```
LLM_API_KEY=your_api_key_here
```

### 3. 运行

在项目根目录执行：

```bash
python -m src.redactor
```

或使用入口脚本：

```bash
python src/redactor/__main__.py
```

## ⌨️ 快捷键

- **Ctrl + Shift + S**: 全局截图快捷键。
- **Ctrl + Z**: 撤销上一个手动打码块。
- **Ctrl + S**: 保存处理后的图片。
- **Ctrl + C**: 复制处理后的图片到剪贴板。

## 🛠 技术架构

- **GUI**: PyQt6（支持高 DPI 屏幕）
- **视觉模型**: 
  - Qwen/Qwen3-VL-32B-Instruct (via SiliconFlow) - OCR 识别
  - Pro/moonshotai/Kimi-K2.5 (via SiliconFlow) - AI 语义分析（可选）
- **识别流程**:
  - **快速模式**（默认）: OCR 同时识别敏感信息 + 规则补充，30-60秒
  - **深度模式**（可选）: OCR + 规则 + AI 语义分析，60-150秒
- **规则引擎**: 正则表达式匹配标准格式信息（手机号、身份证等）
- **图像处理**: OpenCV + Pillow

## 📝 开源协议

MIT License
