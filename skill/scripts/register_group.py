#!/usr/bin/env python3
"""
register_group.py — 计件群自动注册脚本

用法:
  python scripts/register_group.py \
    --chat-id oc_xxx \
    --name "员工<13>计件群" \
    --employee-openid ou_xxx \
    --employee-name "员工<13>" \
    --table-url "https://tenant_<redacted-01>.feishu.cn/wiki/XXX?table=tblYYY"

功能:
  1. 解析 wiki URL → app_token + table_id
  2. 调 Bitable API 获取字段定义
  3. 自动生成 fields_detail
  4. 写入中央配置 piecework-groups.json
  5. 验证 JSON + dry-run 路由测试

可选参数:
  --admin-openid ou_xxx    独立管理员 OpenID
  --dry-run                仅预览，不写入配置
  --skip-verify            跳过 dry-run 路由验证
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ── 路径 ──────────────────────────────────────────────
SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / 'scripts'
CONFIG_PATH = SKILL_DIR / 'configs' / 'piecework-groups.json'

# ── Bitable 类型映射 ─────────────────────────────────
TYPE_MAP = {
    1: 'Text',
    2: 'Number',
    5: 'DateTime',
    7: 'Checkbox',
    11: 'User',
    13: 'Phone',
    15: 'Url',
    17: 'Attachment',
    18: 'Link',
    20: 'Formula',
    22: 'DuplexLink',
    1001: 'CreatedTime',
    1002: 'ModifiedTime',
    1003: 'CreatedUser',
    1004: 'ModifiedUser',
    1005: 'AutoNumber',
}

# ── 需要的字段（用于验证） ─────────────────────────────
REQUIRED_FIELDS = {'编码', '姓名', '单价', '数量'}


def parse_table_url(url: str) -> tuple[str, str]:
    """从 wiki URL 提取 app_token 和 table_id"""
    # 格式: https://xxx.feishu.cn/wiki/{app_token}?table={table_id}
    m = re.search(r'/wiki/([A-Za-z0-9_-]+)', url)
    if not m:
        raise ValueError(f'无法从 URL 提取 app_token: {url}')
    app_token = m.group(1)

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    table_ids = qs.get('table', [])
    if not table_ids:
        raise ValueError(f'无法从 URL 提取 table_id (缺少 ?table= 参数): {url}')
    table_id = table_ids[0]

    return app_token, table_id


def fetch_fields(app_token: str, table_id: str) -> list[dict]:
    """调 Bitable API 获取表格字段定义"""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from router.feishu_client import FeishuClient

    client = FeishuClient()
    token = client.token()
    import requests
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
    url = f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields'
    r = requests.get(url, headers=headers, timeout=15)
    data = r.json()
    if data.get('code') != 0:
        raise RuntimeError(f'Bitable API 错误: code={data.get("code")} msg={data.get("msg")}')
    return data.get('data', {}).get('items', [])


def build_fields_detail(fields: list[dict]) -> dict:
    """将 API 返回的字段列表转为 fields_detail 格式"""
    detail = {}
    for f in fields:
        name = f.get('field_name', '')
        field_id = f.get('field_id', '')
        type_code = f.get('type', 0)
        type_name = TYPE_MAP.get(type_code, f'Type{type_code}')

        entry: dict = {'field_id': field_id, 'type': type_name}

        # AutoNumber → is_primary
        if type_code == 1005:
            entry['is_primary'] = True

        # Formula → auto_calculated
        if type_code == 20:
            entry['auto_calculated'] = True

        # formatter（从 property 中提取）
        prop = f.get('property', {})
        if prop and isinstance(prop, dict):
            fmt = prop.get('formatter') or prop.get('date_formatter')
            if fmt:
                entry['formatter'] = fmt

        detail[name] = entry
    return detail


def validate_fields(fields_detail: dict) -> list[str]:
    """检查是否包含必要字段"""
    warnings = []
    names = set(fields_detail.keys())
    missing = REQUIRED_FIELDS - names
    if missing:
        warnings.append(f'缺少必要字段: {", ".join(missing)}')
    if '编码' in fields_detail:
        if fields_detail['编码'].get('type') != 'AutoNumber':
            warnings.append(f'"编码" 字段类型不是 AutoNumber，而是 {fields_detail["编码"].get("type")}')
    if '金额' in fields_detail:
        if fields_detail['金额'].get('type') != 'Formula':
            warnings.append(f'"金额" 字段类型不是 Formula，而是 {fields_detail["金额"].get("type")}')
    return warnings


def load_config() -> dict:
    with CONFIG_PATH.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    # 更新版本和时间
    try:
        old_ver = cfg.get('version', '1.0')
        parts = old_ver.split('.')
        minor = int(parts[1]) + 1 if len(parts) > 1 else 1
        cfg['version'] = f'{parts[0]}.{minor}'
    except Exception:
        cfg['version'] = '1.1'
    cfg['updated_at'] = date.today().isoformat()

    with CONFIG_PATH.open('w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write('\n')


def run_dry_run(chat_id: str, employee_openid: str) -> dict:
    """执行 dry-run 路由验证"""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from router.router import Router

    r = Router(shadow_only=False)
    res = r.dispatch(chat_id, employee_openid, '0.12 103', dry_run=True, send_reply=False)
    return {
        'ok': res.ok,
        'executed': res.executed,
        'reason': res.reason,
        'route': res.decision.route_type.value,
        'group': res.decision.group_name,
    }


def main():
    p = argparse.ArgumentParser(description='计件群自动注册')
    p.add_argument('--chat-id', required=True, help='群聊 ID (oc_xxx)')
    p.add_argument('--name', required=True, help='群名称')
    p.add_argument('--employee-openid', required=True, help='员工 OpenID (ou_xxx)')
    p.add_argument('--employee-name', required=True, help='员工姓名')
    p.add_argument('--table-url', required=True, help='飞书表格 wiki URL')
    p.add_argument('--admin-openid', default=None, help='独立管理员 OpenID (可选)')
    p.add_argument('--dry-run', action='store_true', help='仅预览，不写入配置')
    p.add_argument('--skip-verify', action='store_true', help='跳过 dry-run 路由验证')
    args = p.parse_args()

    print(f'=== 计件群注册 {"[DRY-RUN]" if args.dry_run else ""} ===\n')

    # Step 1: 解析 URL
    print('[1/5] 解析表格 URL...')
    try:
        app_token, table_id = parse_table_url(args.table_url)
        print(f'  app_token : {app_token}')
        print(f'  table_id  : {table_id}')
    except ValueError as e:
        print(f'  ❌ {e}')
        sys.exit(1)

    # Step 2: 获取字段
    print('\n[2/5] 获取 Bitable 字段定义...')
    try:
        fields = fetch_fields(app_token, table_id)
        print(f'  ✅ 获取到 {len(fields)} 个字段')
    except Exception as e:
        print(f'  ❌ {e}')
        sys.exit(1)

    # Step 3: 生成 fields_detail
    print('\n[3/5] 生成 fields_detail...')
    fields_detail = build_fields_detail(fields)
    for name, info in fields_detail.items():
        marker = '  ★' if name in REQUIRED_FIELDS else '   '
        print(f'  {marker} {name}: {info["field_id"]} ({info["type"]})')

    warnings = validate_fields(fields_detail)
    if warnings:
        print('\n  ⚠️  验证警告:')
        for w in warnings:
            print(f'    - {w}')
    else:
        print('\n  ✅ 字段验证通过')

    # Step 4: 构建配置
    print('\n[4/5] 构建群组配置...')
    group_cfg = {
        'name': args.name,
        'app_token': app_token,
        'table_id': table_id,
        'independent_admins': [args.admin_openid] if args.admin_openid else [],
        'employee_list': [args.employee_openid],
        'fields_detail': fields_detail,
    }

    print(f'  群名    : {group_cfg["name"]}')
    print(f'  员工    : {args.employee_name} ({args.employee_openid})')
    if args.admin_openid:
        print(f'  管理员  : {args.admin_openid}')

    # Step 5: 写入 / 预览
    if args.dry_run:
        print('\n[5/5] DRY-RUN 模式，不写入配置')
        print('\n将要写入的配置:')
        print(json.dumps({args.chat_id: group_cfg}, ensure_ascii=False, indent=2))
    else:
        print('\n[5/5] 写入中央配置...')
        cfg = load_config()

        # 检查是否已存在
        existing = (cfg.get('groups') or {}).get(args.chat_id)
        if existing:
            print(f'  ⚠️  群 {args.chat_id} 已存在 ({existing.get("name")})，将覆盖')

        # 更新 openid_name_mapping
        mapping = cfg.get('openid_name_mapping', {})
        if args.employee_openid not in mapping:
            mapping[args.employee_openid] = args.employee_name
            print(f'  + openid_name_mapping: {args.employee_openid} → {args.employee_name}')
        if args.admin_openid and args.admin_openid not in mapping:
            mapping[args.admin_openid] = f'管理员({args.name})'
            print(f'  + openid_name_mapping: {args.admin_openid} → 管理员({args.name})')
        cfg['openid_name_mapping'] = mapping

        # 更新 groups
        if 'groups' not in cfg:
            cfg['groups'] = {}
        cfg['groups'][args.chat_id] = group_cfg

        # 写入
        save_config(cfg)
        print(f'  ✅ 已写入 {CONFIG_PATH}')
        print(f'  版本: {cfg["version"]}, 日期: {cfg["updated_at"]}')

        # JSON 校验
        print('\n  验证 JSON 完整性...')
        try:
            json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            print('  ✅ JSON 格式正确')
        except json.JSONDecodeError as e:
            print(f'  ❌ JSON 格式错误: {e}')
            sys.exit(1)

    # Step 6 (可选): dry-run 路由验证
    if not args.skip_verify:
        print('\n[验证] 执行 dry-run 路由测试...')
        try:
            # 如果是 dry-run 模式，需要临时加载新配置
            if args.dry_run:
                # 临时写入再回滚
                cfg = load_config()
                backup = json.dumps(cfg, ensure_ascii=False)
                cfg['groups'][args.chat_id] = group_cfg
                with CONFIG_PATH.open('w', encoding='utf-8') as f:
                    json.dump(cfg, f, ensure_ascii=False, indent=2)
                    f.write('\n')

            result = run_dry_run(args.chat_id, args.employee_openid)
            print(f'  route  : {result["route"]}')
            print(f'  group  : {result["group"]}')
            print(f'  reason : {result["reason"]}')

            if result['route'] == 'submit' and result['group'] == args.name:
                print('  ✅ 路由验证通过')
            else:
                print(f'  ⚠️  路由结果不符合预期 (期望 route=submit, group={args.name})')

            # 回滚
            if args.dry_run:
                with CONFIG_PATH.open('w', encoding='utf-8') as f:
                    f.write(backup)
                print('  (dry-run: 已回滚配置)')

        except Exception as e:
            print(f'  ❌ 路由验证失败: {e}')
            # 回滚
            if args.dry_run:
                with CONFIG_PATH.open('w', encoding='utf-8') as f:
                    f.write(backup)
    else:
        print('\n[验证] 已跳过 (--skip-verify)')

    print('\n=== 完成 ===')


if __name__ == '__main__':
    main()
