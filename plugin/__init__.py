"""Kingdou 网关前置路由（Hermes 插件形态）。

历史版本把这段逻辑硬编码进 `gateway/platforms/feishu.py`（`_run_kingdou_gateway_router`）。
当前 Hermes 把飞书拆成插件（`plugins/platforms/feishu/adapter.py`），并且提供了官方扩展点
`pre_gateway_dispatch`（每个入站 MessageEvent 一次、认证之前触发，可返回 {"action": "skip"}
丢弃该消息）。本插件把同一条业务链路接到这个受支持的钩子上，因此：

* 不修改 Hermes 安装目录下的任何文件，`hermes update` 不会冲掉集成；
* 开关语义与 SKILL.md 一致：ENABLE_KINGDOU_GATEWAY_MODE=execute | shadow | off；
* 日志标记与旧版一致：`[KingdouScript]` / `[KingdouShadow]`，便于沿用既有排障命令；
* 失败一律 fail-open（返回 None → 交给 AI），绝不阻断正常消息。

业务分类与写库完全由 skill 内的 router 负责，本文件不含业务规则。
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SKILL_DIR = Path.home() / ".hermes" / "skills" / "kingdou"
SCRIPTS_DIR = SKILL_DIR / "scripts"
ROUTER_FILE = SCRIPTS_DIR / "router" / "router.py"

_OFF_VALUES = {"0", "false", "no", "off", "disabled"}


def _mode() -> str:
    return (os.environ.get("ENABLE_KINGDOU_GATEWAY_MODE") or "execute").strip().lower()


def _snippet(text: str, limit: int = 120) -> str:
    return (text or "").replace("\n", " ")[:limit]


def _run_router(chat_id: str, sender_id: str, text: str, message_id: str = "") -> bool:
    """同步执行 Kingdou router；返回 True 表示"脚本已成功处理，应拦截 AI"。

    由 :func:`_on_pre_gateway_dispatch` 放进线程池调用：router 内部会做阻塞的
    飞书 HTTP 调用与固定 sleep，不能跑在网关事件循环上。
    """
    scripts_dir_str = str(SCRIPTS_DIR)
    if scripts_dir_str not in sys.path:
        sys.path.insert(0, scripts_dir_str)
    from router.router import Router  # type: ignore  # noqa: WPS433 (runtime-path import)

    if _mode() == "shadow":
        decision = Router(shadow_only=True).route(chat_id, sender_id, text)
        logger.info(
            "[KingdouShadow] message_id=%s chat_id=%s sender=%s route=%s reason=%s group=%s",
            message_id, chat_id, sender_id,
            getattr(decision.route_type, "value", str(decision.route_type)),
            decision.reason, decision.group_name,
        )
        return False

    result = Router(shadow_only=False).dispatch(chat_id, sender_id, text, dry_run=False, send_reply=True)
    logger.info(
        "[KingdouScript] message_id=%s chat_id=%s sender=%s route=%s ok=%s executed=%s reason=%s group=%s",
        message_id, chat_id, sender_id,
        getattr(result.decision.route_type, "value", str(result.decision.route_type)),
        result.ok, result.executed, result.reason, result.decision.group_name,
    )
    return bool(result.ok and result.executed)


async def _on_pre_gateway_dispatch(event: Any = None, gateway: Any = None,
                                   session_store: Any = None, **_: Any) -> Optional[dict]:
    """`pre_gateway_dispatch` 回调：处理成功→丢给脚本并丢弃消息，否则放行给 AI。"""
    try:
        mode = _mode()
        if mode in _OFF_VALUES:
            return None
        if not ROUTER_FILE.exists():
            return None

        source = getattr(event, "source", None)
        if source is None:
            return None
        platform = getattr(getattr(source, "platform", None), "value", "")
        if platform != "feishu":
            return None

        chat_id = getattr(source, "chat_id", "") or ""
        sender_id = getattr(source, "user_id", None) or ""
        text = getattr(event, "text", "") or ""
        if not chat_id or not sender_id or not text:
            return None
        if not str(sender_id).startswith("ou_"):
            # 飞书 open_id（ou_）才是配置里登记的身份；其它层级（u_/on_）不匹配时交给 AI。
            logger.debug("[KingdouScript] non-open_id sender=%s chat_id=%s; passing to AI",
                         sender_id, chat_id)
            return None

        message_id = getattr(event, "message_id", None) or getattr(source, "message_id", None) or ""
        intercepted = await asyncio.to_thread(
            _run_router, chat_id, str(sender_id), text, str(message_id)
        )
        if intercepted:
            logger.info("[KingdouScript] intercepted message_id=%s chat_id=%s sender=%s; skipping AI pipeline",
                        message_id, chat_id, sender_id)
            return {"action": "skip", "reason": "kingdou_handled"}
    except Exception:
        logger.warning("[KingdouScript] gateway router failed message_id=%s chat_id=%s sender=%s text=%r",
                       getattr(event, "message_id", ""), _snippet(getattr(getattr(event, "source", None), "chat_id", "")),
                       getattr(getattr(event, "source", None), "user_id", ""), _snippet(getattr(event, "text", "")),
                       exc_info=True)
    return None


def register(ctx) -> None:
    """由 Hermes 插件加载器调用一次。"""
    if not SCRIPTS_DIR.exists():
        logger.warning("kingdou plugin: skill 未安装（%s 不存在），插件不生效", SCRIPTS_DIR)
        return
    ctx.register_hook("pre_gateway_dispatch", _on_pre_gateway_dispatch)
    logger.info("kingdou plugin: 已注册 pre_gateway_dispatch（ENABLE_KINGDOU_GATEWAY_MODE=%s）", _mode())
