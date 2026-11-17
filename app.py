"""开发入口：python app.py

生产部署用 gunicorn / waitress 调用 create_app()，例如：
    gunicorn -w 1 -b 0.0.0.0:8080 "app:app"
说明：状态在进程内存里，**多 worker 会各自记账**，生产建议 -w 1，
或把 pelareeflet/store.py 换成 Redis 实现。
"""
from pelareeflet import create_app

app = create_app()

if __name__ == "__main__":
    import os

    app.run(
        host=os.getenv("REEFLET_HOST", "127.0.0.1"),
        port=int(os.getenv("REEFLET_PORT", "8080")),
        debug=os.getenv("REEFLET_DEBUG") == "1",
    )
