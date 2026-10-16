#!/usr/bin/env python3
"""飞书机器人私聊(open_id)可达性探针。

注意：本脚本用「真实发送」来做验证 —— 这就是可达性验证本身。
要零噪音自检，请挑一个**预期失败**的目标（如已确认跨应用的 open_id）来跑。

用法:
  # 测应用创建者本人（隔离"通道是否可用"）
  PYTHONPATH=~/.hermes/skills/kingdou/scripts \
  $KINDOU_PY \
    ~/.hermes/skills/kingdou/scripts/check-dm-capability.py --self

  # 按中央配置 openid_name_mapping 里的姓名测
  ... check-dm-capability.py 员工<02> 管理员<01>

  # 直接指定 open_id
  ... check-dm-capability.py --open-id ou_xxx
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, '~/.hermes/skills/kingdou/scripts')
from router.feishu_client import FeishuClient  # noqa: E402

CONFIG = Path('~/.hermes/skills/kingdou/configs/piecework-groups.json')

MEANING = {
    0: 'OK 已送达',
    230013: 'FAIL 230013 不在应用可用范围（控制台加成员并发布新版本）',
    99992361: 'FAIL 99992361 open_id 跨应用，该 ID 对本应用无效',
    99991672: 'WARN 99991672 应用缺少 contact 权限',
}

TEST_TEXT = '【权限测试】金豆机器人私聊通道验证消息，收到请忽略。'


def load_mapping() -> dict[str, str]:
    try:
        return json.loads(CONFIG.read_text()).get('openid_name_mapping', {}) or {}
    except Exception:
        return {}


def send_dm(client: FeishuClient, open_id: str, text: str) -> dict:
    url = f'{client.base}/im/v1/messages?receive_id_type=open_id'
    payload = {
        'receive_id': open_id,
        'msg_type': 'text',
        'content': json.dumps({'text': text}, ensure_ascii=False),
    }
    return client.session.post(url, headers=client.headers(), json=payload, timeout=10).json()


def app_creator(client: FeishuClient) -> str | None:
    url = f'{client.base}/application/v6/applications/{client.app_id}?lang=zh_cn'
    try:
        d = client.session.get(url, headers=client.headers(), timeout=10).json()
        return ((d.get('data') or {}).get('app') or {}).get('creator_id')
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*', help='openid_name_mapping 中的姓名')
    ap.add_argument('--open-id', action='append', default=[], help='直接指定 open_id，可重复')
    ap.add_argument('--self', action='store_true', help='测应用创建者本人')
    ap.add_argument('--text', default=TEST_TEXT)
    args = ap.parse_args()

    client = FeishuClient()
    mapping = load_mapping()
    by_name = {v: k for k, v in mapping.items()}

    targets: list[tuple[str, str]] = []
    if args.self or not (args.names or args.open_id):
        creator = app_creator(client)
        if creator:
            targets.append((f"应用创建者({mapping.get(creator, '?')})", creator))
        else:
            print('WARN 无法获取应用创建者，跳过 --self')
    for n in args.names:
        oid = by_name.get(n)
        if not oid:
            print(f'WARN 姓名 {n} 不在 openid_name_mapping 中，跳过')
            continue
        targets.append((n, oid))
    for oid in args.open_id:
        targets.append(('(--open-id)', oid))

    if not targets:
        print('没有可测目标。用 --self / 姓名 / --open-id 指定。')
        return 2

    print(f'应用 app_id={client.app_id}  目标数={len(targets)}')
    rc = 0
    for name, oid in targets:
        d = send_dm(client, oid, args.text)
        code = d.get('code')
        mid = (d.get('data') or {}).get('message_id') or '-'
        print(f'{name:<24} {oid}  code={code}  '
              f'{MEANING.get(code, d.get("msg"))}  mid={mid}')
        if code != 0:
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
