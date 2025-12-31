import socket
import threading
from PyQt5 import QtWidgets
from datetime import datetime

ROUTER_NAME = "R1"  # ← R2 ou R3


class Routeur(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Routeur {ROUTER_NAME}")
        self.resize(450, 400)

        self.master_label = QtWidgets.QLabel("Master:")
        self.master_input = QtWidgets.QLineEdit("127.0.0.1:9000")
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.start_btn = QtWidgets.QPushButton("Connecter")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.master_label)
        layout.addWidget(self.master_input)
        layout.addWidget(self.log_view)
        layout.addWidget(self.start_btn)
        self.setLayout(layout)

        self.start_btn.clicked.connect(self.start)
        self.sock = None
        self.priv_key = None

    def log(self, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{t}] {msg}")

    def simple_decrypt(self, msg, key):
        """XOR symétrique (identique à encrypt)"""
        return ''.join(chr(ord(c) ^ (key & 0xFF)) for c in msg)

    def start(self):
        self.start_btn.setEnabled(False)
        threading.Thread(target=self.connect_master, daemon=True).start()

    def connect_master(self):
        host, port = self.master_input.text().split(":", 1)
        port = int(port)
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.sock.send(f"HELLO:{ROUTER_NAME}".encode())

            data = self.sock.recv(1024).decode()
            if data.startswith("PRIVKEY:"):
                self.priv_key = int(data.split(":", 1)[1])
                self.log(f"🔑 Privé: {self.priv_key}")

            self.listen_loop()
        except Exception as e:
            self.log(f"❌ {e}")

    def listen_loop(self):
        try:
            while True:
                data = self.sock.recv(4096)
                if not data:
                    self.log("Socket fermée")
                    break
                msg = data.decode('utf-8', errors='ignore')
                self.log(f"📨 Reçu du Master: {repr(msg)[:80]}")

                if msg.startswith("NEXT:") and self.priv_key:
                    encrypted = msg[5:]
                    decrypted = self.simple_decrypt(encrypted, self.priv_key)
                    self.log(f"🔓 Déchiffré: {repr(decrypted)[:120]}")

                    if not decrypted.startswith("NEXT:") or "|" not in decrypted:
                        self.log("❌ Format inattendu (pas 'NEXT:xxx|yyy')")
                        continue

                    header, payload = decrypted.split("|", 1)  # header = "NEXT:R2" ou "NEXT:"
                    _, next_hop = header.split(":", 1)  # next_hop = "R2" ou ""

                    if next_hop:
                        # encore un routeur dans la chaîne
                        hop_msg = f"HOP:{next_hop}:{payload}"
                    else:
                        # plus de routeur → payload doit être TO:Client_X;MSG:...
                        hop_msg = f"HOP::{payload}"

                    try:
                        self.sock.send(hop_msg.encode('utf-8'))
                        self.log(f"✅ HOP envoyé au Master ({hop_msg[:80]})")
                    except Exception as e:
                        self.log(f"❌ Erreur envoi HOP: {e}")
                else:
                    self.log(f"ℹ️ Message ignoré: {repr(msg)[:60]}")
        except Exception as e:
            self.log(f"❌ Exception listen_loop: {e}")


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = Routeur()
    win.show()
    sys.exit(app.exec_())
