from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid
import re
import os
import mimetypes
import logging


log_directory = os.environ.get("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = logging.FileHandler(os.path.join(log_directory, "app.log"),encoding="utf-8")
log_file.setFormatter(logging.Formatter(
    "[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.basicConfig(level=logging.INFO,handlers=[log_file])
logger = logging.getLogger()



with open("static/index.html", "r", encoding="utf-8") as f:
    html = f.read()

with open("static/images.html", "r", encoding="utf-8") as f:
    images_template = f.read()

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

def images_page():
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

    return images_template.replace("{items}", items)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path        
        logger.info(f"Дія: перегляд сторінки ({path}).")

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())
            return

        if path == "/images" or path == "/images/":
            page = images_page().encode()
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
        logger.error(f"Помилка: ресурс ({path})не знайдено.")
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
            logger.error(f"Помилка: непідтримуваний формат файлу ({upload_name}).")
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Invalid file extension: *.{extension}".encode())
            return  

        file_size = len(data)

        if file_size > 5 * 1024 * 1024:
            logger.error(f"Помилка: файл ({upload_name}) не завантажено: розмір ({file_size}) байт перевищує ліміт.")
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(f"File size exceeds limit: {file_size} bytes".encode())
            return      

        f = open(path, "wb")
        f.write(data)
        f.close()
        logger.info(f"Успіх: зображення ({upload_name}) завантажено.")

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        
        self.wfile.write(f"http://localhost:8000/{path}".encode())

server=HTTPServer(("0.0.0.0", 8000), Handler)
server.serve_forever()