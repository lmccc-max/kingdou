#!/usr/bin/env bash
# Kingdou 安装脚本：把 skill/ 与 plugin/ 装到 Hermes 对应目录并启用插件。
#
#   ./install.sh              # 安装
#   DRY_RUN=1 ./install.sh    # 只打印将要做什么
#   HERMES_HOME=/path ./install.sh
#
# 幂等：重复执行不会重复追加；已存在的中央配置会先备份再保留（不会覆盖你登记的群）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DST="$HERMES_HOME/skills/kingdou"
PLUGIN_DST="$HERMES_HOME/plugins/kingdou"
LOGS_DST="$HERMES_HOME/logs/kingdou"
STAMP="$(date +%Y%m%d-%H%M%S)"
DRY="${DRY_RUN:-0}"

say()  { printf '%s\n' "$*"; }
run()  { if [ "$DRY" = "1" ]; then say "  [dry-run] $*"; else eval "$@"; fi; }

[ -f "$HERE/skill/SKILL.md" ] || { say "找不到 skill/SKILL.md —— 请在仓库根目录运行"; exit 1; }
[ -f "$HERE/plugin/plugin.yaml" ] || { say "找不到 plugin/plugin.yaml —— 请在仓库根目录运行"; exit 1; }

say "安装 Kingdou 到 $HERMES_HOME"
say ""

# 1) skill（保留已有的中央配置）
say "1. skill → $SKILL_DST"
if [ -f "$SKILL_DST/configs/piecework-groups.json" ]; then
  say "   检测到已存在的中央配置"
  run "cp '$SKILL_DST/configs/piecework-groups.json' '$SKILL_DST/configs/piecework-groups.json.keep-$STAMP'"
  run "mkdir -p '$SKILL_DST'"
  # 只更新 SKILL.md / references / scripts，不动配置
  run "cp '$HERE/skill/SKILL.md' '$SKILL_DST/SKILL.md'"
  run "rm -rf '$SKILL_DST/references' '$SKILL_DST/scripts'"
  run "cp -r '$HERE/skill/references' '$HERE/skill/scripts' '$SKILL_DST/'"
  say "   原配置已保留（备份：configs/piecework-groups.json.keep-$STAMP）"
else
  run "mkdir -p '$SKILL_DST'"
  run "cp -r '$HERE/skill/.' '$SKILL_DST/'"
fi

# 2) plugin
say "2. plugin → $PLUGIN_DST"
run "mkdir -p '$PLUGIN_DST'"
run "cp '$HERE/plugin/plugin.yaml' '$HERE/plugin/__init__.py' '$PLUGIN_DST/'"

# 3) 日志目录
say "3. 日志目录 → $LOGS_DST"
run "mkdir -p '$LOGS_DST'"

# 4) 清理字节码缓存（改完脚本必须清，否则跑旧代码）
run "find '$SKILL_DST' '$PLUGIN_DST' -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true"

# 5) 启用插件
say "4. 启用插件"
if command -v hermes >/dev/null 2>&1; then
  if [ "$DRY" = "1" ]; then
    say "  [dry-run] hermes plugins enable kingdou"
  else
    hermes plugins enable kingdou || say "   启用失败，请手动执行：hermes plugins enable kingdou"
  fi
else
  say "   未找到 hermes 命令，请手动执行：hermes plugins enable kingdou"
fi

say ""
say "完成。还需要两步："
say "  1) 重启网关（必须在 Hermes 网关进程之外的 shell 里执行）："
say "       systemctl --user restart hermes-gateway"
say "  2) 登记真实的群与员工（否则系统是空载的）："
say "       cd $SKILL_DST && python3 scripts/register_group.py --help"
