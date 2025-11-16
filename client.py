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

    def send_message(self, message):
        try:
            start_time = time.time()

            # Trajto komandën upload
            if message.startswith("/upload "):
                parts = message.split(" ", 1)
                if len(parts) < 2:
                    print("Përdorimi: /upload <path-to-file>")
                    return

                full_path = parts[1]
                filename = self.extract_filename(full_path)

                # Dërgo kërkesën për upload
                self.socket.sendto(f"/upload {filename}".encode('utf-8'),
                                   (self.server_host, self.server_port))

                # Prit për READY_FOR_UPLOAD
                response, addr = self.socket.recvfrom(4096)
                response_text = response.decode('utf-8')

                if response_text == "READY_FOR_UPLOAD":
                    self.handle_upload(full_path)
                else:
                    print(f"Përgjigja: {response_text}")

                return

            # Trajto komandën download
            if message.startswith("/download "):
                parts = message.split(" ", 1)
                if len(parts) < 2:
                    print("Përdorimi: /download <filename>")
                    return

                # Për download, dërgojmë vetëm emrin e file, jo path-in e plotë
                filename = self.extract_filename(parts[1])
                self.socket.sendto(f"/download {filename}".encode('utf-8'),
                                   (self.server_host, self.server_port))

                # Prit për përgjigje
                response, addr = self.socket.recvfrom(65536)
                response_time = time.time() - start_time
                response_text = response.decode('utf-8')

                if response_text.startswith("DOWNLOAD:"):
                    self.handle_download(response_text)
                else:
                    print(f"Koha e përgjigjes: {response_time:.3f}s")
                    print(f"Përgjigja: {response_text}")

                return

            # Trajto komandat e tjera normalisht
            self.socket.sendto(message.encode('utf-8'), (self.server_host, self.server_port))

            # Vendos timeout bazuar në privilegjet e përdoruesit (admin merr përgjigje më të shpejtë)
            timeout = 2.0 if self.is_admin else 5.0
            self.socket.settimeout(timeout)

            response, addr = self.socket.recvfrom(65536)
            response_time = time.time() - start_time
            response_text = response.decode('utf-8')

            # Trajto download për raste të tjera
            if response_text.startswith("DOWNLOAD:"):
                self.handle_download(response_text)
                return

            print(f"Koha e përgjigjes: {response_time:.3f}s")
            print(f"Përgjigja: {response_text}")

        except socket.timeout:
            print("Serveri nuk u përgjigj brenda kohës së caktuar")
        except Exception as e:
            print(f"Gabim në dërgim: {e}")

    def handle_upload(self, full_path):
        try:
            if not os.path.exists(full_path):
                print(f"File-i {full_path} nuk ekziston lokalish")
                return

            filename = self.extract_filename(full_path)

            # Përdor vetëm UTF-8 encoding
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                print(f"File-i {filename} nuk mund të lexohet si UTF-8")
                return

            upload_msg = f"UPLOAD:{filename}:{content}"
            self.socket.sendto(upload_msg.encode('utf-8'), (self.server_host, self.server_port))

            response, addr = self.socket.recvfrom(1024)
            print(f"Përgjigja: {response.decode('utf-8')}")

        except Exception as e:
            print(f"Gabim në upload: {e}")