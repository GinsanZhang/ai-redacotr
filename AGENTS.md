# AGENTS.md - Coding Guidelines for This Repository

## Project Overview
This is a Python-based screenshot redaction tool with GUI using PyQt6. It's a standalone desktop application.

## Build/Run Commands

```bash
# Install dependencies
pip install PyQt6 paddleocr paddlepaddle pillow opencv-python requests keyboard pyperclip

# Run the application
python redactor.py

# Run with high DPI support (Windows)
# Add at the start of the script:
# import ctypes
# ctypes.windll.shcore.SetProcessDpiAwareness(2)
```

## Code Style Guidelines

### Python Style
- **Line length**: Follow natural breaks, no strict limit
- **Quotes**: Double quotes for docstrings/strings, single quotes acceptable for internal use
- **Indentation**: 4 spaces
- **Trailing commas**: Use in multi-line data structures

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `MainWindow`, `ProcessWorker`)
- **Functions/Methods**: `snake_case` (e.g., `detect_by_rules`, `apply_mosaic`)
- **Variables**: `snake_case` (e.g., `mosaic_strength`, `ocr_blocks`)
- **Constants**: UPPER_CASE for module-level constants (e.g., `PATTERNS`, `CONFIG`)
- **Private**: Prefix with underscore (e.g., `_instance`, `_setup_ui`)

### Type Hints
- Use type hints for function parameters and returns
- Example: `def recognize(cls, image: np.ndarray) -> list:`
- Optional types: `Optional[np.ndarray]`, `Optional[int]`
- Import from `typing`: `Optional`, `List`, `Dict` as needed

### Imports Organization
1. Standard library (sys, re, json, time, threading, etc.)
2. Third-party (cv2, numpy, requests, PIL, PyQt6)
3. Local modules (if any)
4. Blank line between groups

### Documentation
- Use triple-quoted docstrings for modules and classes
- Brief comments for complex logic
- Chinese comments acceptable for Chinese UI text

### Error Handling
- Use try-except with specific exceptions when possible
- Log errors with `print()` for visibility
- Use `traceback.format_exc()` for full stack traces in worker threads
- Graceful degradation (app continues even if AI fails)

### Qt-specific Conventions
- Signals: Define in separate `QObject` class (e.g., `ProcessSignals`)
- UI elements: Use `setObjectName()` for styling
- Stylesheet: Define large stylesheets as module-level constants
- Threading: Use `QThread` for background processing

### Configuration
- Store config in module-level `CONFIG` dict
- Support both rule-based and AI-based detection
- Make AI features optional (graceful fallback)

## Testing
No formal test suite exists. Test manually:
1. Run `python redactor.py`
2. Test screenshot capture (Ctrl+Shift+S)
3. Verify OCR works with sample images
4. Check all three mosaic styles (blur/pixel/block)

## Common Patterns

### Singleton Pattern for OCR
```python
class OCREngine:
    _instance = None
    @classmethod
    def get(cls):
        if cls._instance is None:
            # Initialize
        return cls._instance
```

### Worker Thread Pattern
```python
class Worker(QThread):
    def __init__(self, ...):
        super().__init__()
        self.signals = Signals()
    
    def run(self):
        try:
            # Do work
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

## Dependencies
- PyQt6: GUI framework
- paddleocr/paddlepaddle: OCR engine
- pillow/PIL: Image manipulation
- opencv-python (cv2): Image processing
- requests: HTTP for AI API
- keyboard: Global hotkeys
- pyperclip: Clipboard operations

## Important Notes
- First run downloads PaddleOCR models (~500MB)
- Windows-specific: Uses ctypes for DPI awareness
- AI features require API key in CONFIG
- No formal CI/CD or linting setup exists

## python path

"D:\ProgramData\anaconda3\python.exe"

---

## Development Workflow (研发流程)

### Workflow Overview

This project follows a structured R&D workflow with 5 checkpoints. As an AI assistant, I must follow this workflow when handling requirements.

```
需求提出 → 需求确认[CP1] → 需求分析 → 设计阶段[CP2] → 开发阶段[CP3] → 测试阶段[CP4] → 验收通过[CP5] → 已关闭
```

### My Responsibilities as AI Assistant

1. **Record Requirements**: When user proposes a requirement/defect, record it in docs/requirements-pool.md
2. **Manage Status**: Track requirement status (proposed/analyzing/designing/developing/testing/accepted/closed)
3. **Checkpoint Confirmation**: Always get user confirmation at each checkpoint before proceeding
4. **Documentation**: Create all design documents (PRD, UI, Architecture, Detail) before development
5. **Testing**: Perform self-testing and prepare test reports
6. **Version Control**: All feature documents go under docs/features/FEATURE-XXX/

### Checkpoints (检查点)

| Checkpoint | Stage | My Action | User Action | Output |
|------------|-------|-----------|-------------|--------|
| **CP1** | 需求确认 | Clarify requirements, confirm understanding | Confirm or correct | 需求澄清记录 |
| **CP2** | 设计完成 | Create PRD, UI, Architecture, Detail docs | Review and approve | 设计文档集 |
| **CP3** | 开发完成 | Implement code, self-test | Verify demo | 代码+自测报告 |
| **CP4** | 测试完成 | Create test cases and report | Review test report | 测试报告 |
| **CP5** | 验收通过 | Prepare acceptance report | Sign off | 验收报告 |

### Requirement Grading (需求分级)

- **P0**: Core features - Must implement (e.g., screenshot, OCR)
- **P1**: Important features - Should implement (e.g., AI recognition)
- **P2**: Nice to have - Implement if time permits (e.g., animations)

### Directory Structure for Features

```
docs/features/FEATURE-XXX-功能名/
├── 01-需求文档.md    # Requirement analysis
├── 02-设计文档.md    # Design docs (UI/Architecture/Detail)
├── 03-测试报告.md    # Test report
└── 04-验收报告.md    # Acceptance report
```

### Communication Protocol

**Requesting Checkpoint Confirmation**:
```
【检查点X申请】
需求: FEATURE-XXX-功能名
阶段: [当前阶段]
交付物: [文件路径]

请评审，确认通过请回复"CPX通过"，有问题请指出。
```

**Checkpoint Passed**: User replies "CPX通过"

**Checkpoint Failed**: User replies with modifications needed

### Key Rules

1. **No development before design docs are approved** (CP2)
2. **No testing before code self-test passes** (CP3)
3. **No acceptance before test report is reviewed** (CP4)
4. **All documents must be version controlled** under docs/
5. **Update real-time architecture doc** after feature completion
6. **Use Chinese for all documentation** (as per project convention)

### Document Templates

**01-需求文档.md**:
- 原始需求描述
- 需求分析（可行性、技术方案）
- 功能范围（包含/不包含）
- 验收标准
- 优先级（P0/P1/P2）

**02-设计文档.md**:
- UI设计（界面、交互）
- 架构设计（模块、接口）
- 详细设计（数据结构、算法）

**03-测试报告.md**:
- 测试用例
- 测试结果
- Bug修复记录

**04-验收报告.md**:
- 功能演示说明
- 验收测试项
- 签字确认

---

## External File References (外部文件引用)

### When to Load External Files (何时加载外部文件)

**ALWAYS read immediately** (立即读取):
- `docs/研发流程规范.md` - 研发流程规范，每次处理需求时必须阅读
- `docs/requirements-pool.md` - 需求池，了解当前待处理需求

**Read when handling requirements** (处理需求时读取):
- `docs/features/FEATURE-XXX/01-需求文档.md` - 具体需求的需求文档
- `docs/features/FEATURE-XXX/02-设计文档.md` - 具体需求的设计文档
- `docs/v2026.3.18.1/01-产品需求文档.md` - 产品整体需求文档

**Read for technical details** (需要技术细节时读取):
- `docs/系统架构文档（实时保鲜）.md` - 系统架构，修改代码前阅读
- `docs/v2026.3.18.1/03-架构设计文档.md` - 架构设计文档
- `docs/v2026.3.18.1/04-详细设计文档.md` - 详细设计文档

**Read for UI reference** (需要UI参考时读取):
- `docs/v2026.3.18.1/02-UI设计文档.md` - UI设计文档

**Read for testing** (测试时读取):
- `docs/features/FEATURE-XXX/03-测试报告.md` - 测试报告
- `docs/features/FEATURE-XXX/04-验收报告.md` - 验收报告

### Loading Strategy (加载策略)

```
CRITICAL: When you encounter a file reference, use your Read tool to load it on a need-to-know basis.
They're relevant to the SPECIFIC task at hand.

Instructions:
- Do NOT preemptively load all references - use lazy loading based on actual need
- When loaded, treat content as mandatory instructions that override defaults
- Follow references recursively when needed
```

---

## Quick Reference (快速参考)

### Project Entry Points
- **Main application**: `src/redactor/__main__.py`
- **Main window**: `src/redactor/main_window.py`
- **UI components**: `src/redactor/ui.py`
- **Core logic**: `src/redactor/core.py`
- **Configuration**: `src/redactor/config.py`

### Key Documents
| Document | Path | When to Read |
|----------|------|--------------|
| 研发流程规范 | `docs/研发流程规范.md` | Always |
| 需求池 | `docs/requirements-pool.md` | Always |
| 系统架构 | `docs/系统架构文档（实时保鲜）.md` | Before coding |
| 产品需求 | `docs/v2026.3.18.1/01-产品需求文档.md` | Requirement analysis |
| UI设计 | `docs/v2026.3.18.1/02-UI设计文档.md` | UI implementation |
| 架构设计 | `docs/v2026.3.18.1/03-架构设计文档.md` | Architecture decisions |
| 详细设计 | `docs/v2026.3.18.1/04-详细设计文档.md` | Implementation details |

---

## Reference Documents

- **Workflow Spec**: docs/研发流程规范.md
- **Requirements Pool**: docs/requirements-pool.md
- **Active Iteration**: docs/requirements-active.md
- **Architecture**: docs/系统架构文档（实时保鲜）.md
- **Baseline**: docs/v2026.3.18.1/