#!/usr/bin/env python3
"""sync-obsidian.py — Obsidian → Hugo 博客同步脚本.

功能:
    1. 把 ~/obsidian/obsidian_alei/02-Projects/博客/ 增量同步到 ./content/posts/,
       子目录直接镜像(以 _ 或 . 开头的文件/目录被跳过)
    2. 注入或保留 YAML frontmatter(title 缺失时取首个 # 标题,日期取 mtime)
    3. 把 ！[[attachments/xxx.png]] 改为 ！[/images/obsidian/xxx.png]
    4. 把 Obsidian wikilink [[xxx]] / [[xxx|alias]] 转成纯文本
    5. 把 attachments/ 同步到 static/images/obsidian/(rsync)

注意: Obsidian 的 GFM callout (> [!NOTE] xxx) Hugo + LoveIt 已原生支持,
      不需要转换。

用法:
    ./scripts/sync-obsidian.sh             # 同步 + 清洗
    ./scripts/sync-obsidian.sh --dry-run   # 只看不写
    ./scripts/sync-obsidian.sh --verbose   # 详细日志
    ./scripts/sync-obsidian.sh --open      # 同步完启动 hugo server 预览

可选 frontmatter 覆盖(写在 Obsidian 正文顶部一行 HTML 注释即可):
    <!-- blogmeta: category=seismology; tags=接收函数,教程 -->
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------- 路径 ----------
VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian/obsidian_alei")).expanduser()
SRC_POSTS = VAULT / "02-Projects/博客"
SRC_ASSETS = VAULT / "attachments"

BLOG_DIR = Path(__file__).resolve().parent.parent
DST_POSTS = BLOG_DIR / "content/posts"
DST_ASSETS = BLOG_DIR / "static/images/obsidian"
IGNORE_FILE = Path(__file__).resolve().parent / "sync-obsidian.ignore"

# ---------- 正则 ----------
FRONTMATTER_RE = re.compile(r"^---\n(.*?\n)---\n", re.DOTALL)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
BLOGMETA_RE = re.compile(
    r"<!--\s*blogmeta:\s*(.+?)\s*-->", re.IGNORECASE
)
TRIM_BLOGMETA_RE = re.compile(
    r"^<!--\s*blogmeta:.*?-->\s*\n", re.IGNORECASE | re.MULTILINE
)
# 全局附件 wikilink: ![[attachments/xxx.png]] 或 ![[attachments/xxx.png|alt]]
EMBED_IMG_RE = re.compile(
    r"!\[\[attachments/([^\[\]]+?\.(?:png|jpe?g|gif|webp|svg|bmp|avif))"
    r"((?:\|[^\]]+)?)\]\]",
    re.IGNORECASE,
)
# 全局附件 markdown: ![alt](attachments/xxx.png)
REL_IMG_RE = re.compile(r"!\[([^\]]*)\]\(attachments/([^)]+)\)")
# Wikilink: [[xxx]] 或 [[xxx|alias]] (不含图片，前面已扫过 ！开头)
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\[\]]+?)\]\]")
# article-local markdown 图片: ![alt](path) 含图片后缀 (除 attachments/ 与 /images/)
LOCAL_REL_RE = re.compile(
    r"!\[([^\]]*)\]\(([^)]+?\.(?:png|jpe?g|gif|webp|svg|bmp|avif))\)",
    re.IGNORECASE,
)
# article-local wikilink 图片: ![[xxx.png]] (任意路径, basename 抽取)
LOCAL_EMBED_RE = re.compile(
    r"!\[\[([^\[\]]+?\.(?:png|jpe?g|gif|webp|svg|bmp|avif))"
    r"((?:\|[^\]]+)?)\]\]",
    re.IGNORECASE,
)


# ---------- blogmeta 注释解析 ----------
def parse_blogmeta(line: str) -> dict:
    """'category=seismology; tags=接收函数,教程' → {'category':'seismology','tags':'接收函数,教程'}"""
    out = {}
    for kv in line.split(";"):
        kv = kv.strip()
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        out[k.strip().lower()] = v.strip()
    return out


def split_frontmatter(text: str):
    """存在 frontmatter 块返回 (块字符串, 剩余文本); 否则 (None, 原文本)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(0), text[m.end():]


def make_frontmatter(title: str, mtime: float) -> str:
    dt = datetime.datetime.fromtimestamp(mtime).astimezone()
    # 转 +0800 → +08:00
    s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    if len(s) >= 5 and s[-5] in "+-":
        s = s[:-2] + ":" + s[-2:]
    return (
        "---\n"
        f'title: "{title}"\n'
        f"date: {s}\n"
        "draft: false\n"
        'description: ""\n'
        "categories: []\n"
        "tags: []\n"
        "---\n\n"
    )


def merge_blogmeta(fm: str, meta: dict) -> str:
    """把 blogmeta 注入到 frontmatter 块里. 返回新的 frontmatter 块(含末尾空行)."""
    body = fm.strip("---\n").strip().splitlines()
    new_lines = list(body)

    if "category" in meta:
        cat = f'categories: ["{meta["category"]}"]'
        idx = next(
            (i for i, l in enumerate(new_lines) if l.startswith("categories:")),
            None,
        )
        if idx is not None:
            new_lines[idx] = cat
        else:
            new_lines.append(cat)

    if "tags" in meta:
        tags = [t.strip() for t in meta["tags"].split(",") if t.strip()]
        tag_str = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
        tag_line = f"tags: {tag_str}"
        idx = next(
            (i for i, l in enumerate(new_lines) if l.startswith("tags:")), None
        )
        if idx is not None:
            new_lines[idx] = tag_line
        else:
            new_lines.append(tag_line)

    return "---\n" + "\n".join(new_lines) + "\n---\n\n"


def inject_title_into_fm(fm: str, title: str) -> str:
    """在已有 frontmatter 块开头注入 title 字段(若缺失)."""
    body = fm.strip("---\n").strip().splitlines()
    title_line = f'title: "{title}"'
    # 插入到 frontmatter 顶部(常见约定)
    return "---\n" + title_line + "\n" + "\n".join(body) + "\n---\n\n"


# ---------- 内容改写 ----------
def rewrite_images(text: str, article_slug: str | None) -> str:
    """图片引用重写.

    1) attachments/ 路径 → /images/obsidian/<basename>  (vault 集中附件)
    2) 其他位置 (assets/, 任意相对路径, 裸文件名) →
       /images/obsidian/<article_slug>/<basename>  (文章旁的 assets/)
       仅当 article_slug 不为空时启用.
    """
    # 1) 全局 attachments
    text = EMBED_IMG_RE.sub(
        lambda m: f"![{m.group(2).lstrip('|')}]"
        f"(/images/obsidian/{Path(m.group(1)).name})",
        text,
    )
    text = REL_IMG_RE.sub(
        lambda m: f"![{m.group(1)}](/images/obsidian/{m.group(2)})", text
    )

    # 2) article-local assets: 仅当 .md 同级存在 assets/ 目录时启用
    if article_slug:
        def repl_md(m):
            alt, path = m.group(1), m.group(2)
            if path.startswith(("/images/", "http", "data:")):
                return m.group(0)
            return f"![{alt}](/images/obsidian/{article_slug}/{os.path.basename(path)})"

        def repl_wiki(m):
            path = m.group(1)
            alt_part = m.group(2) or ""
            return f"![{alt_part.lstrip('|')}]" \
                f"(/images/obsidian/{article_slug}/{os.path.basename(path)})"

        text = LOCAL_REL_RE.sub(repl_md, text)
        text = LOCAL_EMBED_RE.sub(repl_wiki, text)

    return text


def rewrite_wikilinks(text: str) -> str:
    def repl(m):
        inner = m.group(1)
        if "|" in inner:
            return inner.split("|", 1)[1]
        return inner.split("#", 1)[0]
    return WIKILINK_RE.sub(repl, text)


# ---------- 跳过规则 ----------
NUMERIC_PREFIX_RE = re.compile(r"^\d{1,2}-")  # 00-总览.md / 01-Note.md 等 (Obsidian 排序约定, 最多 2 位数字)
EXCALIDRAW_RE = re.compile(r"^\s*excalidraw-plugin\s*:", re.MULTILINE)


def should_skip(rel_path: Path) -> bool:
    """_ / . / NN- 前缀的文件/目录被跳过."""
    return any(part.startswith(("_", ".")) for part in rel_path.parts)


def numeric_prefix_skip(name: str) -> bool:
    """文件名以 NN- 数字前缀开头 (Obsidian 排序习惯) → 跳过."""
    return bool(NUMERIC_PREFIX_RE.match(name))


def is_excalidraw(text: str) -> bool:
    """文本是否 Excalidraw 绘图文件 (frontmatter 含 excalidraw-plugin 字段)."""
    return bool(EXCALIDRAW_RE.search(text))


def is_empty_file(path: Path) -> bool:
    """0 字节文件跳过."""
    return path.stat().st_size == 0


def load_excluded_dirs() -> set:
    """从 sync-obsidian.ignore 读用户自定义要跳过的子目录名."""
    if not IGNORE_FILE.exists():
        return set()
    out = set()
    for line in IGNORE_FILE.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s)
    return out


def in_excluded_dir(rel_path: Path, excluded: set) -> str | None:
    """rel_path 任何路径段是否在 excluded 中. 返回首个匹配项或 None."""
    for part in rel_path.parts:
        if part in excluded:
            return part
    return None


# ---------- 单文件处理 ----------
def process_file(src: Path, dst: Path, dry_run: bool, verbose: bool):
    rel = src.relative_to(SRC_POSTS)
    text = src.read_text(encoding="utf-8")

    # 1. 解析并移除 blogmeta 注释行
    m = BLOGMETA_RE.search(text)
    blogmeta = parse_blogmeta(m.group(1)) if m else {}
    body = TRIM_BLOGMETA_RE.sub("", text, count=1)

    # 2. _index.md 透传,不处理 frontmatter
    if src.name == "_index.md":
        new_text = body
    else:
        # 3. 同步文章旁 assets/ → /images/obsidian/<slug>/
        article_slug = src.stem
        has_assets = sync_article_assets(
            src, article_slug, dry_run, verbose
        )

        # 4. 内容改写(图片先于 wikilink)
        body = rewrite_images(body, article_slug if has_assets else None)
        body = rewrite_wikilinks(body)

        # 5. 处理 frontmatter
        existing_fm, rest = split_frontmatter(body)
        if existing_fm is not None:
            fm = merge_blogmeta(existing_fm, blogmeta) if blogmeta else existing_fm
            # 已有 frontmatter 但缺 title → 注入
            if "title:" not in fm:
                m_title = HEADING_RE.search(rest)
                title = m_title.group(1).strip() if m_title else src.stem
                fm = inject_title_into_fm(fm, title)
            new_text = fm + rest
        else:
            m_title = HEADING_RE.search(rest)
            title = m_title.group(1).strip() if m_title else src.stem
            fm = make_frontmatter(title, src.stat().st_mtime)
            fm = merge_blogmeta(fm, blogmeta) if blogmeta else fm
            new_text = fm + rest

    if dry_run or verbose:
        print(f"  📝 {rel}")
    if not dry_run:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(new_text, encoding="utf-8")


# ---------- 同步 ----------
def sync_posts(dry_run: bool, verbose: bool) -> int:
    if not SRC_POSTS.exists():
        print(f"❌ 源目录不存在: {SRC_POSTS}", file=sys.stderr)
        sys.exit(1)

    print(f"📥 同步源:   {SRC_POSTS}")
    print(f"📤 同步目标: {DST_POSTS}")

    # 仅对镜像过的子树做清理: 删除 DST_POSTS 下文件名/子目录名
    # 与 src 子树中的某个文件对应的项, 但 src 中已不存在的项目不会被
    # 单文件删除. 若要彻底清理可在脚本外手动处理, 防止误删.
    if DST_POSTS.exists():
        for item in DST_POSTS.iterdir():
            if should_skip(item.relative_to(DST_POSTS)):
                continue
            if dry_run:
                print(f"  (existing) {item.name}")
            continue  # 不自动删除, 保护已发布内容

    count = 0
    skipped_numeric = 0
    skipped_excalidraw = 0
    skipped_empty = 0
    skipped_excluded = 0
    excluded_dirs = load_excluded_dirs()

    for src in SRC_POSTS.rglob("*.md"):
        rel = src.relative_to(SRC_POSTS)
        if should_skip(rel):
            if verbose:
                print(f"  ⏭  跳过 (_/.前缀): {rel}")
            continue
        ex = in_excluded_dir(rel, excluded_dirs)
        if ex:
            skipped_excluded += 1
            if verbose or dry_run:
                print(f"  ⏭  跳过 (.ignore: {ex}): {rel}")
            continue
        if numeric_prefix_skip(src.name):
            skipped_numeric += 1
            if verbose or dry_run:
                print(f"  ⏭  跳过 (数字排序): {rel}")
            continue
        if is_empty_file(src):
            skipped_empty += 1
            if verbose or dry_run:
                print(f"  ⏭  跳过 (空文件): {rel}")
            continue
        # 仅对直接放在 posts 树根的 .md 校验 Excalidraw 头 (子目录可保留)
        text_probe = src.read_text(encoding="utf-8")
        if is_excalidraw(text_probe):
            skipped_excalidraw += 1
            if verbose or dry_run:
                print(f"  ⏭  跳过 (Excalidraw 绘图): {rel}")
            continue

        dst = DST_POSTS / rel
        process_file(src, dst, dry_run, verbose)
        count += 1

    if skipped_numeric or skipped_excalidraw or skipped_empty or skipped_excluded:
        print(
            f"   (额外跳过: 数字前缀×{skipped_numeric}, "
            f"Excalidraw×{skipped_excalidraw}, 空文件×{skipped_empty}, "
            f".ignore×{skipped_excluded})"
        )
    print(f"✅ 处理 .md 共 {count} 篇")
    return count


def sync_assets(dry_run: bool, verbose: bool, prune: bool = False):
    """把 vault/attachments/ 同步到 static/images/obsidian/.

    默认不 --delete (保护 article assets 创建的子目录被误删).
    加 --prune-vault-assets 时严格镜像 vault/attachments/, 但会 protect
    sync_article_assets 产生的子目录(避免 article images 被删).

    排除规则 (大文件 / 不适合放博客):
        *.pdf, *.PDF         - 论文 PDF (vault 内, article 旁的 PDF 保留)
        *.zip, *.tar, *.tar.gz, *.7z, *.rar
        *.iso, *.dmg
    """
    if not SRC_ASSETS.exists():
        print(f"⚠️  附件目录不存在: {SRC_ASSETS}", file=sys.stderr)
        return
    if shutil.which("rsync") is None:
        print("⚠️  rsync 未安装, 跳过附件同步 (请安装 rsync)", file=sys.stderr)
        return

    DST_ASSETS.mkdir(parents=True, exist_ok=True)

    print(f"🖼  附件:  {SRC_ASSETS} → {DST_ASSETS}")
    cmd = [
        "rsync", "-a",
        "--exclude", ".DS_Store",
        "--exclude", ".obsidian",
        # 大文件 / 不应进博客
        "--exclude", "*.pdf",
        "--exclude", "*.PDF",
        "--exclude", "*.zip",
        "--exclude", "*.tar",
        "--exclude", "*.tar.gz",
        "--exclude", "*.tgz",
        "--exclude", "*.7z",
        "--exclude", "*.rar",
        "--exclude", "*.iso",
        "--exclude", "*.dmg",
    ]
    if verbose:
        cmd.append("-v")
    if dry_run:
        cmd.append("-n")  # --dry-run
    if prune:
        cmd.append("--delete")
        # 保护 article assets 子目录不被 --delete 清空
        for slug in collect_article_asset_slugs():
            # rsync filter P = protect, 让 --delete 不动该路径下任何东西
            cmd.extend(["--filter", f"P {slug}/"])
    cmd += [f"{SRC_ASSETS}/", f"{DST_ASSETS}/"]
    subprocess.run(cmd, check=True)


def collect_article_asset_slugs() -> set:
    """扫 SRC_POSTS 找所有 article 旁 assets/ 目录, 返回对应的 article slug 集合.

    一个 article slug 是 .md 文件名去后缀, 例: 2026-07-17_arXiv_Song_VORA_精读
    """
    out = set()
    if not SRC_POSTS.exists():
        return out
    for assets_dir in SRC_POSTS.rglob("assets"):
        if not assets_dir.is_dir():
            continue
        # article_slug = assets/ 父目录里非 _index.md 的 .md 文件名(去 .md)
        for md in assets_dir.parent.glob("*.md"):
            if md.name == "_index.md":
                continue
            out.add(md.stem)
    return out


def sync_article_assets(src_md: Path, article_slug: str, dry_run: bool, verbose: bool) -> bool:
    """如果 .md 同级有 assets/ 目录, 复制到 /images/obsidian/<slug>/.
    返回 True 表示存在并同步了 assets."""
    src_assets = src_md.parent / "assets"
    if not src_assets.is_dir():
        return False
    if shutil.which("rsync") is None:
        return False

    dst_assets = DST_ASSETS / article_slug
    print(f"  🖼  article assets: {src_assets}/ → {dst_assets}/")
    if dry_run:
        subprocess.run(["rsync", "-an", f"{src_assets}/", f"{dst_assets}/"], check=True)
        return True

    dst_assets.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-a"]
    if verbose:
        cmd.append("-v")
    cmd += [f"{src_assets}/", f"{dst_assets}/"]
    subprocess.run(cmd, check=True)
    return True


def maybe_open_hugo():
    if shutil.which("hugo") is None:
        print("⚠️  hugo 未安装, 跳过预览", file=sys.stderr)
        return
    print("🌐 启动 hugo server (Ctrl+C 退出)...")
    subprocess.run(["hugo", "server", "-D", "--navigateToChanged"])


def ensure_vault_pulled(verbose: bool, skip_pull: bool) -> bool:
    """把 Obsidian vault 从 origin 拉到最新. 返回 True 表示有新 commit 被拉取.

    - vault 不是 git 仓库 → 跳过
    - 未配 origin 远端 → 跳过并警告
    - 远端有新 commit → git pull --rebase --autostash
    - 本地领先远端 → 不 pull,只警告 (避免覆盖本地未推 commit)
    - 出错 → sys.exit(1)
    """
    if not (VAULT / ".git").exists():
        if verbose:
            print(f"ℹ️  {VAULT} 不是 git 仓库, 跳过 vault pull")
        return False

    remote_check = subprocess.run(
        ["git", "-C", str(VAULT), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if remote_check.returncode != 0:
        print(
            f"⚠️  {VAULT} 未配置 origin 远端, 跳过 vault pull",
            file=sys.stderr,
        )
        return False

    print(f"🔄 vault pull: {VAULT}")

    # 1) fetch 远端
    fetch = subprocess.run(
        ["git", "-C", str(VAULT), "fetch", "--quiet"],
        capture_output=(not verbose), text=True,
    )
    if fetch.returncode != 0:
        sys.stderr.write(fetch.stderr or "")
        print("❌ git fetch 失败", file=sys.stderr)
        sys.exit(1)

    # 2) 当前分支
    branch_out = subprocess.run(
        ["git", "-C", str(VAULT), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    branch = branch_out or "master"

    # 3) ahead/behind
    counts_out = subprocess.run(
        ["git", "-C", str(VAULT), "rev-list", "--left-right", "--count",
         f"origin/{branch}...{branch}"],
        capture_output=True, text=True,
    ).stdout.strip()

    if not counts_out:
        print("   (无法解析 ahead/behind, 跳过 pull)")
        return False

    try:
        parts = counts_out.split()  # git 默认用 tab 分隔, split 默认按任意空白
        behind, ahead = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        print(f"   (ahead/behind 解析失败: {counts_out!r}, 跳过 pull)")
        return False

    if behind == 0 and ahead == 0:
        print("   ✅ vault 已与远端同步")
        return False

    if ahead > 0 and behind == 0:
        print(
            f"   ⚠️  本地领先远端 {ahead} 个 commit (尚未 push).\n"
            f"      sync 会继续,但记得稍后手动: cd <vault> && git push"
        )
        return False

    if behind > 0:
        if skip_pull:
            print(
                f"   ⚠️  远端有 {behind} 个新 commit 但 --no-pull 已设置,\n"
                f"      将基于本地内容继续 sync"
            )
            return False
        pull = subprocess.run(
            ["git", "-C", str(VAULT), "pull", "--rebase", "--autostash"],
            capture_output=(not verbose), text=True,
        )
        if pull.returncode != 0:
            sys.stderr.write(pull.stderr or "")
            print(
                "❌ git pull 失败 (可能是未推送的本地 commit 与远端冲突)",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"   ✅ 已拉取 {behind} 个新 commit")
        return True

    return False


def main():
    p = argparse.ArgumentParser(
        description="Obsidian → Hugo 同步脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--dry-run", "-n", action="store_true", help="只看不写")
    p.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    p.add_argument(
        "--open", action="store_true", help="同步完启动 hugo server 预览"
    )
    p.add_argument(
        "--no-pull", action="store_true",
        help="跳过 vault git pull (离线模式, 强制使用本地 vault 内容)"
    )
    p.add_argument(
        "--prune-vault-assets", action="store_true",
        help="严格镜像 vault/attachments/ (删除 blog 端多余文件)"
    )
    args = p.parse_args()

    # 先把 vault 拉到最新,保证多设备一致
    if not args.dry_run:
        ensure_vault_pulled(args.verbose, args.no_pull)
        print()

    sync_posts(args.dry_run, args.verbose)
    print()
    sync_assets(args.dry_run, args.verbose, args.prune_vault_assets)
    print()
    if args.dry_run:
        print("☝️  --dry-run 模式, 以上是预览, 未实际改动任何文件")
        return
    print("🚀 同步完成. 接下来:")
    print("   git add -A && git commit -m 'post: 同步博客' && git push")
    print()
    if args.open:
        maybe_open_hugo()


if __name__ == "__main__":
    main()
