#!/usr/bin/env python3
"""Serve the animation preview and the asset submodule on loopback."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'vendor/wuwa-tappo-assets'


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        route = unquote(urlsplit(path).path)
        choices = {'/preview/': ROOT / 'preview', '/src/': ROOT / 'src',
                   '/asset-library/data/': ASSETS / 'data',
                   '/asset-library/assets/': ASSETS / 'assets'}
        if route == '/':
            return str(ROOT / 'preview' / 'index.html')
        for prefix, base in choices.items():
            if route.startswith(prefix):
                target = (base / route[len(prefix):]).resolve()
                if target.is_relative_to(base.resolve()):
                    return str(target)
        return str(ROOT / 'preview' / '__not_found__')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=4173)
    args = parser.parse_args()
    if not (ASSETS / 'data/catalog.json').is_file():
        parser.error('缺少素材子模块，请在项目根目录运行 git submodule update --init --recursive')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'动画预览：http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
