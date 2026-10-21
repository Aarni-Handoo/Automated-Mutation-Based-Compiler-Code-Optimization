"""Local-only dependency-free dashboard server. Run: python app.py"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlparse
import uuid
from core import parse, InputError
from engine import optimize, OPERATORS, DEFAULT_OPS
from benchmark import run_benchmark

ROOT = Path(__file__).resolve().parent
JOBS = {}
WORK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, kind='application/json'):
        raw = json.dumps(data).encode() if kind == 'application/json' else data
        self.send_response(code)
        self.send_header('Content-Type', kind + '; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/api/operators':
            self.send(200, [
                {
                    'id': k,
                    'name': v[0],
                    'description': v[1],
                    'default': k in DEFAULT_OPS
                }
                for k, v in OPERATORS.items()
            ])

        elif path.startswith('/api/job/'):
            job = JOBS.get(path.rsplit('/', 1)[1])
            self.send(
                200 if job else 404,
                job or {'error': 'Unknown job'}
            )

        else:
            routes = {
                '/': ('welcome.html', 'text/html'),
                '/dashboard': ('index.html', 'text/html'),
                '/welcome.css': ('welcome.css', 'text/css'),
                '/welcome.js': ('welcome.js', 'text/javascript'),
                '/app.js': ('app.js', 'text/javascript'),
                '/style.css': ('style.css', 'text/css')
            }

            if path in routes:
                filename, mime = routes[path]
                file_path = ROOT / 'static' / filename

                if file_path.is_file():
                    self.send(200, file_path.read_bytes(), mime)
                else:
                    self.send(404, {'error': f'{filename} not found'})
            else:
                self.send(404, {'error': 'Not found'})
    def do_POST(self):
        origin = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        if origin and origin != 'http://' + host:
            self.send(403, {'error': 'Only same-origin requests are accepted.'}); return
        acquired = False
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 50000: raise InputError('Request must be between 1 and 50,000 bytes.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict): raise InputError('Expected a JSON object.')
            acquired = WORK.acquire(blocking=False)
            if not acquired: self.send(409, {'error': 'A calculation is already running. Wait for it to finish.'}); return
            if self.path == '/api/optimize':
                p = parse(data.get('source', ''), data.get('mode', 'python'), data.get('outputs'))
                result = optimize(p, **{k: data[k] for k in ('rounds', 'budget', 'beam_width', 'enabled', 'seed', 'runtime_weight') if k in data})
                self.send(200, result)
            elif self.path == '/api/benchmark':
                count = int(data.get('programs', 200))
                if not 200 <= count <= 500: raise InputError('Choose 200–500 programs.')
                # Bound stored results for this local server.
                for old in list(JOBS):
                    if JOBS[old]['status'] != 'running': del JOBS[old]
                job_id = uuid.uuid4().hex
                JOBS[job_id] = {'status': 'running', 'done': 0, 'total': count}
                def worker():
                    try:
                        result = run_benchmark(count, lambda done, total: JOBS[job_id].update(done=done))
                        JOBS[job_id].update(status='complete', result=result)
                    except Exception as e: JOBS[job_id].update(status='error', error=str(e))
                    finally: WORK.release()
                threading.Thread(target=worker, daemon=True).start()
                acquired = False
                self.send(202, {'job': job_id})
            else: self.send(404, {'error': 'Not found'})
        except (ValueError, TypeError, KeyError, RecursionError) as error:
            self.send(400, {'error': str(error)})
        except Exception:
            self.send(500, {'error': 'Unexpected backend error. Check the terminal.'})
            import traceback
            traceback.print_exc()
        finally:
            if acquired: WORK.release()
    def log_message(self, *_): pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Open http://127.0.0.1:{args.port} in your browser. Press Ctrl+C to stop.', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
