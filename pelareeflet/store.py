"""进程内的最小状态：已用票据、限流窗口。

单进程部署（gunicorn -w 1 / waitress）直接可用；多进程或多实例时需要把
这里换成 Redis —— 接口只有 mark_used / consume / rate_ok 三个，替换成本很低。
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class MemoryStore:
    def __init__(self, max_entries: int = 50000):
        self._lock = threading.Lock()
        self._used_challenges: dict[str, float] = {}
        self._used_tickets: dict[str, float] = {}
        self._rate: dict[str, deque] = defaultdict(deque)
        self._max = max_entries
        self.last_result: dict = {"at": 0.0, "ok": None, "reason": ""}

    # ---------------------------------------------------------------- 挑战票
    def mark_challenge_used(self, key: str, expire_at: float) -> bool:
        now = time.time()
        with self._lock:
            if key in self._used_challenges:
                return False
            if len(self._used_challenges) > self._max:
                self._used_challenges.clear()
            self._used_challenges = {
                k: exp for k, exp in self._used_challenges.items() if exp >= now
            }
            self._used_challenges[key] = expire_at
            return True

    # ---------------------------------------------------------------- 通行票
    def consume_ticket(self, jti: str, expire_at: float) -> bool:
        now = time.time()
        with self._lock:
            if jti in self._used_tickets:
                return False
            if len(self._used_tickets) > self._max:
                self._used_tickets.clear()
            self._used_tickets = {
                k: exp for k, exp in self._used_tickets.items() if exp >= now
            }
            self._used_tickets[jti] = expire_at
            return True

    # ---------------------------------------------------------------- 限流
    def rate_ok(self, key: str, limit: int) -> bool:
        if not key:
            return True
        now = time.time()
        with self._lock:
            if len(self._rate) > 50000:
                self._rate.clear()
            q = self._rate[key]
            while q and now - q[0] > 1.0:
                q.popleft()
            if len(q) >= max(1, limit):
                return False
            q.append(now)
            return True

    def record(self, ok: bool, reason: str) -> None:
        self.last_result = {"at": time.time(), "ok": ok, "reason": reason}
