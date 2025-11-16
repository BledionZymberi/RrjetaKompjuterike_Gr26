import socket
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

    def connect(self):
        try:
            # Test connection
            test_msg = "Ping"
            start_time = time.time()
            self.socket.sendto(test_msg.encode('utf-8'), (self.server_host, self.server_port))

            try:
                response, addr = self.socket.recvfrom(1024)
                self.response_time = time.time() - start_time
                print(f"U lidh me serverin {self.server_host}:{self.server_port}")
                print(f"Koha e përgjigjes: {self.response_time:.3f} sekonda")
                return True
            except socket.timeout:
                print("Serveri nuk u përgjigj. Kontrollo adresën dhe portin.")
                return False

        except Exception as e:
            print(f"Gabim në lidhje: {e}")
            return False

    def login_as_admin(self, username, password):
        try:
            login_msg = f"LOGIN_ADMIN:{username}:{password}"
            self.socket.sendto(login_msg.encode('utf-8'), (self.server_host, self.server_port))

            response, addr = self.socket.recvfrom(1024)
            response_text = response.decode('utf-8')

            if response_text.startswith("SUCCESS"):
                self.is_admin = True
                self.username = username
                print(f"U loguat si administrator: {username}")
                # Admin ka timeout më të shkurtër për përgjigje më të shpejtë
                self.socket.settimeout(2.0)
                return True
            else:
                print(f"Login i dështuar: {response_text}")
                return False

        except Exception as e:
            print(f"Gabim në login: {e}")
            return False
