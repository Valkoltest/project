from http.server import BaseHTTPRequestHandler, HTTPServer
#from xml.sax import handler
import uuid
import re

file = open("static/index.html", "r")
html = file.read()
file.close()

def extract_file_data(handler):
    length = int(handler.headers.get("Content-Length"))
    body = handler.rfile.read(length)
    boundary = handler.headers["Content-Type"].split("boundary=")[-1].encode()
    start = body.find(b"\r\n\r\n") + 4
    end = body.find(b"\r\n--" + boundary, start)
    data = body[start:end]

    upload_name = re.search(
        rb'filename="([^"]+)"',
        body
    ).group(1).decode()

    return data, upload_name

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        self.wfile.write(html.encode())

    def do_POST(self):
        data, upload_name = extract_file_data(self)

        filename = uuid.uuid4().hex + "." + upload_name.split(".")[-1]

        path = f"images/{filename}"

        f = open(path, "wb")
        f.write(data)
        f.close()

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        
        self.wfile.write(f"http://localhost:8000/{path}".encode())

server=HTTPServer(("0.0.0.0", 8000), Handler)
server.serve_forever()