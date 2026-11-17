"""PelaReeflet 自检脚本。

没有 pytest 也能跑：
    python tests/test_flow.py

装了 pytest 的话：
    pytest -q tests
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pelareeflet import create_app                      # noqa: E402
from pelareeflet.config import ReefletConfig            # noqa: E402

SECRET = "test-secret-0123456789abcdef"
SITEKEY = "k-test"


def make_app(**overrides):
    params = dict(secret=SECRET, sitekey=SITEKEY, difficulty=2000, click_gate=True)
    params.update(overrides)
    cfg = ReefletConfig(**params)
    app = create_app(cfg)
    app.config["TESTING"] = True
    return app


def solve(challenge, prefix):
    zeros = "0" * prefix
    nonce = 0
    while True:
        if hashlib.sha256(f"{challenge}:{nonce}".encode()).hexdigest().startswith(zeros):
            return nonce
        nonce += 1


def mouse_path():
    """一条像人手的轨迹：有抖动、有变速。"""
    pts = []
    t = 0
    for i in range(30):
        t += 12 + (i % 5)
        pts.append([100 + i * 3, 200 + (i % 3) - 1, t])
    return pts


def test_challenge_shape():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.1"
    r = c.post("/api/v1/challenge")
    assert r.status_code == 200, r.data
    d = r.get_json()
    assert d["ok"] and len(d["challenge"]) == 64
    assert d["prefix"] == 3
    assert d["token"].count(".") == 1


def test_full_flow_and_replay():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.2"

    job = c.post("/api/v1/challenge").get_json()

    r = c.post("/api/v1/check", json={
        "token": job["token"], "path": mouse_path(),
        "pointer_type": "mouse", "hold_ms": 120,
        "features": {"webdriver": False},
    })
    assert r.status_code == 200, r.data
    gate = r.get_json()["gate"]

    nonce = solve(job["challenge"], job["prefix"])
    r = c.post("/api/v1/solve", json={
        "token": job["token"], "nonce": nonce, "gate": gate
    })
    assert r.status_code == 200, r.data
    ticket = r.get_json()["ticket"]

    r = c.post("/api/v1/siteverify", json={"secret": SECRET, "response": ticket})
    body = r.get_json()
    assert body["success"] is True, body

    # 一次性：同一张票不能再用
    r = c.post("/api/v1/siteverify", json={"secret": SECRET, "response": ticket})
    assert r.get_json()["success"] is False
    assert r.get_json()["error-codes"] == ["replayed"]

    # 同一张挑战票也不能再算一次
    r = c.post("/api/v1/solve", json={
        "token": job["token"], "nonce": nonce, "gate": gate
    })
    assert r.status_code == 403
    assert r.get_json()["reason"] == "replayed"


def test_wrong_nonce_rejected():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.3"

    job = c.post("/api/v1/challenge").get_json()
    gate = c.post("/api/v1/check", json={
        "token": job["token"], "path": mouse_path(),
        "pointer_type": "mouse", "hold_ms": 120,
        "features": {},
    }).get_json()["gate"]

    r = c.post("/api/v1/solve", json={
        "token": job["token"], "nonce": 0, "gate": gate
    })
    assert r.status_code == 403
    assert r.get_json()["reason"] == "wrong"


def test_solve_requires_gate():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.4"

    job = c.post("/api/v1/challenge").get_json()
    nonce = solve(job["challenge"], job["prefix"])
    r = c.post("/api/v1/solve", json={"token": job["token"], "nonce": nonce})
    assert r.status_code == 400, r.status_code
    assert r.get_json()["reason"] == "need_gate"


def test_automation_rejected():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.5"

    job = c.post("/api/v1/challenge").get_json()
    r = c.post("/api/v1/check", json={
        "token": job["token"], "path": mouse_path(),
        "pointer_type": "mouse", "hold_ms": 120,
        "features": {"webdriver": True},
    })
    assert r.status_code == 403
    assert r.get_json()["reason"] == "automation"


def test_automation_score_blocks_fake_env():
    """有 Chrome 的 UA 却没有 window.chrome、环境全空 → 判自动化。"""
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.11"

    job = c.post("/api/v1/challenge").get_json()
    r = c.post("/api/v1/check", json={
        "token": job["token"], "path": mouse_path(),
        "pointer_type": "mouse", "hold_ms": 150,
        "features": {
            "ua": "Mozilla/5.0 Chrome/120.0 Safari/537.36",
            "chrome": False, "plugins": 0, "languages": 0,
            "hardware": 0, "depth": 0, "webdriver": False,
        },
    })
    assert r.status_code == 403
    assert r.get_json()["reason"] == "automation"


def test_track_metrics_scores_scripted_path():
    from pelareeflet.core import _track_metrics

    # 完美水平、等间隔、零回退 —— 脚本特征
    fake = [[i * 2, 300, i * 16] for i in range(40)]
    m = _track_metrics(fake)
    assert m["y_range"] == 0
    assert m["dt_unique"] <= 2
    assert m["score"] >= 3, m

    # 有抖动、有回退、间隔不均 —— 像人
    human = []
    for i in range(40):
        human.append([100 + i * 2 + (i % 4) - 2, 300 + ((i * 7) % 5) - 2, i * 17 + (i % 3)])
    human.insert(20, [human[19][0] - 6, human[19][1] + 1, human[19][2] + 9])
    m2 = _track_metrics(human)
    assert m2["score"] < 4, m2


def test_siteverify_secret_and_sitekey():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.6"

    r = c.post("/api/v1/siteverify", json={"secret": "wrong", "response": "x"})
    assert r.get_json()["error-codes"] == ["invalid-input-secret"]

    r = c.post("/api/v1/siteverify", json={"secret": SECRET, "response": "not-a-ticket"})
    assert r.get_json()["error-codes"] == ["invalid"]


def test_rate_limit():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.7"
    codes = [c.post("/api/v1/challenge").status_code for _ in range(3)]
    assert 429 in codes, codes


def test_unconfigured_service():
    app = make_app(secret="")
    c = app.test_client()
    r = c.post("/api/v1/challenge")
    assert r.status_code == 503
    assert r.get_json()["reason"] == "unavailable"


def test_widget_and_demo_served():
    app = make_app()
    c = app.test_client()
    r = c.get("/embed/pelareeflet.js")
    assert r.status_code == 200
    assert b"PelaReeflet" in r.data
    r = c.get("/demo")
    assert r.status_code == 200
    assert "pelareeflet".encode() in r.data
    cfg = c.get("/api/v1/config").get_json()
    assert cfg["brand"] == "PELAGIC BEACON", cfg["brand"]
    assert cfg["theme"] == "dark"
    assert cfg["attribution"] is True
    assert cfg["links"]["license"].endswith("/PelaReeflet/blob/main/LICENSE")
    assert "github.com/orgs/PelagicBeacon" in cfg["links"]["about"]


def test_cors_header():
    app = make_app()
    c = app.test_client()
    c.environ_base["REMOTE_ADDR"] = "10.0.0.8"
    r = c.post("/api/v1/challenge", headers={"Origin": "https://example.com"})
    assert r.headers.get("Access-Control-Allow-Origin") in ("*", "https://example.com")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ERR   {name}: {type(exc).__name__}: {exc}")
    print()
    print("全部通过" if not failures else f"{failures} 项失败")
    sys.exit(1 if failures else 0)
