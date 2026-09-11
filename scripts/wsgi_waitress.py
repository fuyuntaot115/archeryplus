# -*- coding: UTF-8 -*-
# Windows 部署用 waitress WSGI 启动脚本（gunicorn 不支持 Windows）
# 用法: python scripts/wsgi_waitress.py [端口]
#
# 说明：waitress 直接跑 WSGI 时没有人负责静态文件（Docker 部署里由 nginx 负责），
#       DEBUG=False 下 /static/ 会返回登录页 HTML，导致页面样式与脚本全部加载失败。
#       这里在 WSGI 层补上 /static/（以及配置了 MEDIA_URL 时的 /media/）。
import mimetypes
import os
import sys
from email.utils import formatdate

# 以脚本方式直接运行时 sys.path[0] 是 scripts/ 目录，
# 需要把项目根目录加进来，否则 import archery 会失败。
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "archery.settings")

import django

django.setup()

from waitress import serve  # noqa: E402

from django.conf import settings  # noqa: E402
from django.core.exceptions import SuspiciousFileOperation  # noqa: E402
from django.utils._os import safe_join  # noqa: E402

from archery.wsgi import application  # noqa: E402

for _suffix, _type in (
    ("woff2", "font/woff2"),
    ("woff", "font/woff"),
    ("ttf", "font/ttf"),
    ("js", "application/javascript"),
    ("mjs", "application/javascript"),
    ("css", "text/css"),
    ("map", "application/json"),
):
    mimetypes.add_type(_type, "." + _suffix)


class StaticFilesMiddleware:
    """
    在 WSGI 层直接从 STATIC_ROOT 提供静态文件。

    本地 waitress 部署没有 nginx，而 DEBUG=False 时 /static/ 与静态文件的
    hash 文件名都只能从 STATIC_ROOT 取（Django 的 finders 只查源码目录），
    所以这里自己处理；文件不存在时原样交回 Django 应用。
    """

    def __init__(self, application, url_prefix, document_root):
        self.application = application
        self.url_prefix = url_prefix
        self.document_root = document_root

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if not path.startswith(self.url_prefix):
            return self.application(environ, start_response)
        relative = path[len(self.url_prefix):].lstrip("/")
        try:
            full_path = safe_join(self.document_root, relative)
        except (SuspiciousFileOperation, ValueError):
            return self.application(environ, start_response)
        if not relative or not os.path.isfile(full_path):
            return self.application(environ, start_response)
        return self._serve_file(full_path, start_response)

    @staticmethod
    def _serve_file(full_path, start_response):
        stat = os.stat(full_path)
        content_type = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
        start_response(
            "200 OK",
            [
                ("Content-Type", content_type),
                ("Content-Length", str(stat.st_size)),
                ("Last-Modified", formatdate(stat.st_mtime, usegmt=True)),
            ],
        )
        with open(full_path, "rb") as file_obj:
            return [file_obj.read()]


def build_application():
    static_url = settings.STATIC_URL or ""
    if static_url and settings.STATIC_ROOT:
        print(f"静态文件由 waitress 提供: {static_url} -> {settings.STATIC_ROOT}")
        return StaticFilesMiddleware(application, static_url, str(settings.STATIC_ROOT))
    return application


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    print(f"waitress 启动于 http://0.0.0.0:{port} (Ctrl+C 停止)")
    serve(build_application(), host="0.0.0.0", port=port, threads=8, channel_timeout=600)


if __name__ == "__main__":
    main()
