# Docker 部署指南（写给第一次用 Docker 的人）

> 这份文档只讲一件事：**怎么把「Excel 誊写器服务版」装进 NAS 并让它跑起来**。
> 所有命令都在本项目的开发机上**实际跑通过**，文中标注了实测结果与踩过的坑。
>
> **书写约定**：正文里的 `<尖括号>` 表示需要替换的占位符（如 `<分类名>`、`<文件夹>`、`<文件名>`、`<日期>`、`<token>`）；具体名称只出现在示例中。

---

## 1. 先搞懂 4 个词（其它都不用记）

| 词 | 好比 | 你要关心的事 |
|---|---|---|
| **镜像 image** | 一个装好系统+软件+依赖的**箱子** | 一次做好，可拷贝、可搬到别的机器 |
| **容器 container** | 箱子被打开、**正在运行**的那一份 | 可以起停、删除；删了箱子还在 |
| **Dockerfile** | 箱子的**装箱清单** | 本项目已写好，你基本不用改 |
| **挂载 volume / 绑定挂载** | 箱子外面放着的**抽屉** | Excel、json、logs 等数据放抽屉里，箱子删了数据还在 |

一张图理解你接下来要做的事：

```
       docker build  ──────────────►  镜像（714 MB）
      （按 Dockerfile 装箱）              │
                                          │ docker run
                                          ▼
   NAS 上的文件夹（抽屉）  ◄──挂载──►  容器（正在跑的服务）
     ./data/Excel                          │
     ./json  ./logs                        │  监听 8080
                                          ▼
                              http://<NAS地址>:8080/v1/healthz
                                          ▲
                                     AstrBot 来调
```

---

## 2. 你现在处于什么状态（本项目的实测记录）

| 项 | 状态 |
|---|---|
| 你的 NAS | 已有 Docker，可跑容器；**ARM 架构**；能出外网 |
| 你的开发机 | WSL（Ubuntu）里装了 Docker，`linux/x86_64` |
| 本项目镜像 | **已在开发机 WSL 里构建成功**：`excel-service:4.0.2-test`，714 MB |
| 容器实测 | 以 `--memory 512m` 运行 **healthy**，接口全部通、任务流程通 |
| 尚未验证 | 在 **ARM 的 NAS** 上构建（apt 装 PyQt5 的部分需要确认，见 §6） |

> 注意：**开发机是 x86、NAS 是 ARM，两者镜像不能混用**。所以"在开发机构建再搬到 NAS"这条路，
> 只有在两者架构相同时才直接可用；ARM 的 NAS 需要在 NAS 上构建（或交叉构建）。

---

## 3. 第一次跑起来（4 条命令）

假设你已经把本项目放到 NAS 上（比如 `/volume1/docker/myapp/`），并 `cd` 进去。

### 3.1 准备配置

```bash
cp service.ini.example service.ini
vi service.ini
```

要改的地方（**只有这几处**）：

- `token` → 换成你自己的长随机串（这是访问密码）
- `[target:jc-main]` 里的 `excel_path` / `html_dir` → 改成**容器内路径**（形如 `/data/<文件名>.xlsx`）
- 其它保持默认即可

顺便准备一个目录放数据：

```bash
mkdir -p data json logs
# 把要处理的 Excel 放进 data/，例如：
# cp /你的/副本8-14.xlsx data/book.xlsx
```

### 3.2 构建镜像

```bash
docker build -t excel-service:4.0.2-preview \
  --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .
```

逐段解释：

| 片段 | 意思 |
|---|---|
| `docker build` | 按 Dockerfile 装箱 |
| `-t excel-service:4.0.2-preview` | 给箱子起名字（`名字:标签`），后面运行要用 |
| `--build-arg PIP_INDEX=...` | 构建时用的 pip 源。**国内网络常常连不上 pypi.org**，所以换清华源；国外网络可以不加这个参数 |
| `.` | 装箱清单和文件就在当前目录 |

> **实测**：在开发机上，`apt` 那一步花了约 8 分钟（Debian 源较慢），后续增量构建只花十几秒。
> NAS 上 CPU 弱，第一次构建可能更久（20–40 分钟很正常），**只要没报错就让它跑**。

### 3.3 运行容器

```bash
docker run -d --name excel-service \
  --memory 512m --restart unless-stopped \
  -p 8080:8080 \
  -e TZ=Asia/Shanghai \
  -v "$PWD/service.ini":/app/service.ini:ro \
  -v "$PWD/config.ini":/app/config.ini \
  -v "$PWD/data":/data \
  -v "$PWD/json":/app/json \
  -v "$PWD/logs":/app/logs \
  excel-service:4.0.2-preview
```

| 参数 | 作用 | **不加会怎样**（真实踩过） |
|---|---|---|
| `-d` | 后台运行 | 前台占着终端，关掉就停 |
| `--name excel-service` | 给容器起名 | 后面命令只能用随机 ID |
| `--memory 512m` | 内存上限 | NAS 只有 2GB，可能被这个服务吃光 |
| `--restart unless-stopped` | NAS 重启后自动起来 | 断电/重启后要手动再跑一遍 |
| `-p 8080:8080` | 把 NAS 的 8080 转到容器 8080 | 外部访问不到 |
| `-e TZ=Asia/Shanghai` | 时区 | **日期目录会按 UTC 分**，`json/ai/<日期>/` 会错位 |
| `-v ...service.ini:ro` | 配置文件挂进去（只读） | 容器里没有配置，启动后档案为空 |
| `-v ...config.ini` | 桌面版的 AI 配置（模型名 / 提示词） | AI 调用缺模型与提示词配置 |
| `-e APP_AI_KEY=sk-...` | **API Key（容器里必须用这个）** | AI 调用失败——见 §3.5 |
| `-v ...data:/data` | Excel 与源文件 | **容器里改的 Excel 在容器删掉后会消失** |
| `-v ...json` `-v ...logs` | 产物与日志 | 同上，任务记录与日志会丢 |

> 📁 **我的文件该放哪个文件夹？结果从哪里取？** —— 见 [service_api.md](service_api.md) 第 1 章「文件放哪、结果在哪」：目录映射表、输入位置、各类产物的落点都有说明。

> ⚠️ **最容易踩的一个坑**：`service.ini` 里 `host` 必须是 `0.0.0.0`。
> 镜像已默认设好 `APP_HOST=0.0.0.0`，但如果你在 ini 里写成 `127.0.0.1`，
> 就会出现"容器显示 healthy，但从外面访问超时/连接被拒"——**容器内只听回环，端口映射转不进去**。

### 3.4 验证

```bash
# ① 容器活着吗（看到 healthy 就对了）
docker ps --filter name=excel-service

# ② 接口通不通（healthz 不需要 token）
curl http://127.0.0.1:8080/v1/healthz
# → {"busy":false,"status":"ok","version":"4.0.2-preview"}

# ③ 鉴权生效吗（下面这条应该返回 401）
curl -i http://127.0.0.1:8080/v1/jobs

# ④ 带上 token（把 xxx 换成 service.ini 里的 token）
curl -H "Authorization: Bearer xxx" http://127.0.0.1:8080/v1/jobs
# → {"jobs":[]}
```

> 镜像里**没有 curl**（故意不装，省体积）。所以上面 `curl` 是在 NAS 宿主机上执行的；
> 容器内的健康检查用的是 Python 标准库，不需要 curl。

### 3.5 API Key 怎么给容器（最容易踩的坑）

桌面版输入的 Key 是**加密保存且绑定本机**的（用网卡 MAC + 计算机名做混淆密钥），
所以**把那份 config.ini 挂进 Linux 容器里是解不开的**——表现为"配置看着都对，AI 调用一直失败"。

容器里有**两种**给密钥的方式，推荐第一种：

**方式一：挂载密钥文件（推荐，密钥不出现在命令行）**

1. 准备一个密钥文件（放在宿主机，**不要**放进镜像或随包分发）：

```text
<宿主目录>/key
```

支持三种写法，任选：

```text
sk-xxxxxxxx                 ← 裸密钥
jc: sk-xxxxxxxx             ← 带标签；多条时用环境变量 APP_AI_KEY_LABEL 指定取哪条
任意单行文本                 ← 会先尝试提取 sk- 片段，取不到则整行使用
```

2. 启动时挂进去（镜像自带启动脚本会自动读取并转成环境变量）：

```bash
-v "<宿主目录>/key:/app/key:ro"
```

启动日志会打印一行（**只有长度，不含密钥**）：

```text
[entrypoint] 已从 /app/key 读取 AI 密钥（长度 35）
```

3. 想换密钥：**改文件 → 重启容器**即可。想指定某一条：加 `-e APP_AI_KEY_LABEL=<标签>`。

> 注意：`.dockerignore` 已排除 `key`，**密钥不会被烤进镜像**；`docker exec` 里看不到该变量（它是启动脚本导出的，只作用于服务主进程），这是正常的。

**方式二：环境变量传明文 Key**：

    docker run ... -e APP_AI_KEY=sk-你的key ...

- 支持的变量名（按优先级）：APP_AI_KEY > DEEPSEEK_KEY > OPENAI_API_KEY
- 环境变量优先于 config.ini；桌面版不受影响（桌面版不设这些变量）
- 模型名、提示词等**非密钥**配置仍可放在挂载的 config.ini 里

---

## 4. 三个必须理解的机制

### 4.1 端口映射 `-p 宿主端口:容器端口`

- 左边（8080）是你**在 NAS 上用浏览器/curl 访问**的端口
- 右边（8080）是**容器里服务监听的**端口，必须与 `service.ini` 的 `port` 一致
- 冲突了（8080 被别的服务占用）就改左边，例如 `-p 18080:8080`

### 4.2 目录挂载 `-v 宿主路径:容器路径[:ro]`

- 左边是 NAS 上的真实目录，右边是容器里看到的路径
- **`service.ini` 里写的路径必须是"容器路径"**（形如 `/data/<文件名>.xlsx`），
  而不是 NAS 上的路径（形如 `/volume1/docker/<项目目录>/data/<文件名>.xlsx`）
- `:ro` = 只读（配置文件建议加）
- 不挂载 = 容器内部改动在删除容器后**全部丢失**

### 4.3 环境变量 `-e KEY=VALUE`

本服务认这些：

| 变量 | 作用 | 默认 |
|---|---|---|
| `APP_CONF` | 配置文件路径 | `service.ini` |
| `APP_TOKEN` | 访问令牌（覆盖 ini） | 空（此时不应对外暴露） |
| `APP_HOST` | 监听地址 | `127.0.0.1`（**镜像内已改为 0.0.0.0**） |
| `APP_PORT` | 监听端口 | `8080` |
| `APP_PREVIEW_TTL` | 预览有效期（秒） | `1800` |
| `TZ` | 时区 | 镜像内已设 `Asia/Shanghai` |

---

## 5. 日常运维命令（够用版）

```bash
docker ps                              # 看正在跑的容器（含 healthy 状态）
docker ps -a                           # 连已停止的一起看
docker logs --tail 50 excel-service    # 看最近 50 行日志
docker logs -f excel-service           # 持续跟踪日志（Ctrl+C 退出）
docker stats excel-service             # 看实时内存/CPU 占用

docker restart excel-service           # 重启
docker stop excel-service              # 停止
docker start excel-service             # 启动
docker rm -f excel-service             # 删除容器（镜像与挂载的数据都还在）

docker images                          # 看本机镜像列表及体积
docker rmi excel-service:旧标签         # 删除旧镜像

docker exec -it excel-service sh       # 进容器里看看（排错用）
docker exec excel-service ls /app/json/service/jobs   # 看任务状态文件
```

### 升级到新版本

```bash
# 1. 拿到新代码后，重新构建（用新标签，方便回滚）
docker build -t excel-service:新版本号 --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .

# 2. 停掉旧容器，用新镜像起一个（挂载参数保持不变）
docker rm -f excel-service
docker run -d --name excel-service ...（同 §3.3，把镜像名换成新标签）

# 3. 确认没问题后再删旧镜像
docker rmi excel-service:旧版本号
```

> 数据都在挂载目录里，**换镜像不会丢数据**。

---

## 6. 在 ARM 的 NAS 上部署

你的 NAS 是 ARM，这带来两点差异：

1. **PyPI 上没有 PyQt5 的 ARM 安装包**（实测：PyQt5 / PyQt5-Qt5 / PyQt5-sip 都没有 aarch64 轮子），
   所以本项目的 Dockerfile 特意改用 **Debian 官方包 `python3-pyqt5`**（arm64 有现成的）。
   → 因此**必须在 NAS 上（或为 ARM 交叉）构建**，不能直接把开发机的 x86 镜像拷过去。
2. 构建更慢：apt 与 pip 都受 CPU 限制，第一次十几分钟到半小时都属正常。

### 路线 A：在 NAS 上构建（推荐，架构天然正确）

```bash
# 把项目拷到 NAS（scp / 共享文件夹都行），然后：
cd /你的/项目目录
docker build -t excel-service:4.0.2-preview \
  --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .
```

若构建时报某个 apt/pip 包找不到，把报错发我——大概率是源或包名问题，改一行即可。

### 路线 B：在开发机构建后传到 NAS（仅当架构相同）

```bash
# 开发机（WSL）
docker save excel-service:4.0.2-preview -o excel-service.tar
# 传到 NAS 后
docker load -i excel-service.tar
```

> ⚠️ x86 镜像**不能**在 ARM 的 NAS 上运行。只有 NAS 也是 x86 时这条路才通。

### 路线 C：交叉构建 ARM 镜像（进阶）

```bash
docker buildx create --use --name armbuilder
docker buildx build --platform linux/arm64 \
  -t excel-service:4.0.2-preview --load .
```
需要开发机 Docker 支持 buildx（你的 WSL Docker 29.9 支持）。构建会走 qemu 模拟，**比较慢**，
但产物可以直接搬去 NAS。

---

## 7. 排错清单（按"现象"查）

| 现象 | 最可能原因 | 处理 |
|---|---|---|
| `docker ps` 里**没有容器** | 容器启动后立刻退出 | `docker logs excel-service` 看报错；常见是 ini 路径不对或 token 为空 |
| 状态是 `unhealthy` | 健康检查失败 | `docker logs` 看是否有异常；确认 `port` 与 healthcheck 的 8080 一致 |
| 容器 `healthy` 但**外部访问超时/拒绝** | ① `service.ini` 的 `host` 写成了 `127.0.0.1`；② 端口没映射 | ini 改 `0.0.0.0`（镜像已默认）；确认 `-p` 参数 |
| `curl` 返回 `401` | 没带 token 或 token 不对 | 加 `-H "Authorization: Bearer <token>"` |
| 返回 `CONFIG_ERROR: 未找到目标档案` | `service.ini` 没挂进去，或段名写错 | 确认 `-v ...service.ini:/app/service.ini:ro`，段名是 `[target:xxx]` |
| 返回 `MISSING_MATCH_DATE` | 请求没带 `match_date` | 见 API 文档，extract 必须带 |
| 返回 `NO_WHITELIST` | 目标 Excel 读不到白名单 | 确认 Excel 挂载正确、`sheet` 名字对 |
| 返回 `EXCEL_LOCKED` | 有人在写同一个 Excel | 稍后重试；不要用桌面版同时开同一个文件 |
| 日志里 `路径不存在: /data/html` | `html_dir` 指的目录没挂载 | 图片模式可留空目录；HTML 模式必须挂载 |
| 日志里中文日期目录错位（差 8 小时） | 时区 | 加 `-e TZ=Asia/Shanghai` |
| 构建时 `Connection to pypi.org timed out` | 网络 | 加 `--build-arg PIP_INDEX=<国内镜像>` |
| 构建时 `No matching distribution found for PyQt5` | 在 ARM 上用 pip 装 PyQt5 | 用本项目 Dockerfile（走 apt），不要在 ARM 上 `pip install PyQt5` |
| `docker images` 显示 714MB | 正常 | 见 §9 |

---

## 8. 安全注意

1. **token 一定要改**：`service.ini` 里的 `token` 是唯一凭据，别用样例值
2. **不要把这个端口暴露到公网**：目前只适合局域网（或通过 VPN / 反向代理加 TLS）
3. **别把 `config.ini`（含 API Key）提交到 git**：项目 `.gitignore` 已处理，但你自己复制文件时要注意
4. `docker logs` 里不会打印 API Key（这点已实现），但**不要把含 key 的 ini 贴给别人**

---

## 9. 几个常见疑问

**Q：714MB 的镜像会不会把 NAS 内存吃光？**
A：不会。镜像占的是**磁盘**；运行时内存实测在 **512MB 上限内**正常（一个任务并发）。
NAS 只有 2GB 且要与 AstrBot 共用，所以 `--memory 512m` 是刻意的保护。

**Q：数据到底存在哪？**
A：全部在你挂载的目录里：Excel 在 `./data`，任务状态在 `./json/service/jobs/`，
AI 结果留档在 `./json/ai/<日期>/`，日志在 `./logs/`。**删容器不删数据**。

**Q：容器里为什么不装 curl / 浏览器 / OCR？**
A：刻意省体积与内存——`curl` 用 Python 标准库替代；HTML 预览是桌面版才需要的；
本地 OCR 需要常驻 onnxruntime+模型，2GB 的 NAS 扛不住（服务固定用"原生视觉"，图片直接送 AI）。

**Q：服务崩了会自己恢复吗？**
A：`--restart unless-stopped` 会在进程退出时自动重启。
另外服务启动时会把"上次正在写入"的任务标记为 `interrupted`，**不会自动重放**（避免重复写 Excel）。

**Q：多个任务会并行吗？**
A：默认**并发 1**（队列排队）。这是为 2GB 内存设的；如果 NAS 内存更大，可用
`--concurrency` 参数（`docker run ... excel-service:版本 --concurrency 2`）但**不建议**，
因为 Excel 同一时刻只能被一个写入者安全修改（openpyxl 是整文件覆盖写）。

---

## 附 A：Windows + Docker Desktop 部署（实测流程）

> 适用于 Windows 10/11。以下流程已在 Windows 10 家庭版 + Docker Desktop（WSL2 后端）实测通过。

### A.1 安装 Docker Desktop（可指定安装位置）

```powershell
# 安装到 D 盘，避开系统盘
.\DockerDesktopInstaller.exe install --quiet --accept-license --backend=wsl-2 --installation-dir=D:\Docker
```

- 安装需要管理员权限（会弹 UAC），约 3 GB
- **镜像/容器数据盘固定在 C 盘**：`C:\Users\<用户>\AppData\Local\Docker`（约 2 GB）
  - WSL2 后端下界面里的 "Disk image location" 是灰的、不可用
  - 用目录联接（junction）把该目录指向别处会导致 Docker 无法启动，**不要尝试**
- 装完后托盘出现鲸鱼图标；`docker version` 能返回客户端与服务端版本即成功

### A.2 构建镜像

```powershell
cd D:\excel-service-deploy
docker build -t excel-service:4.0.5-preview --build-arg PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple .
```

> 能直连 pypi 时可不传 `--build-arg`。首次构建约 5–10 分钟（系统包安装最慢），之后增量构建很快。

### A.3 用图形界面部署（推荐）

Docker Desktop → 左侧 **Images** → 选中刚构建的镜像 → 右侧 **▷ Run**，按下表填写：

| 字段 | 值 |
|---|---|
| Container name | `excel-service` |
| Host port / Container port | `18085` / `8080` |
| Environment variables | `TZ=Asia/Shanghai`、`APP_HOST=0.0.0.0`、`APP_TOKEN=<你的令牌>` |
| Volumes（4 条 bind） | `D:\excel-service-deploy\service.ini` → `/app/service.ini`（勾 Read only）<br>`D:\excel-service-deploy\data` → `/data`<br>`D:\excel-service-deploy\json` → `/app/json`<br>`D:\excel-service-deploy\logs` → `/app/logs` |
| Optional settings → Restart policy | `Unless stopped` |
| Optional settings → Memory | `512` MB |

点 **Run**，等状态变为 `Running (healthy)`。

> **与 WSL 内 Docker 的区别**：Docker Desktop 的挂载路径可直接写 Windows 路径（`D:\...`），
> 不需要写成 `/mnt/d/...`。

### A.4 验证

```powershell
curl.exe http://127.0.0.1:18085/v1/healthz
# {"busy":false,"status":"ok","version":"4.0.5-preview"}

# 或使用项目自带脚本（自动读取令牌，7 项检查，不消耗 AI 额度）
cd D:\excel-service-deploy
.\test-api.ps1 -Base http://127.0.0.1:18085
```

### A.5 Windows 上常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 容器 `healthy` 但外部访问超时 | 服务只监听了 `127.0.0.1` | 镜像已默认 `APP_HOST=0.0.0.0`；确认 ini 没把它覆盖成 `127.0.0.1` |
| 容器显示 `Exited (137)` | 引擎重启或内存超限 | `docker inspect <容器> --format '{{.State.OOMKilled}}'` 查看；重新启动容器 |
| 改了 Docker Desktop 设置后容器不见了 | 重启引擎会重建容器 | 保留 `Restart policy: Unless stopped` 与固定挂载，重新 Run 一次即可 |
| 带令牌仍返回 401 | 令牌含中文或空格 | 令牌只用 ASCII 字母、数字、连字符 |
| 宿主端口被占用 | 旧容器未停止 | `docker ps` 找到占用者，或改用其它宿主端口 |
| 构建时 `Connection to pypi.org timed out` | 网络 | 加 `--build-arg PIP_INDEX=<国内镜像>` |