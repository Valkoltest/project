FROM python:3.10.21-alpine3.24
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/images /logs

CMD ["python", "-u", "app.py"]