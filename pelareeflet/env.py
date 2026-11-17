"""极简 .env 读取（不引入 python-dotenv 依赖）。

只支持 KEY=VALUE、# 注释、export 前缀、成对的单双引号；不展开变量、不支持多行。
已存在的真实环境变量优先于 .env —— 生产环境用进程管理器注入即可，不需要带这个文件。
"""
from __future__ import annotations

import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path: str | None = None) -> int:
    """把 .env 读进 os.environ，返回注入的条目数。"""
    path = path or os.path.join(_ROOT, ".env")
    if not os.path.isfile(path):
        return 0

    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return 0

    loaded = 0
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if not key or key in os.environ:
            continue
        os.environ[key] = value
        loaded += 1
    return loaded
