"""图片来源解析模块 —— 剪贴板与拖放的"取图片路径"逻辑

需求来源：Requires/Requirements/Update_require_2026-10-13_2.md

职责边界（刻意收窄）：
- 只负责"从剪贴板/拖放拿到一个可用的图片文件路径"，以及剪贴板位图的落盘归档
- **不做 OCR、不调 AI、不写 json/ai**
- 拿到路径后由 ``window/table_qt.py`` 交给现有的 ``_ai_fill_from_path()`` 走完整链路
  （识别 → 预览 → 填入），因此本模块不重复任何既有业务逻辑
"""
import atexit
import os
import shutil
import tempfile
from datetime import datetime

from src.app_paths import app_root, runtime_subdir

SUPPORTED_IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.bmp'}
SUPPORTED_HTML_EXTS = {'.html', '.htm'}
ARCHIVE_ROOT = "pic"        # 归档到 <软件目录>/pic/<YYYY-MM-DD>/

_FALLBACK_DIR = None        # 归档失败时降级用的临时目录（惰性创建，退出清理）


def is_supported_image(path) -> bool:
    """是否为受支持的图片文件（仅看扩展名，不检查存在性）"""
    if not path:
        return False
    return os.path.splitext(str(path))[1].lower() in SUPPORTED_IMAGE_EXTS


def archive_dir(date: str = None) -> str:
    """剪贴板图片的归档目录：<软件目录>/pic/<YYYY-MM-DD>/"""
    day = date or datetime.now().strftime("%Y-%m-%d")
    return os.path.join(runtime_subdir(ARCHIVE_ROOT), day)


def fallback_dir() -> str:
    """降级目录：系统临时目录下的独立子目录（惰性创建，进程退出时清理）"""
    global _FALLBACK_DIR
    if _FALLBACK_DIR is None or not os.path.isdir(_FALLBACK_DIR):
        _FALLBACK_DIR = tempfile.mkdtemp(prefix="excel_clip_")
        atexit.register(_cleanup_fallback)
    return _FALLBACK_DIR


def _cleanup_fallback():
    global _FALLBACK_DIR
    if _FALLBACK_DIR and os.path.isdir(_FALLBACK_DIR):
        shutil.rmtree(_FALLBACK_DIR, ignore_errors=True)
    _FALLBACK_DIR = None


def _unique_path(directory: str, stem: str) -> str:
    """同名时追加 _2/_3…，避免同一秒内多次粘贴互相覆盖"""
    path = os.path.join(directory, stem + ".png")
    n = 2
    while os.path.exists(path):
        path = os.path.join(directory, stem + f"_{n}.png")
        n += 1
    return path


def save_qimage(qimage, logger=None) -> str:
    """把剪贴板位图存成 PNG。

    优先写入 ``pic/<日期>/``；若归档失败（磁盘满 / 无权限 / 目录被占用）则
    **降级到系统临时目录**，保证主流程不被阻断。

    Returns: 落盘后的绝对路径；两种位置都失败时返回 None
    """
    stem = "clipboard_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    for directory in (archive_dir(), fallback_dir()):
        try:
            os.makedirs(directory, exist_ok=True)
            path = _unique_path(directory, stem)
            if qimage.save(path, "PNG"):
                if logger:
                    logger.info(f"剪贴板图片已保存: {path}")
                return path
            if logger:
                logger.warning(f"剪贴板图片写入失败，尝试下一个位置: {path}")
        except Exception:
            if logger:
                logger.exception(f"保存剪贴板图片到 {directory} 失败，尝试降级")
    return None


#: 剪贴板里可能出现的"原始图片字节"格式（hasImage() 为 False 时的兜底）
_RAW_IMAGE_FORMATS = ("image/png", "image/jpeg", "image/jpg", "image/bmp",
                      "image/webp", "PNG", "JFIF", "image/x-png")


def mime_has_image_bytes(mime) -> bool:
    """轻量判断 MIME 是否**可能**含原始图片字节（只看格式名，不解码）。

    供 ``dragEnterEvent`` 这类会被频繁调用的地方使用：拖动过程中反复解码整张图
    代价太高，这里只做格式名匹配，真正解码留到松手（``image_from_mime_bytes``）。
    """
    try:
        formats = mime.formats() or []
    except Exception:
        return False
    return any(fmt in formats for fmt in _RAW_IMAGE_FORMATS)


def image_from_mime_bytes(mime):
    """从 MIME 的原始图片字节解码 QImage。

    **为什么需要**：浏览器、部分微信/QQ、Office 复制或拖出图片时只提供
    ``image/png`` / ``JFIF`` 之类的原始字节，``mimeData().hasImage()`` 为 False。
    只认 hasImage() 的话，用户会得到"剪贴板中没有图片"而无法粘贴/拖入。

    Returns: QImage 或 None（无法解码时）
    """
    from PyQt5.QtGui import QImage

    for fmt in _RAW_IMAGE_FORMATS:
        try:
            raw = mime.data(fmt)
        except Exception:
            continue
        if raw is None or raw.isEmpty():
            continue
        image = QImage.fromData(raw)
        if image is not None and not image.isNull():
            return image
    return None


def save_image_from_mime(mime, logger=None):
    """把 MIME 里的图片字节落盘归档，返回路径或 None。

    供拖放复用：从浏览器/微信拖出的图片往往只有图片字节、没有本地文件。
    """
    image = image_from_mime_bytes(mime)
    if image is None:
        return None
    return save_qimage(image, logger)


def clipboard_image_path(logger=None):
    """从剪贴板取一个可用的图片路径。

    支持三种剪贴板形态（客户实际操作会遇到的情形）：
    - **位图**（微信/QQ/系统截图工具）→ 落盘到 ``pic/<日期>/`` 后返回该路径
    - **原始图片字节**（浏览器/部分 IM 复制图片）→ 同上（见 ``image_from_mime_bytes``）
    - **文件路径列表**（资源管理器 Ctrl+C 复制图片文件）→ 直接返回该文件路径，**不重复落盘**

    Returns: (path | None, reason)
        path 为 None 时 reason 是给用户看的失败原因
    """
    from PyQt5.QtWidgets import QApplication

    clipboard = QApplication.clipboard()
    mime = clipboard.mimeData() if clipboard is not None else None
    if mime is None:
        return None, "剪贴板中没有图片"

    # 1) 位图：Qt 能直接识别的情形
    image = None
    if mime.hasImage():
        candidate = clipboard.image()
        if candidate is not None and not candidate.isNull():
            image = candidate

    # 1b) 兜底：只提供原始图片字节的来源（浏览器 / 部分 IM）
    if image is None:
        image = image_from_mime_bytes(mime)

    if image is not None:
        path = save_qimage(image, logger)
        if path:
            return path, ""
        return None, "剪贴板图片保存失败（磁盘空间或权限问题）"

    # 2) 文件路径列表（资源管理器复制图片文件）
    if mime.hasUrls():
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            local = os.path.normpath(url.toLocalFile())
            if is_supported_image(local) and os.path.isfile(local):
                return local, ""

    return None, "剪贴板中没有图片"


def local_paths_from_mime(mime) -> list:
    """从拖放事件的 MIME 数据里取出本地文件路径列表。

    统一用 ``os.path.normpath`` 规范化 —— ``QUrl.toLocalFile()`` 在 Windows 上
    返回正斜杠路径，规范化后日志与 ``json/ai`` 里记录的 source_file 风格才一致。
    """
    if mime is None or not mime.hasUrls():
        return []
    return [os.path.normpath(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]


def first_supported_path(paths, allow_html: bool = True):
    """从拖入的路径里挑第一个可处理的文件。

    allow_html=True 时连 HTML 一起接受 —— 因为下游 ``_ai_fill_from_path`` 本来就按
    扩展名分流，**限制成"只收图片"反而要额外写过滤代码**。

    Returns: (path | None, 被忽略的文件数)
    """
    exts = set(SUPPORTED_IMAGE_EXTS)
    if allow_html:
        exts |= SUPPORTED_HTML_EXTS

    files = [p for p in (paths or []) if p and os.path.isfile(p)]
    for path in files:
        if os.path.splitext(path)[1].lower() in exts:
            return path, max(0, len(files) - 1)
    return None, len(files)
