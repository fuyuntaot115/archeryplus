# Windows 部署用 waitress WSGI 启动脚本（gunicorn 不支持 Windows）
# 用法: python scripts/wsgi_waitress.py [端口]
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")

import django

django.setup()

from waitress import serve  # noqa: E402

from archery.wsgi import application  # noqa: E402


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    print(f"waitress 启动于 http://0.0.0.0:{port} (Ctrl+C 停止)")
    serve(application, host="0.0.0.0", port=port, threads=8, channel_timeout=600)


if __name__ == "__main__":
    main()
