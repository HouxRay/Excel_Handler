#!/bin/sh
# 容器启动脚本：从文件读取 AI 密钥后，再启动服务本体。
#
# 为什么需要它：业务代码只认环境变量 APP_AI_KEY（容器里读不到桌面版加密保存的密钥），
# 而把密钥写在 docker run 的 -e 参数里会留在命令历史 / docker inspect 里。
# 这里改为「挂载密钥文件 → 启动时读取 → 导出为环境变量」，密钥不出现在命令行。
#
# 支持的密钥文件形式（任选其一）：
#   1) 裸密钥：        sk-xxxxxxxx
#   2) 带标签：        jc: sk-xxxxxxxx    ← 多条时用 APP_AI_KEY_LABEL 指定取哪条
#   3) 其它单行文本：  会先尝试提取 sk- 片段，取不到则整行使用
#
# 环境变量：
#   APP_AI_KEY_FILE   密钥文件路径（默认 /app/key）
#   APP_AI_KEY_LABEL  按标签取（如 jc），默认取文件里第一条含 sk- 的行
#   APP_AI_KEY        已通过 -e 传入时保持原样（本脚本不覆盖）

set -u

KEY_FILE="${APP_AI_KEY_FILE:-/app/key}"

if [ -z "${APP_AI_KEY:-}" ] && [ -f "$KEY_FILE" ]; then
    LINE=""
    if [ -n "${APP_AI_KEY_LABEL:-}" ]; then
        LINE=$(grep -iE "^[[:space:]]*${APP_AI_KEY_LABEL}[[:space:]]*[:=]" "$KEY_FILE" 2>/dev/null | head -1 || true)
    fi
    if [ -z "$LINE" ]; then
        LINE=$(grep -iE 'sk-[A-Za-z0-9_-]{10,}' "$KEY_FILE" 2>/dev/null | head -1 || true)
    fi
    if [ -z "$LINE" ]; then
        LINE=$(head -1 "$KEY_FILE" 2>/dev/null || true)
    fi
    CANDIDATE=$(printf '%s' "$LINE" | tr -d '\r' | grep -oE 'sk-[A-Za-z0-9_-]{10,}' 2>/dev/null | head -1 || true)
    if [ -z "$CANDIDATE" ]; then
        CANDIDATE=$(printf '%s' "$LINE" | tr -d '\r\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
    fi
    if [ -n "$CANDIDATE" ]; then
        APP_AI_KEY="$CANDIDATE"
        export APP_AI_KEY
        echo "[entrypoint] 已从 $KEY_FILE 读取 AI 密钥（长度 ${#APP_AI_KEY}${APP_AI_KEY_LABEL:+，标签 $APP_AI_KEY_LABEL}）"
    else
        echo "[entrypoint] 警告：$KEY_FILE 存在但没解析出密钥，AI 提取将不可用" >&2
    fi
elif [ -z "${APP_AI_KEY:-}" ]; then
    echo "[entrypoint] 提示：未挂载密钥文件（$KEY_FILE）且未传 APP_AI_KEY，AI 提取将不可用" >&2
fi

exec "$@"