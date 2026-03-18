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