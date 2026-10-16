#!/usr/bin/env python3
"""打一份干净的 kingdou 备份包（安装模板）。

配套文档：`references/backup-restore-install.md`「备份包约定」。

用法:
  python3 scripts/make_clean_backup.py [--out-dir DIR] [--owner USER:GROUP]
                                       [--stamp-tz +08:00] [--no-verify]

行为:
  1. 预检 —— 调 `scripts/scrub_restore_identifiers.py`（不带 --dry）扫三个源目录，
     退出码非 0（即仍有标识符/姓名残留）就拒绝打包。
  2. 组装 `kingdou_skill/` + `kingdou_plugin/` + `piecework/groups/` + `MANIFEST.md` + `SHA256SUMS`。
  3. 打包到 `<out-dir>/kingdou_backup_<YYYYmmdd_HHMMSS>.tar.gz`，按 --owner 设属主、0644/0664 权限。
  4. 验证 —— 解开到临时目录：SHA256SUMS 自洽、与源逐文件比对、JSON 合法、py_compile、
     路由 dry-run（期望 group_not_configured）、两个回归测试、复扫无残留。

源目录（默认）:
  ~/.hermes/skills/kingdou   ~/.hermes/plugins/kingdou   ~/.hermes/piecework/groups
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]          # …/skills/kingdou
SCRIPTS_DIR = SKILL_DIR / 'scripts'
DEFAULT_SOURCES = [
    ('kingdou_skill', SKILL_DIR),
    ('kingdou_plugin', Path.home() / '.hermes' / 'plugins' / 'kingdou'),
    ('piecework/groups', Path.home() / '.hermes' / 'piecework' / 'groups'),
]
SKIP_NAMES = {'__pycache__', '.DS_Store'}
HTTP_LIBS = ('python3',)


def _ignore(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n in SKIP_NAMES or n.endswith('.pyc')]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p) for p in root.rglob('*')
            if p.is_file() and not any(part in SKIP_NAMES for part in p.parts) and p.suffix != '.pyc'}


def _parse_tz(spec: str) -> timezone:
    m = re.fullmatch(r'([+-])(\d{1,2}):?(\d{2})', spec.strip())
    if not m:
        raise SystemExit(f'时区格式应为 +HH:MM，收到 {spec!r}')
    sign = -1 if m.group(1) == '-' else 1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def preflight(sources: list[tuple[str, Path]], python: str) -> None:
    roots = [str(p) for _, p in sources if p.exists()]
    scrub = SCRIPTS_DIR / 'scrub_restore_identifiers.py'
    if not scrub.exists():
        raise SystemExit(f'缺少预检脚本 {scrub}')
    proc = subprocess.run([python, str(scrub), *roots], capture_output=True, text=True)
    tail = (proc.stdout or proc.stderr).strip().splitlines()
    print('预检：', tail[-1] if tail else '(无输出)')
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        raise SystemExit('预检失败：源目录仍含标识符/姓名残留，拒绝打包')


def build(name: str, sources: list[tuple[str, Path]], stage_root: Path) -> Path:
    root = stage_root / name
    root.mkdir(parents=True)
    for dest_rel, src in sources:
        if not src.exists():
            print('  跳过（不存在）：%s' % src)
            continue
        shutil.copytree(src, root / dest_rel, ignore=_ignore)
    return root


MANIFEST = """# Kingdou 备份包 {name}

本包是 **干净安装模板**，不含任何真实人员或业务数据：所有 open_id / 群 ID / app_token / table_id /
field_id / 租户域名 / app_id / 姓名都是占位符（`ou_<redacted-NN>`、`oc_<redacted-NN>`、`员工<NN>` …）。

## 内容

| 目录 | 对应安装位置 |
|------|--------------|
| `kingdou_skill/` | `~/.hermes/skills/kingdou/`（SKILL.md、references/、configs/、scripts/） |
| `kingdou_plugin/` | `~/.hermes/plugins/kingdou/`（网关前置路由插件，`pre_gateway_dispatch` 钩子） |
| `piecework/groups/` | `~/.hermes/piecework/groups/`（只有 `_template/config.json` 空格式模板） |

旧版备份包里的 `gateway/feishu.py`（旧 Hermes 的整体平台适配器）与 `openid_name_mapping.json`
（含真实 open_id 的旧映射）本包都没有，理由见 `kingdou_skill/references/backup-restore-install.md`。

## 恢复步骤

1. 解包到持久目录，把三棵目录分别拷回上表位置。
2. 建日志目录 `~/.hermes/logs/kingdou/`。
3. `hermes plugins enable kingdou`，再 `systemctl --user restart hermes-gateway`
   （必须在网关进程之外的 shell 里执行）。
4. 按 SKILL.md「添加新计件群/员工」登记真实群与身份 —— 本包里的占位符照抄不会生效。
5. 装真实数据前先验证：`python3 -m json.tool configs/piecework-groups.json`、`py_compile`、
   `scripts/tests/` 两个回归测试、以及 `scripts/scrub_restore_identifiers.py` 的 dry-run。

生成时间：{created}（{tz}）
"""


def verify(tar_path: Path, sources: list[tuple[str, Path]], python: str, tmp_root: Path) -> bool:
    ok = True
    name = tar_path.name[:-len('.tar.gz')]
    with tarfile.open(tar_path) as tf:
        tf.extractall(tmp_root)
    root = tmp_root / name

    def check(label: str, cond: bool, extra: str = '') -> None:
        nonlocal ok
        print(('✅ ' if cond else '❌ ') + label + (('  ' + extra) if extra else ''))
        ok = ok and cond

    sums = (root / 'SHA256SUMS').read_text().splitlines()
    bad = [l.split('  ', 1)[1] for l in sums if _sha(root / l.split('  ', 1)[1]) != l.split('  ', 1)[0]]
    check('SHA256SUMS 自洽（%d 项）' % len(sums), not bad, str(bad[:3]))

    diffs = []
    for dest_rel, src in sources:
        if not src.exists():
            continue
        a, b = _tree(src), _tree(root / dest_rel)
        diffs += ['%s:%s' % (dest_rel, k) for k in set(a) | set(b) if a.get(k) != b.get(k)]
    check('包内容与源目录一致', not diffs, str(diffs[:3]))

    cfg = root / 'kingdou_skill' / 'configs' / 'piecework-groups.json'
    try:
        json.loads(cfg.read_text(encoding='utf-8'))
        check('configs/piecework-groups.json 合法 JSON', True)
    except Exception as e:  # noqa: BLE001 - 验证路径，失败即报告
        check('configs/piecework-groups.json 合法 JSON', False, str(e))

    pys = [str(p) for p in (root / 'kingdou_skill' / 'scripts').rglob('*.py')]
    pys += [str(root / 'kingdou_plugin' / '__init__.py')]
    proc = subprocess.run([python, '-m', 'py_compile', *pys], capture_output=True, text=True)
    check('py_compile（%d 个 .py）' % len(pys), proc.returncode == 0, proc.stderr.strip()[:120])

    env = {**os.environ, 'PYTHONPATH': str(root / 'kingdou_skill' / 'scripts')}
    proc = subprocess.run([python, '-m', 'router.router', 'oc_example_group', 'ou_example_user',
                           '0.12 103', '--execute', '--dry-run', '--no-send'],
                          capture_output=True, text=True, cwd=str(root / 'kingdou_skill' / 'scripts'), env=env)
    check('路由 dry-run → group_not_configured', 'group_not_configured' in proc.stdout, proc.stdout.strip()[:120])

    for t in ('tests/test_cancel_piecework.py', 'tests/test_gateway_plugin.py'):
        proc = subprocess.run([python, t], capture_output=True, text=True,
                              cwd=str(root / 'kingdou_skill' / 'scripts'), env=env)
        check('包里 %s' % t, '失败 0' in proc.stdout,
              (proc.stdout.strip().splitlines() or [''])[-1] or proc.stderr.strip()[:120])

    scrub = root / 'kingdou_skill' / 'scripts' / 'scrub_restore_identifiers.py'
    proc = subprocess.run([python, str(scrub), str(root)], capture_output=True, text=True)
    check('解包内容无标识符/姓名残留', proc.returncode == 0,
          (proc.stdout.strip().splitlines() or [''])[-1][:120])
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='打一份干净的 kingdou 备份包')
    ap.add_argument('--out-dir', default=os.environ.get('KINDOU_BACKUP_DIR') or str(Path.home()),
                    help='输出目录（默认 $KINDOU_BACKUP_DIR，未设则家目录）')
    ap.add_argument('--owner', default='lmccc:lmccc', help='属主（默认 lmccc:lmccc；留空则不改）')
    ap.add_argument('--stamp-tz', default='+08:00', help='文件名时间戳时区（默认 +08:00）')
    ap.add_argument('--python', default=sys.executable, help='预检/验证用的解释器')
    ap.add_argument('--no-verify', action='store_true', help='跳过打包后验证')
    args = ap.parse_args(argv)

    tz = _parse_tz(args.stamp_tz)
    name = 'kingdou_backup_%s' % datetime.now(tz).strftime('%Y%m%d_%H%M%S')
    out_dir = Path(args.out_dir).expanduser()

    sources = [(dest_rel, p) for dest_rel, p in DEFAULT_SOURCES]
    missing = [str(p) for _, p in sources if not p.exists()]
    if missing:
        print('源目录缺失：%s' % missing, file=sys.stderr)
        return 2

    preflight(sources, args.python)

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (name + '.tar.gz')
    with tempfile.TemporaryDirectory(prefix='kingdou-backup-') as stage:
        stage_root = Path(stage)
        root = build(name, sources, stage_root)
        (root / 'MANIFEST.md').write_text(
            MANIFEST.format(name=name, created=datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S'),
                            tz=args.stamp_tz), encoding='utf-8')
        lines = ['%s  %s' % (_sha(f), f.relative_to(root).as_posix())
                 for f in sorted(root.rglob('*')) if f.is_file() and f.name != 'SHA256SUMS']
        (root / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with tarfile.open(out, 'w:gz') as tf:
            tf.add(root, arcname=name)

        if args.owner:
            user, _, group = args.owner.partition(':')
            shutil.chown(out, user=user, group=group or None)
        out.chmod(0o664)
        print('已生成：%s (%.1f KB, %d 个文件)' % (out, out.stat().st_size / 1024, len(lines)))

        if not args.no_verify:
            print()
            with tempfile.TemporaryDirectory(prefix='kingdou-verify-') as vt:
                ok = verify(out, sources, args.python, Path(vt))
            print()
            print('总体：', '全部通过' if ok else '有失败项')
            if not ok:
                return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
