#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, traceback
from dataclasses import dataclass
from typing import Any
try:
    from .audit_log import log_event
    from .config_loader import load_config
    from .message_parser import RouteDecision, RouteType, parse_message
    from .submit_piecework import handle_submit
    from .review_piecework import handle_review
    from .cancel_piecework import handle_cancel
    from .query_pending_reviews import handle_pending
    from .query_salary import handle_query
except ImportError:
    from audit_log import log_event
    from config_loader import load_config
    from message_parser import RouteDecision, RouteType, parse_message
    from submit_piecework import handle_submit
    from review_piecework import handle_review
    from cancel_piecework import handle_cancel
    from query_pending_reviews import handle_pending
    from query_salary import handle_query
@dataclass
class DispatchResult:
    ok: bool
    executed: bool
    reason: str
    decision: RouteDecision
    data: dict[str, Any] | None = None
class Router:
    def __init__(self, shadow_only: bool = True):
        self.shadow_only = shadow_only; self.config = load_config()
    def route(self, chat_id: str, sender_id: str, text: str) -> RouteDecision:
        group = (self.config.get('groups') or {}).get(chat_id)
        if not group: return RouteDecision(RouteType.UNKNOWN, 'group_not_configured', '', {})
        return parse_message(text, group.get('name', ''))
    def dispatch(self, chat_id: str, sender_id: str, text: str, dry_run: bool = False, send_reply: bool = True) -> DispatchResult:
        d = self.route(chat_id, sender_id, text)
        event = {'chat_id': chat_id, 'sender_id': sender_id, 'route': d.route_type.value, 'reason': d.reason, 'group': d.group_name, 'shadow_only': self.shadow_only, 'dry_run': dry_run}
        log_event('shadow-router.log', event)
        if d.route_type == RouteType.UNKNOWN: return DispatchResult(False, False, d.reason, d)
        if self.shadow_only: return DispatchResult(True, False, 'shadow_only', d)
        group = (self.config.get('groups') or {}).get(chat_id)
        try:
            if d.route_type == RouteType.SUBMIT: data = handle_submit(chat_id, sender_id, text, d, self.config, group, dry_run, send_reply)
            elif d.route_type == RouteType.REVIEW: data = handle_review(chat_id, sender_id, text, d, self.config, group, dry_run, send_reply)
            elif d.route_type == RouteType.CANCEL: data = handle_cancel(chat_id, sender_id, text, d, self.config, group, dry_run, send_reply)
            elif d.route_type == RouteType.PENDING_REVIEW: data = handle_pending(chat_id, sender_id, text, d, self.config, group, dry_run, send_reply)
            elif d.route_type == RouteType.QUERY: data = handle_query(chat_id, sender_id, text, d, self.config, group, dry_run, send_reply)
            else: data = {'ok': False, 'executed': False, 'reason': 'unhandled_route'}
            log_event('shadow-router.log', {**event, **data})
            return DispatchResult(bool(data.get('ok')), bool(data.get('executed')), data.get('reason', ''), d, data)
        except Exception as e:
            log_event('shadow-router-errors.log', {**event, 'error': str(e), 'traceback': traceback.format_exc()})
            return DispatchResult(False, False, 'exception', d, {'error': str(e)})
def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument('chat_id', nargs='?'); p.add_argument('sender_id', nargs='?'); p.add_argument('text', nargs='?')
    p.add_argument('--execute', action='store_true'); p.add_argument('--dry-run', action='store_true'); p.add_argument('--no-send', action='store_true')
    args = p.parse_args(argv)
    if not args.chat_id or not args.sender_id or args.text is None: p.error('chat_id sender_id text required')
    r = Router(shadow_only=not args.execute)
    if args.execute:
        res = r.dispatch(args.chat_id, args.sender_id, args.text, dry_run=args.dry_run, send_reply=not args.no_send)
        print(json.dumps({'ok': res.ok, 'executed': res.executed, 'reason': res.reason, 'route': res.decision.route_type.value, 'group': res.decision.group_name, 'data': res.data}, ensure_ascii=False, default=str))
    else:
        d = r.route(args.chat_id, args.sender_id, args.text)
        print(json.dumps({'route': d.route_type.value, 'reason': d.reason, 'group': d.group_name, 'payload': d.payload}, ensure_ascii=False, default=str))
if __name__ == '__main__': main()
