"""Serve only the built site on this computer; no input or local folders exposed."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=8800, help='Use 0 to select an available port')
parser.add_argument('--open', action='store_true', help='Open the local page in your default browser')
a = parser.parse_args()
dist = Path(__file__).resolve().parents[1] / 'dist'
if not (dist / 'index.html').exists():
    parser.exit(2, 'Run python tools/build_site.py first.\n')
handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
try:
    server = ThreadingHTTPServer(('127.0.0.1', a.port), handler)
except OSError as exc:
    parser.exit(2, f'Cannot start local preview: {exc}\nTry --port 0 for an available port.\n')
with server:
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Local: {url}\nKeep this window open while using the viewer. Press Ctrl+C to stop.', flush=True)
    if a.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
