# -*- coding: utf-8 -*-
"""匿名会话轮换抓取器：零账号，绕开评论接口 461。

原理（2026-10-02 实测）
-----------------------
- 平台对评论接口（edith.xiaohongshu.com/comment/*）按**会话**限流：
  同一会话第 2 次请求即 461。
- 但全新匿名会话（/login/activate 零账号签发）的**首请求必过**（5/5 成功）。
- 匿名身份（a1/webId/web_session 全本地随机生成或服务器签发给随机设备），
  与任何真实账号无关，主号零参与、零风险。
- generate_init_cookies() 约 8-12 次请求走导航/安全域名，
  **不消耗评论接口配额**——等于用廉价请求换配额。

策略：每 MAX_USES 次评论请求就换一个全新匿名会话。
"""

from __future__ import annotations

import time

MAX_USES = 1        # 同一匿名会话最多发几次评论请求（实测 1）
SESSION_GAP = 2.0   # 新建会话之间静置（秒），模拟新用户打开网站
REQ_GAP = 1.0       # 评论请求之间静置（秒）


class AnonPool:
    """维护一个匿名会话，用完即换。调用方只需调 request()。"""

    def __init__(self, log=None):
        self._apis = None
        self._uses = 0
        self._total_sessions = 0
        self._total_requests = 0
        self._log = log or (lambda m: None)

    def _fresh(self):
        from apis.xhs_pc_login_apis import XHSLoginApi
        from xhs_utils.xhs_pc import XHSPcAuth
        from apis.xhs_pc_apis import XHS_Apis
        ck = XHSLoginApi().generate_init_cookies()
        cstr = "; ".join(f"{k}={v}" for k, v in ck.items())
        auth = XHSPcAuth.from_cookie(cstr)
        apis = XHS_Apis(auth)
        apis.bootstrap()
        self._apis = apis
        self._uses = 0
        self._total_sessions += 1
        uid = getattr(auth, "user_id", "?")
        self._log(f"      [匿名会话#{self._total_sessions} uid={uid}] 新建")
        time.sleep(SESSION_GAP)

    def request(self, path: str, params: dict):
        """发一次评论类请求，自动轮换会话。461 会抛 RiskError。"""
        from thread_fetcher import _request
        if self._apis is None or self._uses >= MAX_USES:
            self._fresh()
        d = _request(self._apis, path, params)   # 461 抛 RiskError
        self._uses += 1
        self._total_requests += 1
        time.sleep(REQ_GAP)
        return d

    @property
    def stats(self) -> dict:
        return {"sessions": self._total_sessions,
                "requests": self._total_requests}
