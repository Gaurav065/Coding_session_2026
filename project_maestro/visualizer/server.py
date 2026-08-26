import sys, json, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, r'C:/Coding')
from project_maestro.visualizer.runner import run_live_match

class VisualizerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/index.html', '/app.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('project_maestro/visualizer/index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif parsed.path == '/match_visualizer.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            with open('project_maestro/visualizer/match_visualizer.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/run_match':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            params = json.loads(body) if body else {}
            seed = int(params.get('seed', 42))
            opp = params.get('opponent', 'meta_calibrated')

            res = run_live_match(seed=seed, opp_type=opp)
            data = json.dumps(res).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, VisualizerHandler)
    print(f'Visualizer server live on http://localhost:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server(8080)