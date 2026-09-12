import os
from pathlib import Path
from langchain_core.tools import tool
from backend.config import settings

@tool
def list_files(subpath: str = "") -> str:
    """Liệt kê các tệp tin và thư mục trong không gian làm việc."""
    target = (settings.WORKSPACE_DIR / subpath).resolve()
    if not str(target).startswith(str(settings.WORKSPACE_DIR.resolve())):
        return "Lỗi: Không được phép truy cập ngoài workspace."
    if not target.exists():
        return f"Đường dẫn '{subpath}' không tồn tại."
    try:
        items = os.listdir(target)
        return "\n".join(items) if items else "(Thư mục trống)"
    except Exception as e:
        return f"Lỗi đọc thư mục: {e}"

@tool
def read_file(file_path: str) -> str:
    """Đọc nội dung tệp tin trong không gian làm việc."""
    target = (settings.WORKSPACE_DIR / file_path).resolve()
    if not str(target).startswith(str(settings.WORKSPACE_DIR.resolve())):
        return "Lỗi: Không được phép đọc tệp ngoài workspace."
    if not target.exists():
        return f"Tệp '{file_path}' không tồn tại."
    try:
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(5000)
    except Exception as e:
        return f"Lỗi đọc tệp: {e}"

@tool
def write_file(file_path: str, content: str) -> str:
    """Ghi nội dung vào tệp tin trong không gian làm việc."""
    target = (settings.WORKSPACE_DIR / file_path).resolve()
    if not str(target).startswith(str(settings.WORKSPACE_DIR.resolve())):
        return "Lỗi: Không được phép ghi tệp ngoài workspace."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Đã ghi thành công tệp '{file_path}'."
    except Exception as e:
        return f"Lỗi ghi tệp: {e}"
