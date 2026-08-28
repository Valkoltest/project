from http.server import BaseHTTPRequestHandler, HTTPServer

file = open("static/index.html", "r")
html = file.read()
file.close()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        self.wfile.write(html.encode())

    def do_POST(self):
        # content_length = int(self.headers["Content-Length"])
        # post_data = self.rfile.read(content_length)
        # print(post_data.decode())

        # self.send_response(200)
        # self.end_headers()
        # self.wfile.write(b"Data received")

        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        
        self.wfile.write(b"Ok")

server=HTTPServer(("0.0.0.0", 8080), Handler)
server.serve_forever()