"""按 Excel 路径串行写入的锁（进程内 + 跨进程）

## 为什么必须有

``Excel_Writer`` 用 openpyxl **整文件读入 → 整文件写回**，不是增量合并。
两个写入者（两个服务请求 / 服务 + 桌面版）同时写同一个工作簿时，**后写者会整体覆盖前写者**。
所以在 NAS 场景下"串行 + 加锁"是**硬约束**，不是可选优化。

## 两层锁

1. **进程内**：``threading.Lock``，同一进程的多个请求/线程互斥
2. **跨进程**：Excel 旁边的 ``<excel>.lock`` 文件 + 操作系统级建议锁
   （Windows ``msvcrt.locking`` / POSIX ``fcntl.flock``）

跨进程锁选用**操作系统建议锁**而不是"文件存在即锁"：
进程崩溃时 OS 会自动释放，**不会留下死锁文件**。
``.lock`` 文件本身**不删除**（删除会与"别人正在持有"产生竞态），只是承载锁的载体。

## 用法

```python
from src.service.locking import excel_lock, ExcelBusy

try:
    with excel_lock("/data/副本8-14.xlsx", timeout=30):
        ...  # 读 → 改 → 写
except ExcelBusy:
    ...  # 返回 EXCEL_LOCKED
```
"""
import os
import threading
import time
from contextlib import contextmanager

#: 默认等待秒数（超时抛 ExcelBusy，由上层转成 EXCEL_LOCKED）
DEFAULT_TIMEOUT = 60.0

#: 轮询间隔（秒）
POLL_INTERVAL = 0.1

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


class ExcelBusy(Exception):
    """目标工作簿正被其他写入者占用（等锁超时）"""


def normalized_path(path) -> str:
    """统一路径表示（锁的键）：绝对路径 + 忽略大小写差异"""
    return os.path.normcase(os.path.abspath(str(path)))


def lock_file_for(path) -> str:
    """锁文件路径：Excel 旁边的 ``<excel>.lock``

    放在 Excel 旁边是**唯一保证两端都能看到**的位置：
    桌面版与容器可能不共享应用目录，但一定共享被写入的工作簿。
    """
    return os.path.abspath(str(path)) + ".lock"


def _process_lock(path) -> threading.Lock:
    """取得该路径的进程内互斥锁（按需创建）"""
    key = normalized_path(path)
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.Lock()
        return lock


# ---------------------------------------------------------------------------
# 跨进程锁：OS 级建议锁（进程退出自动释放，不会留死锁）
# ---------------------------------------------------------------------------
if os.name == "nt":                      # Windows
    import msvcrt

    def _try_os_lock(handle) -> bool:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _release_os_lock(handle) -> None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

else:                                    # POSIX（容器里的 Debian 走这条）
    import fcntl

    def _try_os_lock(handle) -> bool:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _release_os_lock(handle) -> None:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


@contextmanager
def excel_lock(path, timeout=DEFAULT_TIMEOUT, logger=None):
    """取得某个工作簿的独占锁（进程内 + 跨进程），退出时释放。

    Raises:
        ExcelBusy: 超过 ``timeout`` 秒仍未取得锁
    """
    proc_lock = _process_lock(path)
    lock_path = lock_file_for(path)

    deadline = time.monotonic() + max(0.0, float(timeout))
    acquired = proc_lock.acquire(timeout=max(0.0, deadline - time.monotonic()))
    if not acquired:
        if logger:
            logger.warning(f"获取工作簿锁超时（进程内）: {path}")
        raise ExcelBusy(f"目标工作簿正被占用: {path}")

    handle = None
    try:
        handle = open(lock_path, "a+b")
        # 保证锁文件至少 1 字节（部分平台上对空文件加锁行为不一致）
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()

        while True:
            if _try_os_lock(handle):
                break
            if time.monotonic() >= deadline:
                if logger:
                    logger.warning(f"获取工作簿锁超时（跨进程）: {path}")
                raise ExcelBusy(f"目标工作簿正被其他进程占用: {path}")
            time.sleep(POLL_INTERVAL)

        try:
            yield lock_path
        finally:
            _release_os_lock(handle)
    finally:
        if handle is not None:
            handle.close()
        proc_lock.release()
