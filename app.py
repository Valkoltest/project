from http.server import BaseHTTPRequestHandler, HTTPServer
#from xml.sax import handler
import uuid
import re
import os
import mimetypes
from urllib.parse import urlparse

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

def render_images_page():
    image_dir = "images"
    files = []

    if os.path.isdir(image_dir):
        files = sorted(
            f for f in os.listdir(image_dir)
            if os.path.isfile(os.path.join(image_dir, f))
        )

    items = "\n".join(
        f'<li class="file-item"><a href="/images/{name}">{name}</a></li>'
        for name in files
    )

    if not items:
        items = '<li class="empty">Поки що немає зображень.</li>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Images</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <div class="files-container">
            <h1>Images</h1>
            <a class="back-link" href="http://localhost:8000/">Back to upload</a>
            <ul class="file-list">
                {items}
            </ul>
        </div>
    </body>
    </html>
    """.strip()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
            return

        if path == "/images" or path == "/images/":
            page = render_images_page().encode()
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(page)
            return

        if path.startswith("/static/"):
            relative_path = path[len("/static/"):]
            file_path = os.path.join("static", relative_path)

            if os.path.isfile(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.end_headers()

                with open(file_path, "rb") as file:
                    self.wfile.write(file.read())
                return

        if path.startswith("/images/"):
            relative_path = path[len("/images/"):]
            file_path = os.path.join("images", relative_path)

            if os.path.isfile(file_path):
                content_type, _ = mimetypes.guess_type(file_path)
                if content_type is None:
                    content_type = "application/octet-stream"

                self.send_response(200)
                self.send_header("Content-type", content_type)
                self.end_headers()

                with open(file_path, "rb") as file:
                    self.wfile.write(file.read())
                return

        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self):
        data, upload_name = extract_file_data(self)

        filename = uuid.uuid4().hex + "." + upload_name.split(".")[-1]

        path = f"images/{filename}"

        extensions = ["jpg", "png", "gif"]
        extension = upload_name.split(".")[-1]
        extension = extension.lower()

        if extension not in extensions:
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Invalid file extension: *.{extension}".encode())
            return        

        f = open(path, "wb")
        f.write(data)
        f.close()

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        
        self.wfile.write(f"http://localhost:8000/{path}".encode())

server=HTTPServer(("0.0.0.0", 8000), Handler)
server.serve_forever()