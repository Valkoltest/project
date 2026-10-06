import datetime
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
from urllib.parse import urlparse, parse_qs
import subprocess
from datetime import datetime

IMAGES_DIR = "images"
os.makedirs(IMAGES_DIR, exist_ok=True) 

BACKUP_DIR = os.environ.get("BACKUP_DIR", "/backups")

def create_backup() -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = f"backup_{datetime.now():%Y-%m-%d_%H%M%S}.sql"
    final_path = os.path.join(BACKUP_DIR, name)
    tmp_path = final_path + ".tmp"

    env = {**os.environ, "PGPASSWORD": db_pwd}
    try:
        with open(tmp_path, "wb") as f:
            subprocess.run(
                ["pg_dump", "-h", db_host, "-p", db_port, "-U", db_user, db_name],
                stdout=f, stderr=subprocess.PIPE, env=env, check=True,
            )
        os.replace(tmp_path, final_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return name


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
            "SELECT * FROM images ORDER BY id OFFSET %s LIMIT 10;",
            [offset]
        )
        return cursor.fetchall()
    

def count_images(connection: Connection) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM images;")
        return cursor.fetchone()[0]


def pagination_html(page: int, total_pages: int) -> str:
    total = count_images(connection)
    if total <= 0:
        return ""

    parts = ['<nav class="pagination">']

    for p in range(1, total_pages + 1):
        if p == page:
            parts.append(f'<span class="current">{p}</span>')
        else:
            parts.append(f'<a href="/images-list?page={p}">{p}</a>')

    parts.append("</nav>")
    return " ".join(parts)


def images_page(temp_list, page=1, total_pages=1):
    items = "\n".join(
        f'''
            <tr>
                <td>{item[1]}</td>
                <td>{escape(item[2])}</td>
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

    result = images_template.replace("{items}", items)
    return result.replace("{pagination}", pagination_html(page, total_pages))


def delete_image_metadata(connection: Connection, id: int):
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM images WHERE id = %s RETURNING filename;",
            [id]
        )
        row = cursor.fetchone()
        connection.commit()
        return row[0] if row else None


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
db_pwd = os.environ['POSTGRES_PASSWORD']
db_name = os.environ['POSTGRES_DB']
db_user = os.environ['POSTGRES_USER']
db_port = os.environ['DB_PORT']
db_host = os.environ['DB_HOST']
while connection is None:
    try:
        connection = psycopg.connect(
            #f"postgresql://{db_user}:{db_pwd}@{db_host}:{db_port}/{db_name}"
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_pwd,
        )
        logger.info("Підключення до бази даних встановлено.")
    except Exception as e:
        logger.error(f"Помилка: не вдалося підключитися до бази даних. {e}")
        time.sleep(1)


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
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        logger.info(f"Перегляд сторінки ({self.path}).")

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(index_page().encode())
            return

        if path == "/images-list" or path == "/images-list/":
            try:
                page = int(query.get("page", ["1"])[0])
            except ValueError:
                page = 1

            total = count_images(connection)
            total_pages = max(1, -(-total // 10)) 
            page = min(max(page, 1), total_pages)  

            temp_list = get_images_metadata(connection, page)
            html_page = images_page(temp_list, page, total_pages).encode()

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_page)
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
            relative_path = os.path.basename(path[len("/images/"):])
            file_path = os.path.join(IMAGES_DIR, relative_path)
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

        if path == "/backup":
            try:
                name = create_backup()
                logger.info(f"Резервну копію створено: {name}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Помилка pg_dump: {e.stderr.decode(errors='replace')}")
            except Exception as e:
                logger.error(f"Помилка створення резервної копії: {e}")

            self.send_response(303)
            self.send_header("Location", "/images-list")
            self.end_headers()

            
            return

        if path.startswith("/delete-image/"):
            try:
                image_id = int(path.rsplit("/", 1)[-1])
                filename = delete_image_metadata(connection, image_id)

                if filename:
                    file_path = os.path.join(IMAGES_DIR, os.path.basename(filename))
                    try:
                        os.remove(file_path)
                        logger.info(f"Зображення ({filename}) видалено з диска та з бази даних (ID {image_id}).")
                    except FileNotFoundError:
                        logger.error(f"Файл ({filename}) не знайдено на диску, запис у базі даних видалено.")
                else:
                    logger.error(f"Зображення з ID {image_id} не знайдено в базі даних.")
            except Exception as e:
                connection.rollback()
                logger.error(f"Помилка видалення зображення ({path}): {e}")

            self.send_response(303)
            self.send_header("Location", "/images-list")
            self.end_headers()
            return

        self.send_response(404)
        logger.error(f"Помилка: ресурс ({path})не знайдено.")
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self):
        data, upload_name = extract_file_data(self)

        filename = uuid.uuid4().hex + "." + upload_name.split(".")[-1]      


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

        file_path = os.path.join(IMAGES_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(data)

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

server=HTTPServer(("0.0.0.0", 8000), Handler)
server.serve_forever()