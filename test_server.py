# test_server.py — положите в корень konckorm_analytics/
from http.server import HTTPServer, SimpleHTTPRequestHandler

print("Тест: открывайте http://127.0.0.1:8888")
HTTPServer(("127.0.0.1", 8888), SimpleHTTPRequestHandler).serve_forever()