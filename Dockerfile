FROM python:3.10.21-alpine3.24
WORKDIR /app
COPY . .
CMD ["python", "app.py"]