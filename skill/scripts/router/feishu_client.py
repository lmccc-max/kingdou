from __future__ import annotations
import os, time, json
from pathlib import Path
from typing import Any
try:
    import requests
except Exception:
    requests = None
class FeishuError(RuntimeError): pass
class FeishuClient:
    def __init__(self):
        if requests is None: raise FeishuError('requests_missing')
        self.session = requests.Session(); self.base = 'https://open.feishu.cn/open-apis'; self._token = None; self._exp = 0
        vals = {}; p = Path.home() / '.hermes' / '.env'
        if p.exists():
            for line in p.read_text(errors='ignore').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1); vals[k.strip()] = v.strip().strip('\"').strip("'")
        self.app_id = os.environ.get('FEISHU_APP_ID') or vals.get('FEISHU_APP_ID')
        self.app_secret = os.environ.get('FEISHU_APP_SECRET') or vals.get('FEISHU_APP_SECRET')
        if not self.app_id or not self.app_secret: raise FeishuError('missing_feishu_credentials')
    def token(self):
        now = time.time()
        if self._token and now < self._exp - 120: return self._token
        r = self.session.post(f'{self.base}/auth/v3/tenant_access_token/internal', json={'app_id': self.app_id, 'app_secret': self.app_secret}, timeout=10)
        d = r.json()
        if d.get('code') != 0: raise FeishuError(f'token_failed:{d.get("code")}:{d.get("msg")}')
        self._token = d['tenant_access_token']; self._exp = now + int(d.get('expire', 7200)); return self._token
    def headers(self): return {'Authorization': f'Bearer {self.token()}', 'Content-Type': 'application/json; charset=utf-8'}
    def check(self, r):
        d = r.json()
        if d.get('code') != 0: raise FeishuError(f'api_failed:{d.get("code")}:{d.get("msg")}')
        return d
    def send_text(self, chat_id: str, text: str) -> str:
        url = f'{self.base}/im/v1/messages?receive_id_type=chat_id'
        payload = {'receive_id': chat_id, 'msg_type': 'text', 'content': json.dumps({'text': text}, ensure_ascii=False)}
        d = self.check(self.session.post(url, headers=self.headers(), json=payload, timeout=10)); return d.get('data', {}).get('message_id', '')
    def create_record(self, app_token: str, table_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        d = self.check(self.session.post(f'{self.base}/bitable/v1/apps/{app_token}/tables/{table_id}/records', headers=self.headers(), json={'fields': fields}, timeout=15)); return d.get('data', {}).get('record', {})
    def list_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        url = f'{self.base}/bitable/v1/apps/{app_token}/tables/{table_id}/records'; out=[]; page=''
        while True:
            params={'page_size':500}
            if page: params['page_token']=page
            d=self.check(self.session.get(url, headers=self.headers(), params=params, timeout=15)).get('data', {})
            out.extend(d.get('items') or [])
            if not d.get('has_more'): break
            page=d.get('page_token') or ''
            if not page: break
        return out
    def search_by_code(self, app_token: str, table_id: str, code: str) -> dict[str, Any] | None:
        url = f'{self.base}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search'
        payload = {'filter': {'conjunction': 'and', 'conditions': [{'field_name': '编码', 'operator': 'is', 'value': [str(code)]}]}, 'page_size': 10}
        items = self.check(self.session.post(url, headers=self.headers(), json=payload, timeout=15)).get('data', {}).get('items') or []
        return items[0] if items else None
    def get_record(self, app_token: str, table_id: str, record_id: str) -> dict[str, Any] | None:
        try:
            d = self.check(self.session.get(f'{self.base}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}', headers=self.headers(), timeout=15))
            return d.get('data', {}).get('record')
        except Exception: return None
    def update_record(self, app_token: str, table_id: str, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        d = self.check(self.session.put(f'{self.base}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}', headers=self.headers(), json={'fields': fields}, timeout=15)); return d.get('data', {}).get('record', {})
