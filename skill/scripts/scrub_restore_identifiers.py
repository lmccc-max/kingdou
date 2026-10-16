#!/usr/bin/env python3
"""去标识化：把一份（刚从备份恢复出来的）skill 树里的业务标识符与人员姓名换成占位符。

配套文档：`references/backup-restore-install.md` 第 6 步。

用法:
  python3 scripts/scrub_restore_identifiers.py <root> [<root> ...] [选项]

  <root>           要清理的目录或文件，可给多个。典型：
                     ~/.hermes/skills/kingdou   ~/.hermes/plugins/kingdou
  --dry            只打印将要替换的映射，不写盘（先跑这个）
  --names-file P   姓名清单，支持三种格式，可重复给：
                     a) JSON 对象 {"真实姓名": "占位符"}
                     b) JSON 数组 ["姓名", ...]          → 占位符自动 员工<NN>
                     c) 纯文本每行「姓名」或「姓名=占位符」
                   备份里的 openid_name_mapping.json 属于 (a) 的反面（值是姓名、键是 id），
                   直接给它也行：脚本会把「值」当姓名收集。
  --name 名[=占位符]  追加一个姓名，可重复

行为:
  * 同一真实值 → 同一占位符（一轮之内全局一一映射），保留文档里「这个 vs 那个」的区分度。
  * 幂等：已经是占位符（<redacted-NN> / 员工<NN> / app_xxx ...）的内容不会被二次替换。
  * 姓名按长度降序替换，避免把长名字切成半个（「全名（别名）」先于「别名」，两字名先于单字姓）。
  * 结束时重扫一遍，仍有未清理的标识符则退出码 1 —— 可直接当验证闸门用。

判断规则（只扫文本类文件，跳过 __pycache__/.git/node_modules）:
  ou_/on_/u_  — 员工、管理员身份
  oc_         — 群 chat_id
  /wiki/、/base/、"app_token": "…" 后面的 token — 多维表格 app_token
  tbl…/vew…/fld…/cli_…  — table_id / view_id / field_id / app_id
  <tenant>.feishu.cn      — 租户子域（open./api. 等公共主机名不动）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

TEXT_SUFFIXES = {'.md', '.py', '.json', '.jsonl', '.yaml', '.yml', '.txt', '.sh', '.cfg', '.ini', '.rst', '.toml'}
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', '.venv'}

# 公共飞书主机名不是租户子域，别动
PUBLIC_HOSTS = {'open', 'api', 'www', 'admin', 'docs', 'sso', 'login', 'passport', 'internal', 'openapis', 'larksuite'}

# 已经是占位符 / 文档本来就写死的模板值，永不二次替换
KEEP = re.compile(r'<redacted-\d+>|员工<\d+>|管理员<\d+>|APP_TOKEN_HERE|app_xxx|tbl_xxx|fld_xxx|oc_xxx|cli_x+|X{8,}|x{8,}')

# 标识符类别：前缀 → (匹配规则, 取值分组)。app_token 用上下文锚定，避免误伤长度相近的普通串；
# 取值分组为 1 的规则会把上下文一起匹配进来（Python 的 re 不支持变长 look-behind），
# 取值时用 group(取值分组)，替换的仍是 token 本身。
CLASS_PATTERNS: list[tuple[str, re.Pattern, int]] = [
    ('ou', re.compile(r'ou_[0-9a-f]{32}'), 0),
    ('on', re.compile(r'on_[0-9a-f]{32}'), 0),
    ('u', re.compile(r'\bu_[0-9a-f]{32}\b'), 0),
    ('oc', re.compile(r'oc_[0-9a-f]{32}'), 0),
    ('app', re.compile(r'(?<=/wiki/)[A-Za-z0-9]{20,32}'), 0),
    ('app', re.compile(r'(?<=/base/)[A-Za-z0-9]{20,32}'), 0),
    ('app', re.compile(r'"app_token"\s*:\s*"([A-Za-z0-9]{20,32})"'), 1),
    ('tbl', re.compile(r'tbl[A-Za-z0-9]{8,}'), 0),
    ('vew', re.compile(r'vew[A-Za-z0-9]{6,}'), 0),
    ('fld', re.compile(r'fld[A-Za-z0-9]{6,}'), 0),
    ('cli', re.compile(r'cli_[0-9a-z]{10,}'), 0),
    ('tenant', re.compile(r'(?<![A-Za-z0-9.])[a-z0-9]{8,20}(?=\.feishu\.cn)'), 0),
]


def iter_files(roots: list[Path]) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if root.is_file():
            out.append(root)
            continue
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            out.append(p)
    return out


def load_names(args: argparse.Namespace) -> list[tuple[str, str]]:
    """→ [(真实姓名, 占位符)]，按长度降序（长串优先替换）。"""
    pairs: OrderedDict[str, str] = OrderedDict()

    def add(name: str, placeholder: str | None) -> None:
        name = name.strip()
        if not name:
            return
        pairs.setdefault(name, placeholder or '')

    for path_str in args.names_file:
        path = Path(path_str)
        raw = path.read_text(encoding='utf-8')
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            for line in raw.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                name, _, ph = line.partition('=')
                add(name, ph or None)
            continue
        if isinstance(data, dict):
            for key, value in data.items():
                # 兼容 openid_name_mapping.json：键是 id、值是姓名
                if isinstance(value, str) and re.fullmatch(r'(ou|on|u)_[0-9a-f]{32}', key):
                    add(value, None)
                else:
                    add(key, value if isinstance(value, str) else None)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    add(item, None)

    for spec in args.name:
        name, _, ph = spec.partition('=')
        add(name, ph or None)

    numbered: list[tuple[str, str]] = []
    counter = 0
    for name, ph in pairs.items():
        if not ph:
            counter += 1
            ph = f'员工<{counter:02d}>'
        numbered.append((name, ph))
    numbered.sort(key=lambda kv: len(kv[0]), reverse=True)
    return numbered


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='去标识化：标识符与姓名 → 稳定占位符')
    ap.add_argument('roots', nargs='+', help='要清理的目录/文件')
    ap.add_argument('--dry', action='store_true', help='只打印映射，不写盘')
    ap.add_argument('--names-file', action='append', default=[], help='姓名清单（JSON/纯文本），可重复')
    ap.add_argument('--name', action='append', default=[], help='单个姓名「名」或「名=占位符」，可重复')
    args = ap.parse_args(argv)

    roots = [Path(r).expanduser() for r in args.roots]
    files = iter_files(roots)
    if not files:
        print('没有可扫描的文本文件：', roots, file=sys.stderr)
        return 2

    texts = {f: f.read_text(encoding='utf-8', errors='ignore') for f in files}

    # ---- 1. 枚举真实值，分配占位符 ----
    mapping: OrderedDict[str, str] = OrderedDict()
    counters: dict[str, int] = {}
    for prefix, pattern, group in CLASS_PATTERNS:
        for text in texts.values():
            for m in pattern.finditer(text):
                found = m.group(group)
                if found in mapping or KEEP.search(found):
                    continue
                if prefix == 'tenant' and found in PUBLIC_HOSTS:
                    continue
                counters[prefix] = counters.get(prefix, 0) + 1
                mapping[found] = f'{prefix}_<redacted-{counters[prefix]:02d}>'
    for name, placeholder in load_names(args):
        if any(name in text for text in texts.values()):
            mapping.setdefault(name, placeholder)

    # ---- 2. 长串优先字面替换，避免子串互相吃掉 ----
    ordered = sorted(mapping.items(), key=lambda kv: -len(kv[0]))
    changed = 0
    for f, text in texts.items():
        new = text
        for real, ph in ordered:
            new = new.replace(real, ph)
        if new != text:
            if not args.dry:
                f.write_text(new, encoding='utf-8')
            changed += 1

    print('映射（%d 项）%s：' % (len(mapping), '（dry-run，未写盘）' if args.dry else ''))
    for real, ph in ordered:
        print('  %-32s -> %s' % (real, ph))
    print('\n改写文件数 = %d / 扫描 %d' % (changed, len(files)))

    # ---- 3. 复查：当验证闸门用 ----
    leftover: list[tuple[str, str]] = []
    if not args.dry:
        for f in files:
            text = f.read_text(encoding='utf-8', errors='ignore')
            for prefix, pattern, group in CLASS_PATTERNS:
                for m in pattern.finditer(text):
                    found = m.group(group)
                    if KEEP.search(found) or (prefix == 'tenant' and found in PUBLIC_HOSTS):
                        continue
                    leftover.append((f.name, found))
    print('残留 =', leftover if leftover else '无')
    return 1 if leftover else 0


if __name__ == '__main__':
    sys.exit(main())
