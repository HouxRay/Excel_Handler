"""
ZIP 文件处理模块
自动检测 .zip 路径并解压到临时目录，让下游模块始终操作正常目录。
处理中文文件名编码问题（CP936/GBK → UTF-8）。
"""
import os
import zipfile
import tempfile
import shutil
import atexit
import sys

# 模块级列表，追踪本次会话创建的所有临时目录
_TEMP_DIRS: list[str] = []
_CLEANUP_REGISTERED = False


def _register_cleanup():
    """注册进程退出时的清理函数"""
    global _CLEANUP_REGISTERED
    if not _CLEANUP_REGISTERED:
        atexit.register(cleanup_temp_dirs)
        _CLEANUP_REGISTERED = True


def is_zip_path(path: str) -> bool:
    """检测路径是否为 .zip 文件"""
    if not path or not isinstance(path, str):
        return False
    return path.lower().endswith('.zip') and os.path.isfile(path)


def _decode_filename(raw_name: bytes, flag_bits: int) -> str:
    """解码 ZIP 中的文件名，处理中文编码问题。

    ZIP 规范中，如果 flag_bits 的 bit 11 置位，则文件名使用 UTF-8 编码。
    但很多中文 ZIP 工具使用 UTF-8 却不设置该标志位，所以先试 UTF-8 再试 GBK。
    """
    # 候选编码列表（按优先级）
    encodings = ['utf-8']
    if flag_bits & (1 << 11):
        # 标志位已指示 UTF-8
        return raw_name.decode('utf-8')

    # 无标志位：尝试多种编码
    for enc in encodings:
        try:
            return raw_name.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 尝试 CP936（GBK），中文 Windows 常用编码
    try:
        return raw_name.decode('cp936')
    except (UnicodeDecodeError, LookupError):
        pass

    # 尝试系统编码
    try:
        return raw_name.decode(sys.getfilesystemencoding())
    except (UnicodeDecodeError, LookupError):
        pass

    # 最终回退：忽略无法解码的字节
    return raw_name.decode('utf-8', errors='replace')


def _extract_with_encoding(zf: zipfile.ZipFile, extract_dir: str, logger=None):
    """解压 ZIP 文件，正确处理中文文件名编码。

    标准库的 extractall 使用 CP437 解码文件名，导致中文乱码。
    此函数逐文件解压，先解码文件名再写入。
    """
    for info in zf.infolist():
        # 解码原始文件名
        raw_name = info.orig_filename.encode('cp437') if hasattr(info, 'orig_filename') else info.filename.encode('cp437')
        decoded = _decode_filename(raw_name, info.flag_bits)

        # 跳过 __MACOSX 等隐藏目录
        if decoded.startswith('__MACOSX') or decoded.startswith('.'):
            continue

        target_path = os.path.join(extract_dir, decoded)

        if decoded.endswith('/') or decoded.endswith('\\'):
            # 目录
            os.makedirs(target_path, exist_ok=True)
        else:
            # 文件
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with zf.open(info) as src, open(target_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)

    if logger:
        logger.info(f"ZIP 解压完成，已处理中文编码")


def _find_effective_root(extract_dir: str) -> str:
    """确定解压后的有效根目录。

    如果 ZIP 只包含一个内容目录（忽略 __MACOSX 等隐藏条目），
    则返回该子目录路径，使非递归扫描（os.listdir）能直接看到文件。
    """
    try:
        entries = os.listdir(extract_dir)
    except Exception:
        return extract_dir

    real_entries = [e for e in entries
                    if not e.startswith('__') and not e.startswith('.')]
    dirs = [e for e in real_entries
            if os.path.isdir(os.path.join(extract_dir, e))]
    files = [e for e in real_entries
             if os.path.isfile(os.path.join(extract_dir, e))]

    # 只有一个目录且没有文件 → 提升该目录
    if len(dirs) == 1 and len(files) == 0:
        return os.path.join(extract_dir, dirs[0])
    return extract_dir


def ensure_extracted(path: str, logger=None) -> str:
    """如果 path 是 .zip，解压到临时目录并返回临时目录路径。

    如果是普通目录，原样返回。
    自动处理中文文件名编码（CP936/UTF-8）。
    临时目录会在进程退出时自动清理。
    """
    if not is_zip_path(path):
        return path

    _register_cleanup()

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="claude_zip_")
        if logger:
            logger.info(f"正在解压 ZIP: {path} -> {temp_dir}")

        with zipfile.ZipFile(path, 'r') as zf:
            _extract_with_encoding(zf, temp_dir, logger)

        effective_dir = _find_effective_root(temp_dir)
        _TEMP_DIRS.append(temp_dir)

        if logger:
            nested = " (自动提升子目录)" if effective_dir != temp_dir else ""
            try:
                count = len(os.listdir(effective_dir))
            except Exception:
                count = 0
            logger.info(f"ZIP 解压完成: {count} 个条目{nested}")

        return effective_dir

    except Exception as e:
        if logger:
            logger.exception(f"ZIP 解压失败: {path}")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError(f"无法解压 ZIP 文件：{path}")


def cleanup_temp_dirs(_logger=None):
    """删除 ensure_extracted 创建的所有临时目录。

    可在多个地方安全调用（atexit、app.aboutToQuit、closeEvent）。
    """
    global _TEMP_DIRS
    count = 0
    for tmp_dir in list(_TEMP_DIRS):
        if os.path.exists(tmp_dir):
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                count += 1
            except Exception:
                pass
    _TEMP_DIRS = []
    return count
