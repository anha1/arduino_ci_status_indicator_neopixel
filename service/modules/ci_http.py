import http.server
import socketserver
from http.server import BaseHTTPRequestHandler
import logging
import pystache
import threading

class CiHttpServer:
    def __init__(self, config):
        self.status = {}
        self.config = config

    def set_status(self, status):
        self.status = status    
        
    def start(self):
        port = int(self.config['http']['port'])

        template = ''
        with open(self.config['http']['template'], 'r') as template_file:
            template = template_file.read()
            template_file.close()

        parent = self

        class GetHandler(BaseHTTPRequestHandler):

            def do_GET(self):

                message = pystache.render(template, {
                    'status': parent.status
                })

                self.send_response(200)
                self.send_header('Content-Type',
                                'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(message.encode('utf-8'))

        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(('', port), GetHandler)
        logging.info('serving at port %d' % port)
        self.thread = threading.Thread(target=server.serve_forever)
        self.thread.setDaemon(True)
        self.thread.start()
