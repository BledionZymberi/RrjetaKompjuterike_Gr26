import socket
import threading
import time
import os

FILES_DIR = "Files"


class UDPClient:
    def __init__(self, server_host='127.0.0.1', server_port=5678):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.socket.settimeout(5.0)
        self.is_admin = False
        self.username = "user"
        self.running = True
        self.response_time = 0

        # Krijo folderin Files nëse nuk ekziston
        if not os.path.exists(FILES_DIR):
            os.makedirs(FILES_DIR)

    def extract_filename(self, path):
        """Extract filename from path handling both / and \\ separators"""
        # Normalizo separatorët e path-it
        normalized_path = path.replace('\\', '/')
        # Nxjerr emrin e file
        filename = os.path.basename(normalized_path)
        return filename
