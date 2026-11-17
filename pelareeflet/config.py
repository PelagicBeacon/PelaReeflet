"""PelaReeflet 配置。

所有配置项都来自环境变量，默认值足以本地跑通演示；生产部署务必设置
REEFLET_SECRET（少于 16 位会被视为未配置，服务拒绝签发挑战）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .env import load_dotenv


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or "").strip() or default


def _int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in ("0", "false", "off", "no")


@dataclass
class ReefletConfig:
    # --- 安全 ---
    secret: str = ""
    sitekey: str = "reeflet-demo"

    # --- 难度与时效 ---
    difficulty: int = 20000
    challenge_ttl: int = 300
    ticket_ttl: int = 300
    challenge_rate: int = 2          # 单 IP 每秒挑战签发上限

    # --- 交互关卡 ---
    click_gate: bool = True
    click_min_hold_ms: int = 40
    click_min_path_ms: int = 20
    click_min_path_px: int = 4
    click_max_speed: float = 15000.0
    automation_threshold: int = 6      # 自动化特征累加到这个分才拒绝
    track_strict: bool = False         # 严格模式：轨迹评分超阈值直接拒绝
    track_threshold: int = 4

    # --- 品牌与外观 ---
    brand: str = "PELAGIC BEACON"
    logo_path: str = "/static/brand/pelareeflet-mark.svg"
    #: dark / light / auto（auto = 跟随系统 prefers-color-scheme）
    theme: str = "dark"
    #: 是否显示右上角品牌角标。MIT 不强制，但强烈建议保留 —— 详见 docs/许可说明.md
    attribution: bool = True

    # --- 页脚链接 ---
    license_url: str = "https://github.com/PelagicBeacon/PelaReeflet/blob/main/LICENSE"
    about_url: str = "https://github.com/orgs/PelagicBeacon/repositories"

    # --- 部署 ---
    allowed_origins: tuple[str, ...] = ("*",)
    hostname: str = ""

    @property
    def configured(self) -> bool:
        """密钥齐备才算可用。短于 16 位一律当作没配。"""
        return len(self.secret) >= 16

    @property
    def prefix(self) -> int:
        """把「期望哈希次数」换算成前导 0 的十六进制位数（向上取整）。"""
        n = 1
        while n < 6 and (16 ** n) < max(1, self.difficulty):
            n += 1
        return max(3, min(n, 6))

    @classmethod
    def from_env(cls, use_dotenv: bool = True) -> "ReefletConfig":
        if use_dotenv:
            load_dotenv()
        origins = _str("REEFLET_ALLOWED_ORIGINS", "*")
        return cls(
            secret=_str("REEFLET_SECRET"),
            sitekey=_str("REEFLET_SITEKEY", "reeflet-demo"),
            difficulty=_int("REEFLET_DIFFICULTY", 20000),
            challenge_ttl=_int("REEFLET_CHALLENGE_TTL", 300),
            ticket_ttl=_int("REEFLET_TICKET_TTL", 300),
            challenge_rate=max(1, _int("REEFLET_CHALLENGE_RATE", 2)),
            click_gate=_bool("REEFLET_CLICK_GATE", True),
            automation_threshold=max(1, _int("REEFLET_AUTOMATION_THRESHOLD", 6)),
            track_strict=_bool("REEFLET_TRACK_STRICT", False),
            track_threshold=max(1, _int("REEFLET_TRACK_THRESHOLD", 4)),
            brand=_str("REEFLET_BRAND", "PELAGIC BEACON"),
            logo_path=_str("REEFLET_LOGO", "/static/brand/pelareeflet-mark.svg"),
            theme=_str("REEFLET_THEME", "dark").lower(),
            attribution=_bool("REEFLET_ATTRIBUTION", True),
            license_url=_str("REEFLET_LICENSE_URL",
                             "https://github.com/PelagicBeacon/PelaReeflet/blob/main/LICENSE"),
            about_url=_str("REEFLET_ABOUT_URL",
                           "https://github.com/orgs/PelagicBeacon/repositories"),
            allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            hostname=_str("REEFLET_HOSTNAME"),
        )
