from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid
import re
import os
import mimetypes
import logging
from html import escape
import psycopg
from psycopg import Connection
import time


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


def images_page(temp_list):
    image_dir = "images"
    files = []

    if os.path.isdir(image_dir):
        files = sorted(
            f for f in os.listdir(image_dir)
            if os.path.isfile(os.path.join(image_dir, f))
        )

    items = "\n".join(
        f'''
            <tr>
                <td>{item[1]}</td>
                <td>{item[2]}</td>
                <td>{item[3]/1024:.2f}</td>
                <td>{item[4]}</td>
                <td>{item[5]}</td>
                <td><a href="/images/{item[1]}">\U0001F4C2</a></td>
                <td><a href="/delete-image/{item[0]}">\U0001F5D1</a></td>
            </tr>         
        '''
        for item in temp_list
    )

    if not items:
        items = 'Поки що немає зображень. Завантажте зображення на головній сторінці.'

    return images_template.replace("{items}", items)


def index_page(message=""):
    return html.replace("{message}", message)


def insert_image_metadata(connection: Connection, filename: str, original_name:str,size: int,file_type:str):
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO images (filename, original_name, size, file_type) VALUES (%s, %s, %s, %s) RETURNING id;",
            [filename, original_name, size, file_type]
        )
        connection.commit()
        return cursor.fetchone()[0]


def get_images_metadata(connection: Connection, page: int=1):
    offset = 10 * (page - 1)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM images OFFSET %s LIMIT 10;",
            [offset]
        )
        return cursor.fetchall()


def delete_image_metadata(connection: Connection, id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM images WHERE id = %s;",
            [id]
        )
        connection.commit()


log_directory = os.environ.get("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = logging.FileHandler(os.path.join(log_directory, "app.log"),encoding="utf-8")
log_file.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S",))
logging.basicConfig(level=logging.INFO, handlers=[log_file])
logger = logging.getLogger()


with open("static/index.html", "r", encoding="utf-8") as f:
    html = f.read()


with open("static/images-list.html", "r", encoding="utf-8") as f:
    images_template = f.read()


connection = None
while connection is None:
    try:
        connection = psycopg.connect(
            "postgresql://images_backend:1048575@db:5432/images_hosting"
        )
        logger.info("Підключення до бази даних встановлено.")
    except Exception as e:
        logger.error(f"Помилка: не вдалося підключитися до бази даних. {e}")
        time.sleep(1)  # Затримка перед повторною спробою


with connection.cursor() as cursor:
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS images (
            id SERIAL PRIMARY KEY,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            size INTEGER NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_type TEXT NOT NULL
        );
        '''
    )
    connection.commit()
    logger.info("Таблиця 'images' створена або вже існує.")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path        
        logger.info(f"Перегляд сторінки ({path}).")

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(index_page().encode())
            return

        if path == "/images-list" or path == "/images-list/":
            temp_list = get_images_metadata(connection)
            logger.info(f"Отримано метадані зображень: {temp_list}.")
            page = images_page(temp_list).encode()
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

        path = f"/images/{filename}"

        extensions = ["jpg", "png", "gif"]
        extension = upload_name.split(".")[-1]
        extension = extension.lower()

        if extension not in extensions:
            logger.error(f"Помилка: непідтримуваний формат файлу ({upload_name}).")
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            message = (
                '<p class="upload-result error">'
                f"Помилка: непідтримуваний формат файлу ({escape(upload_name)})."
                "</p>"
            )
            self.wfile.write(index_page(message).encode())
            return  

        file_size = len(data)

        if file_size > 5 * 1024 * 1024:
            logger.error(f"Помилка: файл ({upload_name}) не завантажено: розмір ({file_size}) байт перевищує ліміт.")
            self.send_response(400)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            message = (
                '<p class="upload-result error">'
                f"Помилка: файл ({escape(upload_name)}) не завантажено: "
                f"розмір ({file_size}) байт перевищує ліміт."
                "</p>"
            )
            self.wfile.write(index_page(message).encode())
            return      

        f = open(path, "wb")
        f.write(data)
        f.close()
        logger.info(f"Зображення ({upload_name}) завантажено.")

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        message = (
            '<p class="upload-result success">'
            f"Успіх: зображення ({escape(upload_name)}) завантажено."
            "</p>"
        )
        self.wfile.write(index_page(message).encode())
        try:
            inserted_id = insert_image_metadata(
                connection, 
                filename, 
                upload_name,
                file_size,
                extension
            )
            logger.info(f"Метадані зображення ({upload_name}) вставлено в базу даних з ID {inserted_id}.")
        except Exception as e:
            logger.error(f"Помилка: не вдалося вставити метадані зображення ({upload_name}) в базу даних. {e}")

server=HTTPServer(("0.0.0.0", 8080), Handler)
server.serve_forever()