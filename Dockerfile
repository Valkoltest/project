FROM python:3.10.21-alpine3.24
WORKDIR /app
COPY ./app.py ./app.py
CMD ["python3", "app.py"]