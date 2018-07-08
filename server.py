#!/usr/bin/env python

from http.server import SimpleHTTPRequestHandler, HTTPServer

server_address = ('', 8000)
httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)

httpd.serve_forever()
