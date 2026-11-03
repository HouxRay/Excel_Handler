"""HTTP 接口（Flask 应用，由 waitress 承载）

## 设计要点

- **统一任务模型**：所有功能都"创建任务 → 看预览 → 提交"，用 ``action`` 区分做什么：
  ``extract``（提取并写入）/ ``sort``（排序统计写入）/ ``export_json``（写汇总 JSON）
- **创建立即返回**：AI 提取要 5–60 秒，不能同步阻塞 HTTP 请求。
  任务先置 ``queued``，后台线程干完活再置 ``preview``；调用方轮询 ``GET /v1/jobs/<id>``
- **两阶段提交**：``commit`` 才真正动 Excel；``commit`` 幂等（重复调用不重复写）
- **写入串行**：同一工作簿的写入由 :func:`src.service.locking.excel_lock` 串行化
- **并发上限 1**：NAS 只有 2 GB 内存，且要与 AstrBot 共用（见规格 §5.7）
- **输入两种形态**：NAS 本地路径（AstrBot 存好后传路径）或 **multipart 上传**（兼容）
- **鉴权**：``Authorization: Bearer <token>``；未配置 token 时应只监听本机（见 config）

## 端点

============================  ============================================
``GET  /v1/healthz``          健康检查（免鉴权）
``GET  /v1/version``          版本号（与桌面版一致）
``POST /v1/jobs``             创建任务 → 202 + job_id
``GET  /v1/jobs/<id>``        查询状态 / 预览 / 进度
``POST /v1/jobs/<id>/commit`` 确认执行 → 写入并返回报告
``POST /v1/jobs/<id>/cancel`` 取消（未提交前有效）
``GET  /v1/jobs``             任务列表（便于排查）
============================  ============================================
"""
import glob
import os
import threading
import traceback

from flask import Flask, jsonify, request

from src import ai_alignment, ai_handler, ai_storage, image_source, zip_handler
from src.log_setup import logger
from src.service.config import ConfigError, ServiceConfig, VERSION
from src.service.context import build_context
from src.service.jobs import QUEUED, JobError, JobStore
from src.service.locking import ExcelBusy, excel_lock

#: 允许的 action
ACTIONS = ("extract", "sort", "export_json")

#: 上传文件落盘目录（相对 CWD，与 json/ 同级）
UPLOAD_ROOT = os.path.join("json", "service", "uploads")

#: 上传体积上限（与 Flask MAX_CONTENT_LENGTH 对应）
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

#: JobError → HTTP 状态码
_ERROR_STATUS = {
    "JOB_NOT_FOUND": 404,
    "PREVIEW_EXPIRED": 409,
    "JOB_CANCELLED": 409,
    "JOB_FAILED": 409,
    "JOB_BUSY": 409,
    "JOB_NOT_READY": 409,
    "JOB_INTERRUPTED": 409,
    "JOB_STATE_ERROR": 409,
    "JOB_NOT_CANCELLABLE": 409,
    "NO_WHITELIST": 400,
    "MISSING_INPUTS": 400,
    "BAD_INPUT": 400,
    "EXCEL_LOCKED": 409,
}


def _error(status: int, code: str, message: str):
    return jsonify({"error": {"code": code, "message": message}}), status


def create_app(config: ServiceConfig = None, store: JobStore = None,
               context_factory=None, concurrency: int = 1) -> Flask:
    """创建 Flask 应用（便于测试时注入替身）"""
    cfg = config or ServiceConfig()
    jobs = store or JobStore(base_dir=cfg.jobs_dir, preview_ttl=cfg.preview_ttl)
    make_ctx = context_factory or build_context

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
    app.extensions["service"] = {"cfg": cfg, "jobs": jobs}

    slots = threading.BoundedSemaphore(max(1, int(concurrency)))

    # ---------------- 错误映射 ----------------

    @app.errorhandler(JobError)
    def _on_job_error(e: JobError):
        return _error(_ERROR_STATUS.get(e.code, 400), e.code, e.message)

    @app.errorhandler(ConfigError)
    def _on_config_error(e: ConfigError):
        return _error(400, "CONFIG_ERROR", str(e))

    # ---------------- 鉴权 ----------------

    @app.before_request
    def _authorize():
        # 健康检查与版本号免鉴权：便于容器编排与客户排障（不含业务数据）
        if request.method == "OPTIONS" or request.path in ("/v1/healthz", "/v1/version"):
            return None
        expected = cfg.token
        if not expected:
            return None            # 未配置 token（约定：此时只监听本机）
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or header[len("Bearer "):].strip() != expected:
            return _error(401, "UNAUTHORIZED", "缺少或错误的 Bearer token")
        return None

    # ---------------- 只读端点 ----------------

    @app.get("/v1/healthz")
    def healthz():
        return jsonify({"status": "ok", "version": VERSION, "busy": slots._value == 0
                        if hasattr(slots, "_value") else None})

    @app.get("/v1/version")
    def version():
        return jsonify({"version": VERSION})

    @app.get("/v1/jobs")
    def list_jobs():
        items = [{
            "job_id": j.get("job_id"),
            "status": j.get("status"),
            "action": j.get("action"),
            "target": j.get("target_name"),
            "created_at": j.get("created_at"),
        } for j in jobs.list()]
        return jsonify({"jobs": items})

    @app.get("/v1/jobs/<job_id>")
    def get_job(job_id):
        job = jobs.get(job_id)          # 顺带做过期判定
        if job is None:
            raise JobError("JOB_NOT_FOUND", f"任务不存在: {job_id}")
        return jsonify(job)

    # ---------------- 创建任务 ----------------

    @app.post("/v1/jobs")
    def create_job():
        payload = _read_payload()
        action = (payload.get("action") or "extract").strip().lower()
        if action not in ACTIONS:
            return _error(400, "BAD_ACTION", f"不支持的 action: {action}（可选 {' / '.join(ACTIONS)}）")

        spec = cfg.resolve_target(payload)

        match_date = str(payload.get("match_date") or "").strip()
        if action == "extract" and not match_date:
            return _error(400, "MISSING_MATCH_DATE",
                          "extract 必须提供 match_date（工作簿可能含多天预测，服务不会猜）")
        if action == "extract" and not spec.get("target_name"):
            return _error(400, "MISSING_TARGET",
                          "extract 必须提供 target_name（要写入哪个机构 / 图片类别）")

        inputs, input_dirs, input_zips = _collect_inputs(payload, job_id_hint=None)
        if action == "extract" and not inputs:
            return _error(400, "MISSING_INPUTS", "extract 至少需要一个输入（路径或上传文件）")

        job = jobs.create({
            "action": action,
            "spec": spec,
            "match_date": match_date,
            "inputs": inputs,
            "input_dirs": input_dirs,
            "input_zips": input_zips,
            "target_name": spec.get("target_name", ""),
        }, status=QUEUED)

        threading.Thread(target=_run_job, args=(job["job_id"],),
                         name=f"job-{job['job_id']}", daemon=True).start()
        return jsonify({"job_id": job["job_id"], "status": QUEUED}), 202

    # ---------------- 后台执行 ----------------

    def _run_job(job_id: str):
        try:
            job = jobs.get(job_id, check_expiry=False)
            if job is None:
                return
            with slots:
                ctx = make_ctx(job["spec"])
                action = job["action"]
                if action == "extract":
                    _do_extract(job_id, job, ctx)
                elif action == "sort":
                    _do_sort(job_id, job, ctx)
                else:
                    _do_export_json(job_id, job, ctx)
        except JobError as e:
            jobs.fail(job_id, e.message, code=e.code)
        except Exception as e:
            logger.exception(f"任务执行失败: {job_id}")
            jobs.fail(job_id, f"{type(e).__name__}: {e}")

    def _do_extract(job_id, job, ctx):
        """提取：逐个输入调 AI → 对齐白名单 → 预填进数据中枢 → 生成预览"""
        whitelist = ctx._current_whitelist()
        if not whitelist:
            raise JobError("NO_WHITELIST",
                           "未配置 Excel 白名单，拒绝运行（避免 AI 幻觉写到错误位置）")

        mode = ctx._batch_ai_mode()
        predictions, failed_inputs = [], []
        for path in job.get("inputs") or []:
            try:
                if image_source.is_supported_image(path):
                    result = ai_handler.extract_predictions_from_image(path)
                else:
                    target_bd_code = ""
                    if mode == "bd":
                        target_bd_code = ai_alignment.extract_bd_code_from_filename(
                            os.path.basename(path))
                    result = ai_handler.extract_predictions_from_html(
                        path, mode=mode, target_bd_code=target_bd_code,
                        whitelist=whitelist)
                preds = result.get("predictions") or []
                predictions.extend(preds)
                try:
                    ai_storage.save_ai_result(result, source_file=path, mode=mode)
                except Exception:
                    logger.exception(f"AI 结果留档失败（不影响主流程）: {path}")
            except Exception as e:
                logger.exception(f"输入处理失败: {path}")
                failed_inputs.append({"input": path, "error": f"{type(e).__name__}: {e}"})

        if not predictions and failed_inputs:
            raise JobError("BAD_INPUT",
                           "全部输入都处理失败: " + "; ".join(
                               f"{os.path.basename(f['input'])} → {f['error']}"
                               for f in failed_inputs[:3]))

        applied = ctx.apply_predictions(predictions,
                                       target_override=job.get("target_name") or None)

        items = []
        known = set(ctx.data_storage.get(job.get("target_name") or "", {}) or {})
        for pred in predictions:
            code = str(pred.get("code", "")).zfill(3)
            would_write = (code in known) if ctx.data_mode != "bd" else bool(ctx.bd_data_storage)
            items.append({
                "code": code,
                "wdl": pred.get("wdl") or [],
                "scores": pred.get("scores") or [],
                "would_write": would_write,
            })

        jobs.mark_preview(job_id, {
            "items": items,
            "summary": {
                "total": len(items),
                "applied": applied["applied"],
                "skipped": applied["skipped"],
                "failed_inputs": len(failed_inputs),
                "dirs": len(job.get("input_dirs") or []),
                "zips": len(job.get("input_zips") or []),
            },
            "predictions": predictions,
            "failed_inputs": failed_inputs,
            "progress": {"done": len(job.get("inputs") or []),
                         "total": len(job.get("inputs") or [])},
        })

    def _do_sort(job_id, job, ctx):
        """排序：统计 + 生成写入操作（预览里给出统计结果）"""
        ops, counter = ctx.collect_sort_ops()
        stats = {k: v for k, v in list(counter.items())[:50]}
        jobs.mark_preview(job_id, {
            "items": [{"code": k, "counts": v} for k, v in stats.items()],
            "summary": {"codes": len(counter), "ops": len(ops)},
            "progress": {"done": 1, "total": 1},
        })

    def _do_export_json(job_id, job, ctx):
        """汇总 JSON：不需要人工确认，直接执行并置 committed"""
        ok, message = ctx.export_json_file()
        if not ok:
            jobs.fail(job_id, message, code="EXPORT_JSON_FAILED")
            return
        jobs.finish_commit(job_id, {"artifacts": [_artifact_path(message)], "message": message})

    # ---------------- 提交 ----------------

    @app.post("/v1/jobs/<job_id>/commit")
    def commit_job(job_id):
        job, already = jobs.begin_commit(job_id)      # 幂等 / 过期 / 状态校验都在这
        if already:
            return jsonify({"job_id": job_id, "status": job.get("status"),
                            "already_committed": True, "result": job.get("result")})

        spec = job["spec"]
        excel_path = spec.get("excel_path") or ""
        try:
            ctx = make_ctx(spec)
            artifacts = []
            with excel_lock(excel_path, timeout=30, logger=logger):
                if job["action"] == "extract":
                    ctx.apply_predictions(job.get("predictions") or [],
                                           target_override=job.get("target_name") or None)
                result = _write_back(ctx, job, excel_path)
                result["locate_failures"] = getattr(ctx, "last_locate_failures", [])
                if ctx.data_mode == "bd" and job["action"] == "extract":
                    pass
            jobs.finish_commit(job_id, result)
            return jsonify({"job_id": job_id, "status": "committed", "result": result})
        except ExcelBusy as e:
            jobs.fail(job_id, str(e), code="EXCEL_LOCKED")
            return _error(409, "EXCEL_LOCKED", str(e))
        except JobError:
            raise
        except Exception as e:
            logger.exception(f"提交失败: {job_id}")
            jobs.fail(job_id, f"{type(e).__name__}: {e}")
            return _error(500, "COMMIT_FAILED", f"{type(e).__name__}: {e}")

    def _write_back(ctx, job, excel_path) -> dict:
        """把数据中枢写回 Excel（在锁内调用）"""
        from src.BD_Handler import export_bd_data
        from src.Excel_Writer import ExcelWriter

        if job["action"] == "sort":
            ops, counter = ctx.collect_sort_ops()
            _apply_ops(excel_path, job["spec"].get("sheet"), ops)
            return {"written_ops": len(ops), "codes": len(counter)}

        if ctx.data_mode == "bd":
            infos, invalid = ctx.collect_bd_export_infos()
            if not infos:
                raise JobError("BAD_INPUT", "没有可导出的北单数据")
            success, message = export_bd_data(
                infos, excel_path, job["spec"].get("sheet"),
                ctx._bd_export_rows, logger)
            if not success:
                raise JobError("COMMIT_FAILED", message)
            return {"written": len(infos), "message": message, "invalid": invalid[:20]}

        ops, invalid_all, missing = ctx.collect_all_export_ops()
        if not ops:
            raise JobError("BAD_INPUT", "没有可写入的数据（目标机构可能没有对应编号）")
        _apply_ops(excel_path, job["spec"].get("sheet"), ops)
        return {"written_ops": len(ops), "invalid": invalid_all[:20], "missing": missing}

    # ---------------- 取消 ----------------

    @app.post("/v1/jobs/<job_id>/cancel")
    def cancel_job(job_id):
        return jsonify(jobs.cancel(job_id))

    return app


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _apply_ops(excel_path: str, sheet, ops) -> None:
    """把写入操作落进工作簿：批量写 + 一次 save（与桌面版同一条路径）"""
    from src.Excel_Writer import ExcelWriter

    writer = ExcelWriter(excel_path, sheet)
    for line, col, value in ops:
        if isinstance(value, list):
            writer.batch_write_list(line, col, value)
        elif isinstance(value, dict):
            writer.batch_write_dict(line, col, value)
        else:
            writer.batch_write_cell(line, col, value)
    writer.save()


def _artifact_path(message: str) -> str:
    """从"导出成功: <路径>"里取出产物路径（取不到就返回空串）"""
    if ": " in message:
        return message.rsplit(": ", 1)[-1]
    return ""


def _read_payload() -> dict:
    """读取请求体：支持 JSON 与 multipart（multipart 的普通字段转成字符串/列表）"""
    if request.files:
        payload = {k: v for k, v in request.form.items()}
        if "target" in payload and not payload["target"]:
            payload.pop("target")
        return payload
    return request.get_json(silent=True) or {}


def _is_supported_file(path: str) -> bool:
    """是不是服务能处理的文件（网页 / 图片）"""
    ext = os.path.splitext(path)[1].lower()
    return image_source.is_supported_image(path) or ext in (".html", ".htm")


def _expand_dir(path: str, recursive: bool):
    """把目录展开成 (可处理文件, 内含的 zip 列表)，均按路径排序保证顺序稳定"""
    pattern = os.path.join(path, "**", "*") if recursive else os.path.join(path, "*")
    files, zips = [], []
    for entry in sorted(glob.glob(pattern, recursive=recursive)):
        if not os.path.isfile(entry):
            continue
        if zip_handler.is_zip_path(entry):
            zips.append(entry)
        elif _is_supported_file(entry):
            files.append(entry)
    return files, zips


def _expand_zip(path: str):
    """解压 zip 并返回其中可处理的文件（复用 zip_handler，已处理中文名编码）"""
    try:
        root = zip_handler.ensure_extracted(path, logger)
    except Exception as e:
        logger.exception(f"压缩包解压失败: {path}")
        raise JobError("BAD_INPUT",
                       f"压缩包解压失败: {os.path.basename(path)}（{type(e).__name__}）")
    files, _ = _expand_dir(root, recursive=True)
    return files


def _collect_inputs(payload: dict, job_id_hint=None):
    """收集输入：文件 / 目录 / zip + multipart 上传

    支持的形态（可混用）：
    - 单个文件：网页（html/htm）或图片
    - 目录：展开其中的网页、图片，**以及目录里的 zip**（zip 解压后继续展开）
    - zip 文件：直接解压后展开

    Returns: ``(files, dirs, zips)``
        - ``files``：实际要处理的文件
        - ``dirs``：被展开的目录（写进任务记录，便于回报来源）
        - ``zips``：被解压的压缩包（同上）
    """
    raw = payload.get("inputs")
    if isinstance(raw, str):
        inputs = [raw]
    elif isinstance(raw, (list, tuple)):
        inputs = [str(x) for x in raw]
    else:
        inputs = []
    inputs = [p for p in inputs if p.strip()]
    #: recursive=true 时递归展开子目录
    recursive = bool(payload.get("recursive"))

    for storage in request.files.values():
        if not storage or not storage.filename:
            continue
        safe_name = os.path.basename(storage.filename)
        directory = os.path.join(UPLOAD_ROOT, job_id_hint or "pending")
        os.makedirs(directory, exist_ok=True)
        target = os.path.join(directory, safe_name)
        base, ext = os.path.splitext(target)
        idx = 1
        while os.path.exists(target):
            target = f"{base}_{idx}{ext}"
            idx += 1
        storage.save(target)
        inputs.append(os.path.abspath(target))
        logger.info(f"已接收上传文件: {target}")

    files, dirs, zips, missing = [], [], [], []
    for path in inputs:
        if os.path.isfile(path) and zip_handler.is_zip_path(path):
            got = _expand_zip(path)
            if not got:
                raise JobError("BAD_INPUT", f"压缩包里没有可处理的文件: {path}")
            zips.append(path)
            files.extend(got)
            logger.info(f"压缩包 {path} 解压出 {len(got)} 个文件")
        elif os.path.isdir(path):
            got, inner_zips = _expand_dir(path, recursive)
            for z in inner_zips:
                more = _expand_zip(z)
                if more:
                    zips.append(z)
                    got.extend(more)
                    logger.info(f"压缩包 {z} 解压出 {len(more)} 个文件")
            if not got:
                raise JobError("BAD_INPUT",
                               f"目录里没有可处理的文件（网页 / 图片 / zip）: {path}")
            dirs.append(path)
            files.extend(got)
            logger.info(f"目录 {path} 展开出 {len(got)} 个文件"
                        f"{'（含子目录）' if recursive else ''}")
        elif os.path.exists(path):
            files.append(path)
        else:
            missing.append(path)

    if missing and not files:
        raise JobError("BAD_INPUT", "输入文件/目录不存在: " + ", ".join(missing[:3]))
    if missing:
        logger.warning(f"忽略不存在的输入: {missing[:3]}")
    return files, dirs, zips
