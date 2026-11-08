# Excel 誊写器 —— 无界面服务镜像
#
# ## 三个关键决策（详见规格 §5.7）
#
# 1. 基础镜像用 **Debian bookworm-slim**，而不是 `python:3.10-slim`
#    原因：客户 NAS 是 **ARM**，而 **PyPI 上没有 PyQt5 的 aarch64 轮子**（实测：
#    PyQt5 / PyQt5-Qt5 / PyQt5-sip 都没有），`pip install PyQt5` 在 ARM 上必然失败。
#    Debian 官方为 arm64 提供了 `python3-pyqt5`（已核实 packages.debian.org）。
#
# 2. **不装 QtWebEngine**：只有桌面版的 HTML 预览器用得到；服务版不需要浏览器。
#    （`src/` 完全不 import `window/`，所以连界面层都不拷进镜像。）
#
# 3. **不装 onnxruntime / RapidOCR**：NAS 只有 2 GB 内存、CPU 弱，本地 OCR 会拖垮；
#    服务固定走"原生视觉"（图片直接送 AI，本地零算力）。
#    若有人把识别方式配成 ocr，服务会给出清晰错误而不是悄悄降级。
#
# ## 为什么 PyQt5 走 apt、另一些走 pip
# - `python3-pyqt5` / `python3-openpyxl` / `python3-requests` / `python3-bs4` / `python3-lxml`
#   → Debian 有 arm64 现成包，**零编译**
# - `flask` / `waitress` / `pypinyin` → 纯 Python，走 venv 安装
# - venv 用 `--system-site-packages`，这样能复用 apt 装好的 PyQt5

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QT_QPA_PLATFORM=offscreen \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

# 系统包：**经静态扫描确认服务端真正需要的**（全部有 arm64 版本，无需编译）
# 扫描方法见 tests/test_service_deps.py：从 service_main.py 出发跟随 src.* 导入，
# 收集所有第三方顶层模块 → PyQt5 / openpyxl / openai / flask / waitress / pypinyin
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-pyqt5 \
        python3-openpyxl \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# 纯 Python 依赖（venv 复用 apt 的 PyQt5 等）
# 注意 `openai`：AI 客户端用的 SDK，漏装会在启动时报 ModuleNotFoundError（已踩过）
#
# PIP_INDEX 可换源：国内网络常常连不上 pypi.org，构建时传
#   --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX=https://pypi.org/simple

# 依赖清单必须**先于**安装步骤进镜像（否则 pip 找不到文件）
WORKDIR /app
COPY requirements-service.txt ./

RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip -i ${PIP_INDEX} \
    && /opt/venv/bin/pip install --no-cache-dir -i ${PIP_INDEX} -r requirements-service.txt

ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# 只拷运行必需的东西：入口 + 业务层 + 映射表
# （不拷 window/ = 不带界面层；不拷 tests/ dist/ build/ 等，见 .dockerignore）
COPY service_main.py ./
COPY src ./src
COPY mapping ./mapping
COPY prompts ./prompts
COPY entrypoint.sh ./
RUN chmod +x /app/entrypoint.sh

# 运行时数据目录（**请挂载**，否则删容器即丢数据）
RUN mkdir -p /app/json /app/logs /app/txt /app/pic

# 容器内必须监听 0.0.0.0，否则 `-p` 端口映射转不进来
# （ServiceConfig 的默认值是 127.0.0.1 —— 那是给本机运行时的安全默认；
#   容器是隔离环境，"对外暴露与否"由 `-p` 映射决定，因此这里覆盖为 0.0.0.0）
ENV APP_HOST=0.0.0.0

# 服务端口
EXPOSE 8080

# 健康检查用标准库 urllib（镜像里没有 curl，少装一个包）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["/opt/venv/bin/python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/v1/healthz', timeout=4).status==200 else 1)"]

# 配置来源：/app/service.ini（建议挂载），或环境变量 APP_CONF / APP_TOKEN 等
# 启动脚本先从 /app/key（或 APP_AI_KEY_FILE 指向的文件）读取密钥，再 exec 下面这条命令
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/opt/venv/bin/python", "service_main.py"]
