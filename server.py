from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

try:
    import psycopg2  # type: ignore
except (ModuleNotFoundError, ImportError):
    psycopg2 = None  # type: ignore

# Server settings
SERVER_IP = "0.0.0.0"
SERVER_PORT = int(os.environ.get("PORT", "8080"))
LOG_FILE = "RECEIVED_data.txt"
DB_TABLE = "received_data"


def get_db_url():
    return os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")


def ensure_db_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DB_TABLE} (
                id SERIAL PRIMARY KEY,
                timestamp TEXT NOT NULL,
                payload JSONB NOT NULL
            );
            """
        )
    conn.commit()


def write_payload_to_db(payload):
    db_url = get_db_url()
    if not db_url:
        logging.warning("DATABASE_URL/POSTGRES_URL is not configured")
        return False
    if psycopg2 is None:
        logging.warning("psycopg2 is not installed; payload was not saved to Postgres")
        return False

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        ensure_db_table(conn)
        timestamp = datetime.now(timezone.utc).isoformat()
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {DB_TABLE} (timestamp, payload) VALUES (%s, %s)",
                (timestamp, json.dumps(payload)),
            )
        conn.commit()
        return True
    except Exception:
        logging.exception("Failed to save payload to Postgres")
        return False
    finally:
        if conn is not None:
            conn.close()


def read_recent_logs_from_db():
    db_url = get_db_url()
    if not db_url or psycopg2 is None:
        return None

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        ensure_db_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT timestamp, payload FROM {DB_TABLE} ORDER BY id DESC LIMIT 50"
            )
            rows = cur.fetchall()
        if not rows:
            return []
        return [
            f"{timestamp} | {json.dumps(payload, ensure_ascii=False)}"
            for timestamp, payload in reversed(rows)
        ]
    except Exception:
        logging.exception("Failed to read logs from Postgres")
        return None
    finally:
        if conn is not None:
            conn.close()


# Server loop
def server_loop():
    class RequestHandler(BaseHTTPRequestHandler):
        def _get_path(self):
            return urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

        def _get_valid_key(self):
            return os.environ.get("VIEW_KEY") or os.environ.get("SECRET_KEY")

        def do_GET(self):
            parsed_path = urllib.parse.urlparse(self.path)
            path = self._get_path()
            query_params = urllib.parse.parse_qs(parsed_path.query)
            secret_key = self._get_valid_key()

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

                if not secret_key or provided_key != secret_key:
                    body = b"403 Forbidden: Invalid or missing secret key."
                    self.send_response(403)
                    self.send_header("Content-type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                try:
                    db_lines = read_recent_logs_from_db()
                    if db_lines is not None:
                        recent_lines = db_lines
                        source = "database"
                    else:
                        with open(LOG_FILE, "r", encoding="utf-8") as log_file:
                            lines = log_file.readlines()
                        recent_lines = lines[-50:]
                        source = "file"

                    output = "TIMESTAMP | PAYLOAD\n" + "=" * 60 + "\n"
                    if recent_lines:
                        for line in recent_lines:
                            output += line.rstrip("\n") + "\n"
                    else:
                        output += f"No log entries found in {source}.\n"

                    body = output.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except FileNotFoundError:
                    body = b"TIMESTAMP | PAYLOAD\n============================================================\nNo log entries found in file.\n"
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain; charset=utf-8")
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
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path.rstrip("/") or "/"

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
            elif path == '/view-db-logs':
                query_params = urllib.parse.parse_qs(parsed_path.query)
                provided_key = query_params.get('key', [None])[0]
                secret_key = self._get_valid_key()
                status = 200 if secret_key and provided_key == secret_key else 403
                self.send_response(status)
                self.send_header("Content-type", "text/plain; charset=utf-8")
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

                db_saved = write_payload_to_db(parsed_data)
                if db_saved:
                    logging.info("Payload saved to Postgres database")
                else:
                    logging.warning("Payload written to file only; DB save unavailable or failed")

                logging.info("Received POST payload from %s: %s", self.client_address[0], parsed_data)

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
                logging.exception("Unexpected error while processing POST from %s", self.client_address[0])
                body = b"Internal Server Error"
                self.send_response(500)
                self.send_header("Content-type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    httpd = ThreadingHTTPServer((SERVER_IP, SERVER_PORT), RequestHandler)
    logging.info("Server running on %s:%s", SERVER_IP, SERVER_PORT)
    httpd.serve_forever()

# Start the server
if __name__ == "__main__":
    try:
        logging.info("Server started. Ready to receive data.")
        server_loop()
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")