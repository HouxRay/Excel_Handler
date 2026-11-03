"""任务状态机与持久化 —— 支撑"预览 → 确认 → 写入"的两阶段提交

## 为什么需要持久化

客户选择的流程是"**先预览、人工确认后再写**"。在无界面/聊天场景下，
预览与确认之间可能隔几分钟甚至几小时（人在手机上操作），因此**任务状态必须落盘**，
服务重启后仍能查询与提交。

## 状态流转

```
preview ──commit──> running ──成功──> committed
   │                   └──失败──────> failed
   ├──cancel──────────> cancelled
   └──超时（TTL）──────> expired
```

## 三条硬规则

1. **commit 幂等**：已 committed 的任务再次 commit 只返回首次结果，**不重复写 Excel**
2. **预览有效期**：preview 超过 TTL → expired；此后 commit 被拒（`PREVIEW_EXPIRED`）
3. **重启不自动重试**：重启时处于 ``running`` 的任务标 ``interrupted``，
   **绝不自动重放**（安全优先，避免重复写入）

## 落盘

- 位置：``<base_dir>/<job_id>.json``（默认 ``json/service/jobs/``）
- **原子写**：先写 ``.tmp`` 再 ``os.replace``，避免读到半个文件
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta

#: 任务状态
QUEUED = "queued"            # 已受理、正在提取（还没有预览）
PREVIEW = "preview"
RUNNING = "running"
COMMITTED = "committed"
CANCELLED = "cancelled"
FAILED = "failed"
EXPIRED = "expired"
INTERRUPTED = "interrupted"

#: 默认预览有效期（秒）
DEFAULT_PREVIEW_TTL = 30 * 60

#: 可提交的状态（只有 preview 可以进入写入）
_COMMITABLE = (PREVIEW,)


class JobError(Exception):
    """任务相关错误；``code`` 供 HTTP 层直接映射成错误码"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class JobStore:
    """任务存储与状态机（纯文件实现，无 Qt、无数据库）"""

    def __init__(self, base_dir="./json/service/jobs", preview_ttl=DEFAULT_PREVIEW_TTL):
        self.base_dir = base_dir
        self.preview_ttl = int(preview_ttl)

    # ---------------- 基础 ----------------

    def _path(self, job_id: str) -> str:
        return os.path.join(self.base_dir, f"{job_id}.json")

    def _atomic_write(self, path: str, payload: dict) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    @staticmethod
    def new_id() -> str:
        """可排序、可读的任务号：20261020-103427-a1b2"""
        return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    # ---------------- 写操作 ----------------

    def create(self, payload: dict, preview_ttl=None, status: str = PREVIEW) -> dict:
        """创建任务，返回任务对象

        ``status=QUEUED`` 用于"创建任务立即返回、后台提取"的场景：
        此时还没有预览内容，``commit`` 会被拒（``JOB_NOT_READY``）。
        """
        ttl = self.preview_ttl if preview_ttl is None else int(preview_ttl)
        now = self._now()
        job = dict(payload)
        job.update({
            "job_id": payload.get("job_id") or self.new_id(),
            "status": status,
            "created_at": now.isoformat(timespec="seconds"),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(timespec="seconds"),
            "preview_ttl": ttl,
        })
        self.save(job)
        return job

    def mark_preview(self, job_id: str, fields: dict = None, **kwargs) -> dict:
        """后台提取完成：置 ``preview`` 并写入预览内容。

        接受一个字典（``fields``）或关键字参数，两者都支持。

        **重新计算有效期**（有效期应从"预览可用"开始算，而不是从受理开始）。
        """
        job = self.get(job_id, check_expiry=False)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        ttl = int(job.get("preview_ttl") or self.preview_ttl)
        now = self._now()
        if fields:
            job.update(fields)
        if kwargs:
            job.update(kwargs)
        job["status"] = PREVIEW
        job["preview_at"] = now.isoformat(timespec="seconds")
        job["expires_at"] = (now + timedelta(seconds=ttl)).isoformat(timespec="seconds")
        return self.save(job)

    def save(self, job: dict) -> dict:
        job["updated_at"] = self._now().isoformat(timespec="seconds")
        self._atomic_write(self._path(job["job_id"]), job)
        return job

    def mark(self, job_id: str, status: str, **fields) -> dict:
        job = self.get(job_id, check_expiry=False)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        job.update(fields)
        job["status"] = status
        return self.save(job)

    def cancel(self, job_id: str) -> dict:
        job = self.get(job_id)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        if job["status"] in (COMMITTED, FAILED, EXPIRED):
            raise JobError("JOB_NOT_CANCELLABLE",
                           f"任务当前状态为 {job['status']}，无法取消")
        if job["status"] == CANCELLED:
            return job
        return self.mark(job_id, CANCELLED)

    # ---------------- 读操作 ----------------

    def get(self, job_id: str, check_expiry: bool = True):
        """读取任务；``check_expiry=True`` 时顺带做过期判定（会落盘）"""
        path = self._path(job_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                job = json.load(f)
        except (OSError, ValueError):
            return None
        if check_expiry:
            job = self._expire_if_needed(job)
        return job

    def list(self) -> list:
        """列出全部任务（按创建时间倒序）"""
        if not os.path.isdir(self.base_dir):
            return []
        jobs = []
        for name in os.listdir(self.base_dir):
            if not name.endswith(".json"):
                continue
            job = self.get(name[:-5])
            if job is not None:
                jobs.append(job)
        jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
        return jobs

    # ---------------- 过期 ----------------

    def _expire_if_needed(self, job: dict) -> dict:
        if job.get("status") not in (PREVIEW, QUEUED):
            return job
        raw = job.get("expires_at")
        if not raw:
            return job
        try:
            expires = datetime.fromisoformat(raw)
        except ValueError:
            return job
        if self._now() <= expires:
            return job
        job["status"] = EXPIRED
        job["expired_at"] = self._now().isoformat(timespec="seconds")
        return self.save(job)

    # ---------------- 两阶段提交 ----------------

    def begin_commit(self, job_id: str):
        """进入写入阶段。

        Returns: ``(job, already_committed)``
            ``already_committed=True`` 表示此前已提交成功 → 调用方**不要重复写**，
            直接返回首次结果即可（幂等）。

        Raises:
            JobError: ``JOB_NOT_FOUND`` / ``PREVIEW_EXPIRED`` / ``JOB_CANCELLED``
                      / ``JOB_FAILED`` / ``JOB_BUSY``（正在写入）
        """
        job = self.get(job_id)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")

        status = job["status"]
        if status == QUEUED:
            raise JobError("JOB_NOT_READY", "任务仍在提取中，请稍后查询")
        if status == COMMITTED:
            return job, True                      # 幂等：不重复写
        if status == EXPIRED:
            raise JobError("PREVIEW_EXPIRED",
                           f"预览已过期（{job.get('expires_at')}），请重新创建任务")
        if status == CANCELLED:
            raise JobError("JOB_CANCELLED", "任务已取消")
        if status == FAILED:
            raise JobError("JOB_FAILED", f"任务此前已失败: {job.get('error', '')}")
        if status == RUNNING:
            raise JobError("JOB_BUSY", "任务正在写入中，请稍后查询")
        if status == INTERRUPTED:
            raise JobError("JOB_INTERRUPTED",
                           "任务在上次服务退出时中断，请重新创建任务")
        if status not in _COMMITABLE:
            raise JobError("JOB_STATE_ERROR", f"任务状态不允许提交: {status}")

        job["status"] = RUNNING
        job["started_at"] = self._now().isoformat(timespec="seconds")
        return self.save(job), False

    def finish_commit(self, job_id: str, result: dict) -> dict:
        """写入成功：置 committed 并保存结果"""
        job = self.get(job_id, check_expiry=False)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        job["status"] = COMMITTED
        job["finished_at"] = self._now().isoformat(timespec="seconds")
        job["result"] = result
        return self.save(job)

    def fail(self, job_id: str, message: str, code: str = "JOB_FAILED") -> dict:
        """写入失败：置 failed 并记录原因"""
        job = self.get(job_id, check_expiry=False)
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        job["status"] = FAILED
        job["error"] = message
        job["error_code"] = code
        job["finished_at"] = self._now().isoformat(timespec="seconds")
        return self.save(job)

    # ---------------- 重启恢复 ----------------

    def recover(self) -> list:
        """服务启动时调用：把残留的 ``running`` 标为 ``interrupted``。

        **绝不自动重试**：无法判断上次写入是否已经落盘，重放可能重复写入。
        Returns: 被标记的任务列表
        """
        touched = []
        for job in self.list():
            if job.get("status") == RUNNING:
                job["status"] = INTERRUPTED
                job["interrupted_at"] = self._now().isoformat(timespec="seconds")
                self.save(job)
                touched.append(job)
        return touched
