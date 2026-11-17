"""PelaReeflet 核心：挑战签发、交互关卡、工作量证明、通行票校验。

三条设计原则
------------
1. **无状态优先**：挑战票 / 关卡票 / 通行票都是「签名过的 JSON」，服务端只
   记「已用过的 jti」，重启丢状态也不影响正确性，只是重放窗口略大。
2. **先验答案，再记账**：任何人拿一张真票 + 假答案都不能把票烧掉。
3. **只拒绝确定性异常**：行为分析拿不准的一律放行，后面还有 PoW 兜底。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import ReefletConfig
from .store import MemoryStore

MAX_NONCE = 10 ** 15

#: 命中即拒绝的确定性信号（一条就够）
HARD_AUTOMATION = {"webdriver", "headless_ua", "chrome_missing"}


# ============================================================
# 签名 / 验签
# ============================================================
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode())


def pack(secret: str, payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return _b64e(body) + "." + sig


def unpack(secret: str, token: str) -> dict | None:
    if not token or not isinstance(token, str) or token.count(".") != 1:
        return None
    body_b64, sig = token.split(".", 1)
    try:
        body = _b64d(body_b64)
    except Exception:
        return None
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        payload = json.loads(body.decode())
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def ip_fingerprint(ip: str | None) -> str:
    return hashlib.sha256((ip or "").encode()).hexdigest()[:16]


# ============================================================
# 主体
# ============================================================
class Reeflet:
    def __init__(self, cfg: ReefletConfig, store: MemoryStore | None = None):
        self.cfg = cfg
        self.store = store or MemoryStore()

    # ---------------------------------------------------------- 签发挑战
    def issue_challenge(self, ip: str | None) -> tuple[dict | None, str]:
        """返回 (data, reason)。reason 为 ok / unavailable / rate_limited。"""
        if not self.cfg.configured:
            return None, "unavailable"
        if not self.store.rate_ok(ip or "", self.cfg.challenge_rate):
            return None, "rate_limited"

        payload = {
            "k": "challenge",
            "challenge": secrets.token_hex(32),
            "prefix": self.cfg.prefix,
            "exp": int(time.time()) + self.cfg.challenge_ttl,
            "ip": ip_fingerprint(ip),
            "sk": self.cfg.sitekey,
        }
        return {
            "challenge": payload["challenge"],
            "prefix": payload["prefix"],
            "difficulty": self.cfg.difficulty,
            "expires": payload["exp"],
            "token": pack(self.cfg.secret, payload),
        }, "ok"

    # ---------------------------------------------------------- 交互关卡
    def check_interaction(
        self,
        token: str | None,
        path,
        pointer_type: str | None,
        hold_ms,
        features,
        ip: str | None,
    ) -> tuple[bool, str, str, int]:
        """返回 (ok, reason, gate_token, score)。"""
        if not self.cfg.configured:
            return False, "unavailable", "", 0

        payload = unpack(self.cfg.secret, (token or "").strip())
        if not payload or payload.get("k") != "challenge":
            return False, "invalid", "", 0
        if int(payload.get("exp") or 0) < time.time():
            return False, "expired", "", 0
        if not hmac.compare_digest(str(payload.get("ip") or ""), ip_fingerprint(ip)):
            return False, "bad_ip", "", 0

        challenge = str(payload.get("challenge") or "")
        if not challenge:
            return False, "invalid", "", 0

        features = features if isinstance(features, dict) else {}

        # --- 无头 / 自动化特征：确定性信号直接拒绝，可疑信号累加评分 ---
        auto_score, auto_reasons = self._score_features(features)
        if auto_reasons:
            hard = [r for r in auto_reasons if r in HARD_AUTOMATION]
            if hard:
                return False, "automation", "", 10
            if auto_score >= self.cfg.automation_threshold:
                return False, "automation", "", 10

        try:
            hold = int(hold_ms)
        except (TypeError, ValueError):
            hold = 0

        kind = (pointer_type or "").strip().lower()
        points = _norm_path(path)

        if kind == "synthetic":
            return False, "automation", "", 10

        def gate() -> str:
            return pack(self.cfg.secret, {
                "k": "gate",
                "chal": challenge,
                "exp": int(time.time()) + self.cfg.challenge_ttl,
                "ip": ip_fingerprint(ip),
            })

        if kind in ("touch", "pen"):
            if hold and hold < max(10, self.cfg.click_min_hold_ms // 2):
                return False, "interaction", "", 2
            return True, "ok", gate(), 0

        if kind == "key":
            return True, "ok", gate(), 0

        # 鼠标：没有轨迹时用按压时长区分「手就在框上」和「脚本点一下」
        if len(points) < 2:
            if hold < self.cfg.click_min_hold_ms:
                return False, "interaction", "", 3
            return True, "ok", gate(), min(10, 1 + auto_score)

        span = points[-1][2] - points[0][2]
        length = 0.0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i - 1][0]
            dy = points[i][1] - points[i - 1][1]
            length += (dx * dx + dy * dy) ** 0.5

        if span < self.cfg.click_min_path_ms or length < self.cfg.click_min_path_px:
            return False, "interaction", "", 3 + auto_score
        if span > 0 and length / span * 1000 > self.cfg.click_max_speed:
            return False, "interaction", "", 3 + auto_score

        # --- 轨迹度量：只做评分，严格模式（REEFLET_TRACK_STRICT=1）才拒绝 ---
        m = _track_metrics(points)
        total = auto_score + m["score"]
        if self.cfg.track_strict and m["score"] >= self.cfg.track_threshold:
            return False, "interaction", "", min(10, total)
        return True, "ok", gate(), min(10, total)

    def _score_features(self, features: dict) -> tuple[int, list[str]]:
        """无头 / 自动化环境评分。

        返回 (分数, 命中信号)。HARD_AUTOMATION 里的信号一条就拒绝，其余累加，
        达到 automation_threshold 才拒绝。

        关键约定：**字段缺失 = 未知，不计分**。老版本组件、第三方集成可能只传
        部分字段，不能因此把人当机器人；只有「明确上报了异常值」才算信号。
        """
        score = 0
        reasons: list[str] = []

        def as_int(key):
            if key not in features:
                return None
            try:
                return int(features.get(key) or 0)
            except (TypeError, ValueError):
                return None

        ua = str(features.get("ua") or "")
        if features.get("webdriver") is True:
            reasons.append("webdriver")
        if features.get("headless_ua") is True or "headlesschrome" in ua.lower():
            reasons.append("headless_ua")

        # 有 Chrome 的 UA，却没有 window.chrome（Puppeteer / Playwright 常见）
        if "chrome/" in ua.lower() and features.get("chrome") is False:
            reasons.append("chrome_missing")
            score += 3

        plugins = as_int("plugins")
        languages = as_int("languages")
        hardware = as_int("hardware")
        depth = as_int("depth")
        screen_w = as_int("screen_w")

        if plugins == 0 and languages == 0:
            reasons.append("empty_env")
            score += 3
        if hardware == 0:
            reasons.append("no_hardware")
            score += 2
        if depth == 0:
            reasons.append("no_color_depth")
            score += 2
        if screen_w is not None and screen_w <= 0:
            reasons.append("no_screen")
            score += 2

        return score, reasons

    def _gate_ok(self, gate_token: str | None, challenge: str, ip: str | None) -> bool:
        payload = unpack(self.cfg.secret, (gate_token or "").strip())
        if not payload or payload.get("k") != "gate":
            return False
        if int(payload.get("exp") or 0) < time.time():
            return False
        if not hmac.compare_digest(str(payload.get("ip") or ""), ip_fingerprint(ip)):
            return False
        return hmac.compare_digest(str(payload.get("chal") or ""), challenge)

    # ---------------------------------------------------------- 校验答案
    def solve(
        self,
        token: str | None,
        nonce,
        ip: str | None,
        gate: str | None = None,
    ) -> tuple[bool, str, str]:
        """返回 (ok, reason, ticket)。reason 见 README 的错误码表。"""
        if not self.cfg.configured:
            return False, "unavailable", ""

        token = (token or "").strip() if isinstance(token, str) else ""
        if not token:
            return False, "missing", ""

        payload = unpack(self.cfg.secret, token)
        if not payload or payload.get("k") != "challenge":
            return self._rec(False, "invalid", "")
        if int(payload.get("exp") or 0) < time.time():
            return self._rec(False, "expired", "")
        if not hmac.compare_digest(str(payload.get("ip") or ""), ip_fingerprint(ip)):
            return self._rec(False, "bad_ip", "")

        challenge = str(payload.get("challenge") or "")
        prefix = int(payload.get("prefix") or 0)
        if not challenge or not (1 <= prefix <= 6):
            return self._rec(False, "invalid", "")

        # 开了交互关卡时，必须先拿到关卡票，否则脚本能跳过第一步直接算 PoW
        if self.cfg.click_gate and not self._gate_ok(gate, challenge, ip):
            return self._rec(False, "need_gate", "")

        try:
            nonce_int = int(nonce)
        except (TypeError, ValueError):
            return self._rec(False, "wrong", "")
        if nonce_int < 0 or nonce_int > MAX_NONCE:
            return self._rec(False, "wrong", "")

        digest = hashlib.sha256(f"{challenge}:{nonce_int}".encode()).hexdigest()
        if not digest.startswith("0" * prefix):
            return self._rec(False, "wrong", "")

        # 顺序关键：先验答案，再记账
        key = hashlib.sha256(token.encode()).hexdigest()
        if not self.store.mark_challenge_used(key, int(payload.get("exp") or 0)):
            return self._rec(False, "replayed", "")

        ticket = self._issue_ticket(challenge, ip)
        return self._rec(True, "ok", ticket)

    def _issue_ticket(self, challenge: str, ip: str | None) -> str:
        now = int(time.time())
        return pack(self.cfg.secret, {
            "k": "ticket",
            "jti": secrets.token_hex(16),
            "chal": challenge,
            "sk": self.cfg.sitekey,
            "iat": now,
            "exp": now + self.cfg.ticket_ttl,
            "ip": ip_fingerprint(ip),
        })

    # ---------------------------------------------------------- 服务端校验
    def siteverify(
        self,
        ticket: str | None,
        ip: str | None = None,
        bind_ip: bool = False,
        sitekey: str | None = None,
    ) -> tuple[bool, str, dict]:
        """业务后端拿票来换结论（对应 Turnstile 的 siteverify）。"""
        if not self.cfg.configured:
            return False, "unavailable", {}

        payload = unpack(self.cfg.secret, (ticket or "").strip())
        if not payload or payload.get("k") != "ticket":
            return self._rec(False, "invalid", "")

        if sitekey and not hmac.compare_digest(str(payload.get("sk") or ""), sitekey):
            return self._rec(False, "bad_sitekey", "")
        if int(payload.get("exp") or 0) < time.time():
            return self._rec(False, "expired", "")
        if bind_ip and not hmac.compare_digest(
            str(payload.get("ip") or ""), ip_fingerprint(ip)
        ):
            return self._rec(False, "bad_ip", "")

        jti = str(payload.get("jti") or "")
        if not jti or not self.store.consume_ticket(jti, int(payload.get("exp") or 0)):
            return self._rec(False, "replayed", "")

        return self._rec(True, "ok", payload)

    def _rec(self, ok: bool, reason: str, ticket: str) -> tuple[bool, str, str]:
        self.store.record(ok, reason)
        return ok, reason, ticket

    # ---------------------------------------------------------- 前端配置
    def client_config(self) -> dict:
        return {
            "enabled": self.cfg.configured,
            "sitekey": self.cfg.sitekey,
            "difficulty": self.cfg.difficulty,
            "prefix": self.cfg.prefix,
            "challenge_ttl": self.cfg.challenge_ttl,
            "click": self.cfg.click_gate,
            "theme": self.cfg.theme,
            "attribution": self.cfg.attribution,
            "brand": self.cfg.brand,
            "logo": self.cfg.logo_path,
            "links": {
                "license": self.cfg.license_url,
                "about": self.cfg.about_url,
            },
        }


def _track_metrics(points: list[tuple[float, float, float]]) -> dict:
    """给鼠标轨迹打分（0~6）。

    注意：这是**评分**不是判决。组件的采样被节流到 >=25ms，时间间隔天然
    比较整齐，所以「dt 多样性」这类指标在这里只能当弱信号用；默认不拒绝，
    只在 REEFLET_TRACK_STRICT=1 时按阈值拒绝。
    """
    n = len(points)
    if n < 2:
        return {"score": 0, "n": n, "duration": 0, "dt_unique": 0,
                "dx_unique": 0, "y_range": 0.0, "back_ratio": 0.0, "length": 0.0}

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ts = [p[2] for p in points]

    dts = [ts[i + 1] - ts[i] for i in range(n - 1)]
    dxs = [xs[i + 1] - xs[i] for i in range(n - 1)]
    dts_nz = [d for d in dts if d > 0]
    dxs_nz = [d for d in dxs if abs(d) > 0.5]

    dt_unique = len({round(d, 1) for d in dts_nz})
    dx_unique = len({round(d, 1) for d in dxs_nz})
    y_range = max(ys) - min(ys)
    back = sum(1 for d in dxs if d < -0.5)
    back_ratio = back / len(dxs) if dxs else 0.0

    length = 0.0
    for i in range(1, n):
        dx = xs[i] - xs[i - 1]
        dy = ys[i] - ys[i - 1]
        length += (dx * dx + dy * dy) ** 0.5

    # 说明：**不把时间间隔（dt）当信号**。组件把 mousemove 节流到 25ms，
    # 真人采到的 dt 本来就高度整齐，用它判机器人必然误伤。
    score = 0
    if len(dxs_nz) >= 8 and dx_unique <= 2:
        score += 2          # 位移值几乎只有一两种 = 脚本线性插值
    if y_range < 0.5:
        score += 2          # 人手几乎画不出完美水平线
    if len(dxs_nz) > 10 and back == 0:
        score += 1          # 全程零回退
    if n > 120 and length > 5000:
        score += 1          # 一次点击前扫过整屏

    return {
        "score": min(score, 6),
        "n": n,
        "duration": ts[-1] - ts[0],
        "dt_unique": dt_unique,
        "dx_unique": dx_unique,
        "y_range": round(y_range, 2),
        "back_ratio": round(back_ratio, 3),
        "length": round(length, 2),
    }


def _norm_path(raw) -> list[tuple[float, float, float]]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[-200:]:
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            try:
                out.append((float(item[0]), float(item[1]), float(item[2])))
            except (TypeError, ValueError):
                continue
        elif isinstance(item, dict):
            try:
                out.append((float(item.get("x")), float(item.get("y")), float(item.get("t"))))
            except (TypeError, ValueError):
                continue
    return out


MESSAGES = {
    "rate_limited": "请求过于频繁，请稍后再试",
    "expired": "人机验证已过期，请重新验证",
    "replayed": "人机验证已失效，请重新验证",
    "bad_ip": "网络环境发生变化，请重新验证",
    "unavailable": "人机验证暂时不可用，请稍后重试",
    "missing": "请先完成人机验证",
    "interaction": "验证未通过，请刷新页面后重试",
    "automation": "验证未通过，请刷新页面后重试",
    "need_gate": "页面已更新，请刷新后重试",
    "wrong": "验证未通过，请重试",
    "invalid": "验证数据无效，请刷新后重试",
    "bad_sitekey": "站点密钥不匹配",
}


def failure_message(reason: str) -> str:
    return MESSAGES.get(reason, "人机验证未通过，请重试")
