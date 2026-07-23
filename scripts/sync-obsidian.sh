#!/usr/bin/env bash
# sync-obsidian.sh - Obsidian 仓库到 myblog 博客的同步脚本
# 实际工作由同目录的 sync-obsidian.py 完成
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/sync-obsidian.py "$@"
