# ExcelHandler · Excel 数据誊写工具

读取竞彩（JC）/ 北单（BD）分析数据，自动匹配赛事编号并写入 Excel 指定位置。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/GUI-PyQt5-41CD52?logo=qt&logoColor=white)
![Version](https://img.shields.io/badge/version-4.0.1-blue)
![License](https://img.shields.io/badge/license-Proprietary-lightgrey)

---

## 简介

**ExcelHandler** 是一个基于 **PyQt5** 的桌面应用，用于把体育数据分析结果
（竞彩 JC / 北单 BD）批量、准确地写入 Excel 工作簿的指定位置。

它解决的问题是"**人工誊写又慢又容易错**"：分析师给出的推荐以 HTML 页面或图片形式存在，
而最终要落到一张结构固定的 Excel 里。本工具负责：

- 读取 Excel 的**表头、机构行、赛事编号列**，算出每个值该写在哪一格；
- 解析 HTML / 图片 / 北单三类数据源，提取比分与胜负平；
- 通过**白名单校验**确保不会写到不存在的位置；
- 支持后台线程写入、数据排序、JSON 备份与恢复。

---

## 功能特性

### 数据源与编辑

| 功能 | 说明 |
|---|---|
| **双模式独立配置** | JC（竞彩）与 BD（北单）各自独立的 Excel / JSON / Sheet，互不影响 |
| **三种数据模式** | HTML / 图片 / 北单，顶部按钮一键切换 |
| **分类导航 + 表格编辑** | 左侧机构单选，右侧表格直接编辑比分；空格或反引号自动转为 `0` |
| **路径持久化** | 路径与 Sheet 记入 `config.ini`，下次启动自动预填；支持不重启切换数据源 |
| **HTML 预览** | 内嵌 WebEngine 查看原始页面，星期高亮（按北京时区自动检测，可手动切换） |

### AI 能力

| 功能 | 说明 |
|---|---|
| **AI 提取（JC / BD）** | 调用 DeepSeek 从 HTML 提取比分，**预览勾选后**才填入 |
| **图片识别双通道** | **原生视觉**（默认，快）或 **本地 OCR**（可离线），共用同一提示词与解析器 |
| **图片输入** | 选择图片、从剪贴板粘贴（截图/微信 QQ）、拖拽进窗均可；剪贴板位图自动归档 |
| **AI 一键批量运行** | 遍历文件夹内全部 HTML 批量提取（强制先配白名单、**不覆盖已有值**、可取消重试） |
| **结果留档与复用** | 结果存 `json/ai/<日期>/`，可按日期与机构筛选复用历史预测 |

### 导出与维护

| 功能 | 说明 |
|---|---|
| **导出写入** | 后台线程写 Excel，不阻塞界面；白名单校验失败会逐条提示 |
| **一键导出** | AI 批量结果**汇总后一次写入**，避免反复开关工作簿 |
| **数据排序** | 统计各编号下比分出现频次，写入 Excel 指定区域 |
| **JSON 备份/恢复** | 导出为按编号组织的 JSON，可二次导入继续编辑 |
| **日志系统** | 文件日志 + 界面日志框，便于事后追查 |

---

## 环境要求

| 依赖 | 用途 |
|---|---|
| Python 3.10+ | 运行时 |
| PyQt5 / PyQtWebEngine | 界面与 HTML 预览 |
| openpyxl | 读写 Excel |
| openai | AI 调用（OpenAI 兼容 SDK） |
| pypinyin | 中文排序与匹配 |
| html2text | HTML → Markdown（喂给 AI） |
| rapidocr_onnxruntime | 本地 OCR（可选，未安装则只能用原生视觉） |

## 快速开始

```bash
# 1. 安装依赖
pip install PyQt5 PyQtWebEngine openpyxl openai pypinyin html2text rapidocr_onnxruntime

# 2. 运行
python main.py
```

> 首次启动会弹出路径选择对话框，按提示选择 HTML 目录、Excel 文件与 Sheet 即可。

## 使用流程

1. **启动** → 路径选择对话框（JC / BD 双模式分组）
2. **选数据源** → HTML 目录、Excel 文件、可选 JSON、目标 Sheet
3. **编辑** → 左侧切机构，右侧改比分
4. **AI 辅助**（可选）→ `🤖 AI 填入` 选新预测 / 粘贴图片 / 历史预测；或 `⚡ 一键运行` 批量处理整个文件夹
5. **写入** → `📤 导出`（当前机构）或 `📤 一键导出`（批量汇总）
6. **排序 / 备份** → `📊 排序` 统计频次，`📝 写入JSON` 留档

操作按钮按颜色分三行：

- 🟢 **绿色**：重新选择路径 · 清空（二次确认）· 退出并打开 Excel 目录
- 🟠 **橙色**：填入数据 · 刷新 · 设置 · AI 填入 · 一键运行
- 🔵 **蓝色**：打开 · 保存 · 导出 · 排序 · 写入 JSON · 一键导出

---

## 项目结构

```text
ExcelHandler/
├── main.py                        # 启动入口
├── window/                        # 界面层（仅桌面版使用）
│   ├── table_conbine.py           # 流程编排：路径选择 → 主窗口
│   ├── table_qt.py                # 主窗口：编辑 / 导出 / 排序 / 三模式切换
│   ├── table_qt_2.py              # 路径选择对话框（JC / BD 分组）
│   ├── html_viewer.py             # HTML 查看器（星期高亮 + AI 分析）
│   ├── settings_dialog.py         # 设置（路径 / 映射 / AI 配置）
│   ├── ai_preview_dialog.py       # AI 结果预览（勾选 / 编辑）
│   └── ai_history_dialog.py       # 历史预测（按日期 / 机构筛选）
└── src/                           # 业务逻辑层（不含界面）
    ├── Excel_Handler.py           # 读取 Excel：表头、首列
    ├── Excel_Info.py              # 数据协调：读取、映射、坐标计算
    ├── Excel_Writer.py            # 写入 Excel：校验、批量写、保存
    ├── File_Reader.py             # 文件遍历与文件名提取
    ├── Name_Matcher.py            # 名称匹配（文件名 ↔ Excel 行）
    ├── BD_Handler.py              # 北单：解析 / 导出 / 排序
    ├── data_loader.py             # 数据加载与初始化
    ├── exporter.py                # 导出写入操作收集、排序统计
    ├── mapping_manager.py         # 映射持久化
    ├── worker.py                  # 后台写入线程
    ├── log_setup.py               # 日志（文件 + GUI）
    ├── zip_handler.py             # ZIP 自动解压（中文名编码修复）
    ├── ai_config.py               # AI 配置：Key（加密）、模型、提示词
    ├── ai_client.py               # AI 请求
    ├── ai_prompts.py              # 提示词构造
    ├── ai_parser.py               # 返回解析与词表校验
    ├── ai_alignment.py            # 编号 / 机构白名单对齐
    ├── ai_handler.py              # AI 链路总控
    ├── ai_storage.py              # AI 结果留档
    └── ocr_handler.py             # 图片 → 文本（原生视觉 / OCR）
```

> 本仓库**只存放源代码**。发布包（可执行程序）、映射表、示例数据与设计文档
> 由版权人本地打包后单独分发。

---

## 核心模块

| 模块 | 职责 |
|---|---|
| `Excel_Info` | 把"机构名 + 赛事编号"换算成 Excel 的（行, 列），是写入正确性的核心 |
| `Excel_Writer` | 统一的写入入口；校验值合法性，支持单格/批量/字典写入与一次保存 |
| `Name_Matcher` | 处理"文件名与 Excel 行名不完全一致"的现实情况 |
| `ai_handler` | 串起 配置 → 提示词 → 请求 → 解析 → 对齐 → 留档 的完整链路 |
| `worker` | 把写入放到后台线程，界面不卡死 |
| `exporter` | 把"要写什么"先收集成操作列表，再一次性提交，支持排序统计 |

---

## 数据与隐私

- **API Key 加密保存**在本地 `config.ini`，不以明文存放在仓库中；容器部署请用环境变量
  `APP_AI_KEY` 传入（本机加密的 Key 无法在其他机器解密）。
- AI 调用的**输入内容**（HTML 转换后的文本或图片）会发送到你配置的 AI 服务商，
  请自行确认其数据使用政策。
- 运行产生的结果留在本地：`json/ai/<日期>/`（AI 留档）、`pic/<日期>/`（图片归档）、`logs/`（日志）。

---

## 版本说明

当前发布版本：**v4.0.1**（首个正式版）。

- 标签：`v4.0.1`
- 仓库 `main` 对应发布版本；新功能在开发分支上迭代，稳定后再合并并打新标签。
- 完整变更记录见发布页（Releases）。

## 许可

本项目采用**专有许可（Proprietary, All Rights Reserved）**：
Copyright (c) 2026 HouxRay，保留所有权利。

未经版权人书面许可，不得复制、分发、修改或用于商业用途。
详见 [LICENSE](LICENSE)。

## 关于 AI 辅助开发

本项目的框架设计、需求定义、模块划分与最终取舍由作者完成；部分代码实现借助
AI 编程工具生成。作者对本项目整体享有著作权，并对其内容与使用结果负责。

## 免责声明

本软件按"现状"提供，不附带任何担保。写入 Excel 会修改真实业务数据，
**使用前请务必备份**。因使用本软件造成的任何损失，作者不承担责任。
