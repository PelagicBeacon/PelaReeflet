"""PelaReeflet HTTP 接口。

接口一览（全部返回 JSON）
-------------------------
GET  /api/v1/config      组件渲染所需的公开配置（无任何秘密）
POST /api/v1/challenge   签发挑战
POST /api/v1/check       交互关卡（点击 + 行为）
POST /api/v1/solve       提交 PoW 答案，换取通行票
POST /api/v1/siteverify  业务后端验证通行票（对应 Turnstile 的 siteverify）
GET  /embed/pelareeflet.js  可嵌入的组件脚本
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from .core import Reeflet, failure_message

bp = Blueprint("reeflet_api", __name__, url_prefix="/api/v1")


def reeflet() -> Reeflet:
    return current_app.extensions["reeflet"]


def remote_ip() -> str:
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    return fwd or (request.remote_addr or "")


def _fail(reason: str, status: int = 400):
    return jsonify({"ok": False, "reason": reason, "message": failure_message(reason)}), status


@bp.get("/config")
def config():
    return jsonify({"ok": True, **reeflet().client_config()})


@bp.route("/challenge", methods=["GET", "POST"])
def challenge():
    data, reason = reeflet().issue_challenge(remote_ip())
    if reason == "rate_limited":
        return _fail(reason, 429)
    if not data:
        return _fail("unavailable", 503)
    return jsonify({"ok": True, **data})


@bp.post("/check")
def check():
    body = request.get_json(silent=True) or {}
    ok, reason, gate, score = reeflet().check_interaction(
        body.get("token"),
        body.get("path"),
        body.get("pointer_type"),
        body.get("hold_ms"),
        body.get("features"),
        remote_ip(),
    )
    if not ok:
        return _fail(reason, 503 if reason == "unavailable" else 403)
    return jsonify({"ok": True, "gate": gate, "score": score})


@bp.post("/solve")
def solve():
    body = request.get_json(silent=True) or {}
    ok, reason, ticket = reeflet().solve(
        body.get("token"), body.get("nonce"), remote_ip(), gate=body.get("gate")
    )
    if ok:
        return jsonify({
            "ok": True,
            "ticket": ticket,
            "ttl": reeflet().cfg.ticket_ttl,
        })
    status = 403 if reason in ("wrong", "replayed", "bad_ip", "interaction", "automation") else 400
    if reason == "unavailable":
        status = 503
    return _fail(reason, status)


@bp.post("/siteverify")
def siteverify():
    """业务后端调用：拿通行票换验证结论。

    请求体（JSON 或表单均可）：
        secret   站点私钥（与 REEFLET_SECRET 一致）
        response 组件回调里拿到的 ticket
        remoteip 可选，传了就要求票与 IP 绑定一致
    """
    body = request.get_json(silent=True) or request.form or {}
    secret = str(body.get("secret") or "")
    if not secret:
        return jsonify({"success": False, "error-codes": ["missing-input-secret"]}), 200

    cfg = reeflet().cfg
    if secret != cfg.secret:
        return jsonify({"success": False, "error-codes": ["invalid-input-secret"]}), 200

    ok, reason, payload = reeflet().siteverify(
        str(body.get("response") or ""),
        ip=body.get("remoteip") or None,
        bind_ip=bool(body.get("remoteip")),
        sitekey=body.get("sitekey") or None,
    )
    if not ok:
        return jsonify({"success": False, "error-codes": [reason]}), 200

    return jsonify({
        "success": True,
        "challenge_ts": payload.get("iat"),
        "hostname": cfg.hostname or request.host,
        "sitekey": payload.get("sk"),
    }), 200


def register_embed(app, script_path: str) -> None:
    """把组件脚本挂到 /embed/pelareeflet.js。"""
    from flask import send_file

    @app.get("/embed/pelareeflet.js")
    def _embed_script():
        return send_file(script_path, mimetype="application/javascript")


def attach_cors(app) -> None:
    @app.after_request
    def _cors(resp):
        cfg = app.extensions["reeflet"].cfg
        origin = request.headers.get("Origin") or ""
        allowed = cfg.allowed_origins
        if "*" in allowed:
            resp.headers.setdefault("Access-Control-Allow-Origin", "*")
        elif origin and origin in allowed:
            resp.headers.setdefault("Access-Control-Allow-Origin", origin)
            resp.headers.setdefault("Vary", "Origin")
        resp.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
        resp.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    @app.route("/api/v1/<path:_any>", methods=["OPTIONS"])
    def _preflight(_any):  # pragma: no cover - 由浏览器触发
        return ("", 204)
