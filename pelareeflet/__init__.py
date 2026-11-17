"""PelaReeflet —— 可嵌入的人机验证组件（来源可得许可，见 LICENSE）。"""
from __future__ import annotations

import os

from flask import Flask, jsonify, redirect

from .config import ReefletConfig
from .core import Reeflet
from .routes import attach_cors, bp, register_embed

__version__ = "1.0.0"
__all__ = ["create_app", "Reeflet", "ReefletConfig"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def create_app(cfg: ReefletConfig | None = None) -> Flask:
    cfg = cfg or ReefletConfig.from_env()

    if not cfg.configured:
        import sys
        print(
            "[PelaReeflet] 未配置 REEFLET_SECRET（或长度不足 16 位），将拒绝签发挑战。\n"
            "   生成密钥: python -c \"import secrets;print(secrets.token_hex(32))\"\n"
            "   写入 .env: REEFLET_SECRET=<生成的串>\n",
            file=sys.stderr,
        )

    app = Flask(
        __name__,
        static_folder=os.path.join(_ROOT, "static"),
        static_url_path="/static",
        template_folder=os.path.join(_ROOT, "templates"),
    )
    app.extensions["reeflet"] = Reeflet(cfg)
    app.config["REEFLET"] = cfg

    app.register_blueprint(bp)
    attach_cors(app)
    register_embed(app, os.path.join(_ROOT, "static", "widget", "pelareeflet.js"))

    @app.get("/")
    def index():
        return redirect("/demo")

    @app.get("/demo")
    def demo():
        from flask import render_template
        return render_template("demo.html", cfg=app.extensions["reeflet"].client_config())

    @app.get("/healthz")
    def healthz():
        rl = app.extensions["reeflet"]
        return jsonify({
            "ok": True,
            "version": __version__,
            "configured": rl.cfg.configured,
            "difficulty": rl.cfg.difficulty,
            "prefix": rl.cfg.prefix,
            "last": rl.store.last_result,
        })

    @app.post("/demo/verify")
    def demo_verify():
        """演示用的「业务后端」：拿 ticket 走一遍 siteverify。"""
        from flask import request
        body = request.get_json(silent=True) or {}
        rl = app.extensions["reeflet"]
        ok, reason, _payload = rl.siteverify(str(body.get("ticket") or ""), sitekey=cfg.sitekey)
        return jsonify({"success": ok, "reason": reason})

    return app
