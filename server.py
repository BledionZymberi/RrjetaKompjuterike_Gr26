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

            def handle_command(self, command, addr):
                parts = command.split()
                if not parts:
                    self.send_response(addr, "ERROR: Komandë e zbrazët")
                    return

                cmd = parts[0].lower()

                # Komandat e lejuara për përdoruesit normal (vetëm lexim)
                allowed_user_cmds = ['/read', '/search', '/info', '/list']

                if not self.clients[addr]['is_admin'] and cmd not in allowed_user_cmds:
                    self.send_response(addr, "ERROR: Nuk ke leje për këtë komandë")
                    return

                try:
                    if cmd == '/list':
                        directory = parts[1] if len(parts) > 1 else FILES_DIR
                        self.list_files(addr, directory)
                    elif cmd == '/read':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /read <filename>")
                            return
                        self.read_file(addr, parts[1])
                    elif cmd == '/upload':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /upload <filename>")
                            return
                        self.upload_file(addr, parts[1])
                    elif cmd == '/download':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /download <filename>")
                            return
                        self.download_file(addr, parts[1])
                    elif cmd == '/delete':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /delete <filename>")
                            return
                        self.delete_file(addr, parts[1])
                    elif cmd == '/search':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /search <keyword>")
                            return
                        self.search_files(addr, parts[1])
                    elif cmd == '/info':
                        if len(parts) < 2:
                            self.send_response(addr, "ERROR: Përdorimi: /info <filename>")
                            return
                        self.file_info(addr, parts[1])
                    else:
                        self.send_response(addr, "ERROR: Komandë e panjohur")

                except Exception as e:
                    self.send_response(addr, f"ERROR: {e}")

            def handle_upload_content(self, message, addr):
                try:
                    parts = message.split(':', 2)
                    if len(parts) < 3:
                        self.send_response(addr, "ERROR: Format i gabuar i upload")
                        return

                    filename = parts[1]
                    content = parts[2]

                    # Ruaj file në folderin Files
                    filepath = os.path.join(FILES_DIR, filename)

                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)

                    self.send_response(addr, f"OK: Upload sukses për {filename}")
                    self.logger.info(f"FILE UPLOAD - {addr} uploaded {filename}")
                except Exception as e:
                    self.send_response(addr, f"ERROR upload: {e}")

            def list_files(self, addr, directory):
                try:
                    # Sigurohu që directory është brenda FILES_DIR për siguri
                    if not directory.startswith(FILES_DIR):
                        directory = FILES_DIR

                    files = os.listdir(directory)
                    output = "\n".join(files) if files else "(Bosh)"
                    self.send_response(addr, output)
                except Exception as e:
                    self.send_response(addr, f"ERROR list: {e}")

            def read_file(self, addr, filename):
                try:
                    # Sigurohu që file është brenda FILES_DIR
                    filepath = os.path.join(FILES_DIR, filename)

                    if not os.path.exists(filepath):
                        self.send_response(addr, "ERROR: File nuk ekziston")
                        return

                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    self.send_response(addr, content)
                except Exception as e:
                    self.send_response(addr, f"ERROR read: {e}")

            def upload_file(self, addr, filename):
                self.send_response(addr, "READY_FOR_UPLOAD")

            def download_file(self, addr, filename):
                try:
                    # Sigurohu që file është brenda FILES_DIR
                    filepath = os.path.join(FILES_DIR, filename)

                    if not os.path.exists(filepath):
                        self.send_response(addr, "ERROR: File nuk ekziston")
                        return

                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    self.send_response(addr, f"DOWNLOAD:{filename}:{content}")
                    self.logger.info(f"FILE DOWNLOAD - {addr} downloaded {filename}")
                except Exception as e:
                    self.send_response(addr, f"ERROR download: {e}")

            def delete_file(self, addr, filename):
                try:
                    # Sigurohu që file është brenda FILES_DIR
                    filepath = os.path.join(FILES_DIR, filename)

                    if not os.path.exists(filepath):
                        self.send_response(addr, "ERROR: File nuk ekziston")
                        return

                    os.remove(filepath)
                    self.send_response(addr, "OK: File u fshi")
                    self.logger.info(f"FILE DELETE - {addr} deleted {filename}")
                except Exception as e:
                    self.send_response(addr, f"ERROR në delete: {e}")

    def search_files(self, addr, keyword):
        try:
            results = []
            for file in os.listdir(FILES_DIR):
                if keyword.lower() in file.lower():
                    results.append(file)

            if results:
                self.send_response(addr, "\n".join(results))
            else:
                self.send_response(addr, "Asgjë nuk u gjet")
        except Exception as e:
            self.send_response(addr, f"ERROR search: {e}")

    def file_info(self, addr, filename):
        try:
            # Sigurohu që file është brenda FILES_DIR
            filepath = os.path.join(FILES_DIR, filename)

            if not os.path.exists(filepath):
                self.send_response(addr, "ERROR: File nuk ekziston")
                return

            stat = os.stat(filepath)
            created_time = datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            modified_time = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

            info = f"""File: {filename}
Madhësia: {stat.st_size} bytes
Data e krijimit: {created_time}
Data e modifikimit: {modified_time}"""

            self.send_response(addr, info)
        except Exception as e:
            self.send_response(addr, f"ERROR info: {e}")

    def set_admin(self, addr, message):
        try:
            parts = message.split(':')
            if len(parts) < 3:
                self.send_response(addr, "ERROR: Format i gabuar i login")
                return

            if parts[2] == "admin123":
                self.clients[addr]['is_admin'] = True
                self.clients[addr]['username'] = parts[1]
                self.admin_client = addr
                self.send_response(addr, "SUCCESS: Admin login")
                print(f"{addr} u bë administrator")
                self.logger.info(f"ADMIN LOGIN - {addr} as {parts[1]}")
            else:
                self.send_response(addr, "ERROR: Fjalëkalim gabim")
                self.logger.info(f"FAILED LOGIN - {addr} - Wrong password")
        except Exception as e:
            self.send_response(addr, f"ERROR login: {e}")
