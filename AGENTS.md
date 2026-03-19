# AGENTS.md - 项目编码规范与工作指南

## 项目概述

这是一个基于 PyQt6 的桌面截图打码工具，采用云端视觉模型（SiliconFlow Qwen-VL）进行高精度 OCR 识别和隐私信息检测。

**技术栈**: Python + PyQt6 + OpenCV + 云端多模态大模型

---

## 构建与运行命令

```bash
# 安装依赖（推荐）
pip install -r requirements.txt

# 或手动安装核心依赖
pip install PyQt6 pillow opencv-python numpy requests keyboard pyperclip psutil

# 运行应用程序（从项目根目录）
python -m src.redactor

# Windows 高 DPI 支持（已内置在代码中，无需手动添加）
```

---

## 代码风格规范

### Python 代码风格
- **行长度**: 遵循自然断行，无严格限制
- **引号**: 文档字符串和字符串使用双引号，内部使用可使用单引号
- **缩进**: 4 个空格
- **尾随逗号**: 在多行数据结构中使用

### 命名规范
- **类名**: `PascalCase`（如 `MainWindow`、`ProcessWorker`）
- **函数/方法**: `snake_case`（如 `detect_by_rules`、`apply_mosaic`）
- **变量**: `snake_case`（如 `mosaic_strength`、`ocr_blocks`）
- **常量**: 模块级常量使用大写（如 `PATTERNS`、`CONFIG`）
- **私有成员**: 以下划线开头（如 `_instance`、`_setup_ui`）

### 类型提示
- 为函数参数和返回值使用类型提示
- 示例: `def recognize(cls, image: np.ndarray) -> list:`
- 可选类型: `Optional[np.ndarray]`、`Optional[int]`
- 从 `typing` 导入: `Optional`、`List`、`Dict` 等

### 导入组织
1. 标准库（sys, re, json, time, threading 等）
2. 第三方库（cv2, numpy, requests, PIL, PyQt6）
3. 本地模块（如有）
4. 组之间用空行分隔

### 文档规范
- 模块和类使用三引号文档字符串
- 复杂逻辑添加简要注释
- 中文注释可用于中文 UI 文本

### 错误处理
- 尽可能使用 try-except 捕获特定异常
- 使用 `print()` 记录错误以便可见
- 在工作线程中使用 `traceback.format_exc()` 获取完整堆栈跟踪
- 优雅降级（即使 AI 失败，应用程序也能继续运行）

### Qt 特定规范
- 信号: 在单独的 `QObject` 类中定义（如 `ProcessSignals`）
- UI 元素: 使用 `setObjectName()` 进行样式设置
- 样式表: 将大型样式表定义为模块级常量
- 线程: 使用 `QThread` 进行后台处理

### 配置规范
- 将配置存储在模块级 `CONFIG` 字典中
- 同时支持基于规则和基于 AI 的检测
- 使 AI 功能可选（优雅降级）

---

## 测试方法

目前没有正式的测试套件，需手动测试：
1. 运行 `python -m src.redactor`
2. 测试截图功能（Ctrl+Shift+S）
3. 验证 OCR 在样本图片上正常工作
4. 检查所有三种打码样式（模糊/像素/纯色块）

---

## 常用模式

### 单例模式（用于 OCR）
```python
class OCREngine:
    _instance = None
    @classmethod
    def get(cls):
        if cls._instance is None:
            # 初始化
        return cls._instance
```

### 工作线程模式
```python
class Worker(QThread):
    def __init__(self, ...):
        super().__init__()
        self.signals = Signals()
    
    def run(self):
        try:
            # 执行工作
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

---

## 项目依赖

- **PyQt6**: GUI 框架
- **pillow/PIL**: 图像处理
- **opencv-python (cv2)**: 图像处理
- **numpy**: 数值计算
- **requests**: AI API 的 HTTP 请求
- **keyboard**: 全局快捷键
- **pyperclip**: 剪贴板操作
- **psutil**: 系统工具

---

## 重要说明

- **云端识别**: 使用 SiliconFlow API，无需本地部署 OCR 模型
- **API Key**: AI 功能需要在 CONFIG 中配置 API 密钥或通过环境变量设置
- **Windows 特定**: 使用 Qt6 内置机制支持高 DPI 屏幕
- **无 CI/CD**: 目前没有正式的 CI/CD 或代码检查设置

---

## Python 路径

```
"D:\ProgramData\anaconda3\python.exe"
```

---

## 团队信息

### 角色定义
- **产品经理**: Ginsan
- **研发Agent**: Joker (我)

### 提交规范
每次Git提交都需要在commit message中备注需求编号和提交人：
```
[需求编号]: [提交类型] [描述]

Author: [Ginsan|Joker]
```

示例：
```
FEATURE-003: Feat: Add smart mosaic range optimization

Author: Joker
```

**规则说明**:
- 需求编号: FEATURE-XXX 或 BUG-XXX，放在最前面
- 提交类型: Feat|Fix|Refactor|Docs|Test|Style
- 描述: 简洁明了，说明做了什么
- 提交人: Ginsan 或 Joker

---

## 研发工作流程

### 流程概览

本项目遵循结构化的研发流程，包含 5 个检查点。作为 AI 助手，我必须在处理需求时遵循此流程。

```
需求提出 → 需求确认[CP1] → 需求分析 → 设计阶段[CP2] → 开发阶段[CP3] → 测试阶段[CP4] → 验收通过[CP5] → 已关闭
```

### AI 助手职责

1. **记录需求**: 当用户提出需求/缺陷时，记录在 `docs/requirements-pool.md`
2. **管理状态**: 跟踪需求状态（提出/分析中/设计中/开发中/测试中/已验收/已关闭）
3. **检查点确认**: 在每个检查点前始终获得用户确认后再继续
4. **文档编写**: 在开发前创建所有设计文档（PRD、UI、架构、详细设计）
5. **测试执行**: 执行自测并准备测试报告
6. **版本控制**: 所有功能文档放在 `docs/features/FEATURE-XXX/` 下

### 检查点（Checkpoint）

| 检查点 | 阶段 | 我的行动 | 用户行动 | 输出 |
|--------|------|----------|----------|------|
| **CP1** | 需求确认 | 澄清需求，确认理解 | 确认或纠正 | 需求澄清记录 |
| **CP2** | 设计完成 | 创建 PRD、UI、架构、详细设计文档 | 评审并批准 | 设计文档集 |
| **CP3** | 开发完成 | 实现代码，自测 | 验证演示 | 代码+自测报告 |
| **CP4** | 测试完成 | 创建测试用例和报告 | 评审测试报告 | 测试报告 |
| **CP5** | 验收通过 | 准备验收报告 | 签字确认 | 验收报告 |

### 需求分级

- **P0**: 核心功能 - 必须实现（如截图、OCR）
- **P1**: 重要功能 - 应该实现（如 AI 识别）
- **P2**: 优化项 - 有时间再实现（如动画效果）

### 功能特性目录结构

```
docs/features/FEATURE-XXX-功能名/
├── 01-需求文档.md    # 需求分析
├── 02-设计文档.md    # 设计文档（UI/架构/详细设计）
├── 03-测试报告.md    # 测试报告
└── 04-验收报告.md    # 验收报告
```

### 沟通协议

**申请检查点确认**:
```
【检查点X申请】
需求: FEATURE-XXX-功能名
阶段: [当前阶段]
交付物: [文件路径]

请评审，确认通过请回复"CPX通过"，有问题请指出。
```

**检查点通过**: 用户回复 "CPX通过"

**检查点失败**: 用户回复需要修改的内容

### 关键规则

1. **设计文档批准前不得开发** (CP2)
2. **代码自测通过前不得测试** (CP3)
3. **测试报告评审前不得验收** (CP4)
4. **所有文档必须在 docs/ 下版本控制**
5. **功能完成后更新实时架构文档**
6. **所有文档使用中文**（根据项目约定）

### 文档模板

**01-需求文档.md**:
- 原始需求描述
- 需求分析（可行性、技术方案）
- 功能范围（包含/不包含）
- 验收标准
- 优先级（P0/P1/P2）

**02-设计文档.md**:
- UI 设计（界面、交互）
- 架构设计（模块、接口）
- 详细设计（数据结构、算法）

**03-测试报告.md**:
- 测试用例
- 测试结果
- Bug 修复记录

**04-验收报告.md**:
- 功能演示说明
- 验收测试项
- 签字确认

---

## 外部文件引用

### 何时加载外部文件

**始终立即读取**:
- `docs/研发流程规范.md` - 研发流程规范，每次处理需求时必须阅读
- `docs/requirements-pool.md` - 需求池，了解当前待处理需求

**处理需求时读取**:
- `docs/features/FEATURE-XXX/01-需求文档.md` - 具体需求的需求文档
- `docs/features/FEATURE-XXX/02-设计文档.md` - 具体需求的设计文档
- `docs/v2026.3.18.1/01-产品需求文档.md` - 产品整体需求文档

**需要技术细节时读取**:
- `docs/系统架构文档（实时保鲜）.md` - 系统架构，修改代码前阅读
- `docs/v2026.3.18.1/03-架构设计文档.md` - 架构设计文档
- `docs/v2026.3.18.1/04-详细设计文档.md` - 详细设计文档

**需要 UI 参考时读取**:
- `docs/v2026.3.18.1/02-UI设计文档.md` - UI 设计文档

**测试时读取**:
- `docs/features/FEATURE-XXX/03-测试报告.md` - 测试报告
- `docs/features/FEATURE-XXX/04-验收报告.md` - 验收报告

### 加载策略

```
重要: 当遇到文件引用时，根据实际需要使用 Read 工具按需加载。
它们与当前特定任务相关。

说明:
- 不要预加载所有引用 - 基于实际需求使用懒加载
- 加载后，将内容视为覆盖默认值的强制性说明
- 需要时递归跟踪引用
```

---

## 快速参考

### 项目入口点
| 模块 | 路径 | 说明 |
|------|------|------|
| 主应用 | `src/redactor/__main__.py` | 程序入口 |
| 主窗口 | `src/redactor/main_window.py` | 主窗口实现 |
| UI 组件 | `src/redactor/ui.py` | 自定义控件和工作线程 |
| 核心逻辑 | `src/redactor/core.py` | 识别和打码算法 |
| 配置 | `src/redactor/config.py` | 全局配置和样式 |

### 关键文档
| 文档 | 路径 | 何时阅读 |
|------|------|----------|
| 研发流程规范 | `docs/研发流程规范.md` | 始终 |
| 需求池 | `docs/requirements-pool.md` | 始终 |
| 系统架构 | `docs/系统架构文档（实时保鲜）.md` | 编码前 |
| 产品需求 | `docs/v2026.3.18.1/01-产品需求文档.md` | 需求分析时 |
| UI 设计 | `docs/v2026.3.18.1/02-UI设计文档.md` | UI 实现时 |
| 架构设计 | `docs/v2026.3.18.1/03-架构设计文档.md` | 架构决策时 |
| 详细设计 | `docs/v2026.3.18.1/04-详细设计文档.md` | 实现细节时 |

---

## 参考文档

- **研发流程规范**: docs/研发流程规范.md
- **需求池**: docs/requirements-pool.md
- **当前迭代**: docs/requirements-active.md
- **系统架构**: docs/系统架构文档（实时保鲜）.md
- **版本基线**: docs/v2026.3.18.1/
