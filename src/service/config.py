"""服务配置：目标档案（profile）、鉴权 token、目录约定

**为什么要"档案"**：客户实际存在三种情况——
JC 与 BD 可能是**同一个 Excel 的不同 sheet**、也可能是**两个不同的 Excel**、
且一个工作簿可能含**多天预测**。所以"目标位置"不能写死，用命名档案声明。

配置来源（优先级从高到低）：

1. 请求里显式给出的 ``mode`` / ``excel_path`` / ``sheet`` / ``html_dir``
2. ini 里被引用的档案段 ``[target:<名字>]``
3. 环境变量（少量全局项：token / host / port / preview_ttl）

ini 示例（挂载进容器即可）：

```ini
[server]
token = 换成一串长随机字符
host = 0.0.0.0
port = 8080
preview_ttl = 1800

[target:jc-main]
mode = jc
excel_path = /data/副本8-14.xlsx
sheet = 8-16
html_dir = /data/2026-08-16-jc
mapping_path = mapping/mapping_data.txt

[target:bd-main]
mode = bd
excel_path = /data/bd_example.xlsx
sheet = 北单
html_dir = /data/2026-06-16-bd
```
"""
import configparser
import os

#: 服务版本（与桌面版 ``window/table_qt.py`` 里的 version_label 保持一致）
VERSION = "4.0.2-preview"

#: 环境变量名
ENV_CONF = "APP_CONF"
ENV_TOKEN = "APP_TOKEN"
ENV_HOST = "APP_HOST"
ENV_PORT = "APP_PORT"
ENV_PREVIEW_TTL = "APP_PREVIEW_TTL"

DEFAULT_HOST = "127.0.0.1"      # 默认只听本机；局域网暴露需显式配置
DEFAULT_PORT = 8080
DEFAULT_PREVIEW_TTL = 30 * 60
DEFAULT_MAPPING = "mapping/mapping_data.txt"

PROFILE_PREFIX = "target:"

#: 档案里允许透传的键（防止把拼错的键悄悄带进下游）
PROFILE_KEYS = ("mode", "excel_path", "sheet", "html_dir", "mapping_path",
                "bd_excel_path", "bd_sheet", "bd_html_dir", "target_label")


class ConfigError(Exception):
    """配置缺失或非法"""


class ServiceConfig:
    """服务配置：服务器参数 + 命名档案"""

    def __init__(self, ini_path=None, env=None):
        self.env = dict(os.environ if env is None else env)
        self.ini_path = ini_path or self.env.get(ENV_CONF) or "service.ini"
        self._parser = configparser.ConfigParser(interpolation=None)
        self._loaded = False
        # 用 utf-8-sig 读取：**兼容带 BOM 的 ini**。
        # Windows 记事本保存的 UTF-8 文件带 BOM，若用纯 utf-8 读会抛
        # MissingSectionHeaderError —— 服务会启动即崩，这是很容易踩的坑。
        if os.path.isfile(self.ini_path):
            self._parser.read(self.ini_path, encoding="utf-8-sig")
            self._loaded = True

    # ---------------- 服务器参数 ----------------

    def _get(self, section, option, default=None):
        try:
            return self._parser.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    @property
    def token(self) -> str:
        return (self.env.get(ENV_TOKEN) or self._get("server", "token", "") or "").strip()

    @property
    def host(self) -> str:
        return self.env.get(ENV_HOST) or self._get("server", "host", DEFAULT_HOST)

    @property
    def port(self) -> int:
        raw = self.env.get(ENV_PORT) or self._get("server", "port", str(DEFAULT_PORT))
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"端口配置非法: {raw!r}")

    @property
    def preview_ttl(self) -> int:
        raw = self.env.get(ENV_PREVIEW_TTL) or self._get("server", "preview_ttl",
                                                          str(DEFAULT_PREVIEW_TTL))
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ConfigError(f"预览有效期配置非法: {raw!r}")

    @property
    def jobs_dir(self) -> str:
        return self._get("server", "jobs_dir", "./json/service/jobs")

    # ---------------- 档案 ----------------

    def profiles(self) -> list:
        """已声明的档案名"""
        return [s[len(PROFILE_PREFIX):] for s in self._parser.sections()
                if s.startswith(PROFILE_PREFIX)]

    def profile(self, name: str) -> dict:
        """读取档案（未知档案抛 ConfigError，不静默返回空）"""
        section = f"{PROFILE_PREFIX}{name}"
        if not self._parser.has_section(section):
            raise ConfigError(f"未找到目标档案: {name}（已声明: {', '.join(self.profiles()) or '无'}）")
        data = {key: self._parser.get(section, key) for key in PROFILE_KEYS
                if self._parser.has_option(section, key)}
        data.setdefault("mapping_path", DEFAULT_MAPPING)
        if "bd_sheet" in data and "bd_excel_path" not in data:
            data["bd_excel_path"] = data.get("excel_path", "")
        return data

    def resolve_target(self, payload: dict) -> dict:
        """把一次请求解析成完整的执行参数（**显式参数优先于档案**）

        payload 支持：
            {"target": "jc-main", ...}                    引用档案
            {"mode": "jc", "excel_path": "...", ...}      完全显式
            两者混用时，显式字段覆盖档案字段

        Returns: dict（至少含 mode / excel_path / html_dir / mapping_path）
        """
        spec = {}
        name = (payload or {}).get("target")
        if name:
            spec.update(self.profile(name))

        for key in PROFILE_KEYS:
            value = (payload or {}).get(key)
            if value not in (None, ""):
                spec[key] = value

        mode = (spec.get("mode") or "jc").lower()
        if mode not in ("jc", "pic", "bd"):
            raise ConfigError(f"不支持的 mode: {mode}（可选 jc / pic / bd）")
        spec["mode"] = mode

        if mode == "bd":
            if not (spec.get("bd_excel_path") or spec.get("excel_path")):
                raise ConfigError("BD 模式必须提供 bd_excel_path 或 excel_path")
        elif not spec.get("excel_path"):
            raise ConfigError("必须提供 excel_path（或用 target 引用档案）")

        # 只有"提取"才需要 HTML 目录：图片模式输入是图片、排序/导出 JSON 与目录无关
        _action = str((payload or {}).get("action") or "extract").strip().lower()
        _needs_html = (_action == "extract") and (mode != "pic")
        if not spec.get("html_dir") and _needs_html:
            raise ConfigError("必须提供 html_dir（HTML 文件所在目录；图片模式可省略）")

        spec.setdefault("mapping_path", DEFAULT_MAPPING)
        # 目标位置（机构 / 图片类别 / 比赛标签）：请求里显式给的优先，其次档案的 target_label。
        # **不能拿档案名兜底**——档案名是配置标识（jc-main），不是数据里的机构名。
        spec["target_name"] = (str((payload or {}).get("target_name") or "").strip()
                               or str(spec.get("target_label") or "").strip())
        spec["target"] = name or ""
        return spec
