FROM python:3.10.21-alpine3.24
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "app.py"]