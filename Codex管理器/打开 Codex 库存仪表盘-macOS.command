#!/bin/zsh

script_dir="${0:A:h}"
output_dir="${TMPDIR:-/tmp}"
output="${output_dir%/}/codex-manager-inventory.html"

if ! command -v python3 >/dev/null 2>&1; then
  print -u2 '没有找到 Python 3。请先安装 Python 3，再重新双击这个文件。'
  read -r '?按 Enter 键关闭'
  exit 1
fi

exec python3 "$script_dir/零件箱/Codex配置管理器.py" --inventory --output "$output"
