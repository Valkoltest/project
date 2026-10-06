FROM python:3.10.21-alpine3.24
WORKDIR /app

RUN apk add --no-cache postgresql18-client

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/images /logs /backups

CMD ["python", "-u", "app.py"]