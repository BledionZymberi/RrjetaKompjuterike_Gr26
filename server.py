import socket
import threading
import time
import os
import json
from datetime import datetime
from collections import defaultdict
import logging

FILES_DIR = "Files"


class UDPServer:
    def __init__(self, host='0.0.0.0', port=5678, max_connections=5):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        self.clients = {}
        self.active_connections = 0
        self.stats = {
            'total_messages_received': 0,
            'total_bytes_received': 0,
            'total_bytes_sent': 0,
            'client_stats': defaultdict(lambda: {'messages_received': 0, 'bytes_received': 0})
        }
        self.admin_client = None
        self.running = True
        self.last_activity = {}
        self.timeout = 30  # 30 sekonda timeout

        # Krijo folderin Files nëse nuk ekziston
        if not os.path.exists(FILES_DIR):
            os.makedirs(FILES_DIR)

        # Konfigurimi i logging për server_stats.txt
        self.setup_logging()

    def setup_logging(self):
        """Setup logging për server_stats.txt"""
        self.logger = logging.getLogger('server_stats')
        self.logger.setLevel(logging.INFO)

        # Kontrollo nëse handler ekziston tashmë
        if not self.logger.handlers:
            handler = logging.FileHandler('server_stats.txt', encoding='utf-8')
            formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def start(self):
        try:
            self.socket.bind((self.host, self.port))
            print(f"Serveri UDP u startua në {self.host}:{self.port}")
            print(f"Folderi për file: {FILES_DIR}/")
            print(f"Max connections: {self.max_connections}")

            # Regjistro fillimin e serverit
            self.logger.info(f"SERVER STARTED - Host: {self.host}, Port: {self.port}")

            # Nis thread-et
            threading.Thread(target=self.monitor_connections, daemon=True).start()
            threading.Thread(target=self.handle_commands, daemon=True).start()

            while self.running:
                try:
                    data, addr = self.socket.recvfrom(4096)
                    threading.Thread(target=self.handle_request, args=(data, addr)).start()
                except Exception as e:
                    if self.running:
                        print(f"Gabim në pranim të të dhënave: {e}")

        except Exception as e:
            print(f"Gabim në start: {e}")
        finally:
            self.socket.close()
            self.logger.info("SERVER STOPPED")

    def handle_request(self, data, addr):
        # Kontrollo nëse të dhënat janë UTF-8 valid
        try:
            message = data.decode('utf-8')
        except UnicodeDecodeError:
            # Injoro paketat jo-UTF-8 (skanerë, broadcast, noise)
            return

        if self.active_connections >= self.max_connections and addr not in self.clients:
            self.send_response(addr, "ERROR: Server full")
            return

        if addr not in self.clients:
            self.clients[addr] = {
                'connected_at': datetime.now(),
                'messages_received': 0,
                'is_admin': False,
                'username': f"user_{len(self.clients) + 1}"
            }
            self.active_connections += 1
            print(f"Klient i ri: {addr}")
            self.logger.info(f"NEW CLIENT - {addr}")

        # update activity
        self.last_activity[addr] = time.time()

        # update stats
        self.stats['total_messages_received'] += 1
        self.stats['total_bytes_received'] += len(data)
        self.stats['client_stats'][addr]['messages_received'] += 1
        self.stats['client_stats'][addr]['bytes_received'] += len(data)
        self.clients[addr]['messages_received'] += 1

        print(f"Nga {addr}: {message}")

        # FIX: PING / PONG
        if message.lower() == "ping":
            self.send_response(addr, "PONG")
            return

        if message.startswith('/'):
            self.handle_command(message, addr)
        elif message == 'STATS':
            self.send_stats(addr)
        elif message.startswith('LOGIN_ADMIN'):
            self.set_admin(addr, message)
        elif message.startswith('UPLOAD:'):
            self.handle_upload_content(message, addr)
        else:
            self.send_response(addr, "Server: Mesazhi u pranua")
