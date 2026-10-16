#!/usr/bin/env python3
"""kingdou 网关插件（pre_gateway_dispatch 回调）接线自测。

只验证"插件 → router → 拦截判定"这条链路的契约，不碰生产 Bitable：
把 _run_router 换成桩，因此不会有真实写库/发消息。
"""
from __future__ import annotations
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

PLUGIN = Path.home() / '.hermes' / 'plugins' / 'kingdou' / '__init__.py'
spec = importlib.util.spec_from_file_location('kingdou_plugin', PLUGIN)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

GROUP = 'oc_example_group'


def ev(platform='feishu', chat_id=GROUP, user_id='ou_example_user',
       text='0.12 103', message_id='om_x'):
    src = SimpleNamespace(platform=SimpleNamespace(value=platform), chat_id=chat_id,
                          user_id=user_id, message_id=message_id)
    return SimpleNamespace(source=src, text=text, message_id=message_id)


def run(coro):
    return asyncio.run(coro)


fails = []


def check(label, got, want):
    ok = got == want
    print(('✅ ' if ok else '❌ ') + label + ' → ' + repr(got))
    if not ok:
        fails.append(label)


# 1) 非飞书平台 → 放行
check('非飞书平台放行', run(mod._on_pre_gateway_dispatch(ev(platform='telegram'))), None)

# 2) 非 open_id 发送者 → 放行
check('非 open_id 发送者放行', run(mod._on_pre_gateway_dispatch(ev(user_id='u_123'))), None)

# 3) 空文本 → 放行
check('空文本放行', run(mod._on_pre_gateway_dispatch(ev(text=''))), None)

# 4) 现状（未登记任何员工）→ router 判 ok=False → 放行给 AI
check('未登记身份 → 放行给 AI', run(mod._on_pre_gateway_dispatch(ev())), None)

# 5) 未登记群 → 放行
check('未登记群 → 放行给 AI', run(mod._on_pre_gateway_dispatch(ev(chat_id='oc_unknown'))), None)

# 6) router 抛异常 → fail-open 放行（不能阻断网关）
_orig = mod._run_router
mod._run_router = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
check('router 异常 → fail-open 放行', run(mod._on_pre_gateway_dispatch(ev())), None)

# 7) 脚本成功执行 → 必须返回 skip（拦截 AI）
mod._run_router = lambda *a, **k: True
check('脚本成功 → 拦截 AI', run(mod._on_pre_gateway_dispatch(ev())),
      {'action': 'skip', 'reason': 'kingdou_handled'})

# 8) mode=off → 完全不介入
mod._run_router = _orig
import os
os.environ['ENABLE_KINGDOU_GATEWAY_MODE'] = 'off'
check('mode=off → 放行', run(mod._on_pre_gateway_dispatch(ev())), None)

# 9) mode=shadow → 只分类，不拦截
os.environ['ENABLE_KINGDOU_GATEWAY_MODE'] = 'shadow'
check('mode=shadow → 放行（只观察）', run(mod._on_pre_gateway_dispatch(ev())), None)
del os.environ['ENABLE_KINGDOU_GATEWAY_MODE']

print()
print('通过 %d / 失败 %d' % (9 - len(fails), len(fails)))
sys.exit(1 if fails else 0)
