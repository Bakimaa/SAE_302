
import socket
import threading
from PyQt5 import QtWidgets, QtCore
from datetime import datetime


class ClientA(QtWidgets.QWidget):
    message_signal = QtCore.pyqtSignal(str)
    status_signal = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Client A")
        self.resize(500, 600)

        self.chat = QtWidgets.QTextEdit()
        self.chat.setReadOnly(True)
        self.master_label = QtWidgets.QLabel("Master:")
        self.master_input = QtWidgets.QLineEdit("127.0.0.1:9000")
        self.path_label = QtWidgets.QLabel("Chemin:")
        self.path_input = QtWidgets.QLineEdit("R1,R2,R3")
        self.msg_input = QtWidgets.QLineEdit()
        self.msg_input.returnPressed.connect(lambda: self.send_message())
        self.send_btn = QtWidgets.QPushButton("Onion")
        self.send_btn.clicked.connect(lambda: self.send_message())
        self.status = QtWidgets.QLabel("Déconnecté")
        self.dest_label = QtWidgets.QLabel("Destination (nom client) :")
        self.dest_input = QtWidgets.QLineEdit("Client_B")
        self.connect_btn = QtWidgets.QPushButton("Connecter au Master")
        self.connect_btn.clicked.connect(self.start_connect)
        self.client_name = "Client_A"

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.chat)
        layout.addWidget(self.master_label)
        layout.addWidget(self.master_input)
        layout.addWidget(self.path_label)
        layout.addWidget(self.path_input)
        layout.addWidget(self.dest_label)
        layout.addWidget(self.dest_input)
        layout.addWidget(self.msg_input)
        layout.addWidget(self.send_btn)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.status)
        self.setLayout(layout)

        self.message_signal.connect(self.log)
        self.status_signal.connect(self.set_status)

        self.sock = None
        self.router_pub_keys = {}
        self.connect_thread = None

    def start_connect(self):
        """Lancé par le bouton Connecter au Master."""
        if self.connect_thread and self.connect_thread.is_alive():
            self.status_signal.emit("Connexion déjà en cours...")
            return

        self.status_signal.emit("Connexion au Master...")
        self.connect_thread = threading.Thread(target=self.connect_loop, daemon=True)
        self.connect_thread.start()

    def log(self, msg):
        self.chat.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def set_status(self, text):
        self.status.setText(text)

    def simple_encrypt(self, msg, key):
        """XOR symétrique (même clé chiffrement/déchiffrement)"""
        return ''.join(chr(ord(c) ^ (key & 0xFF)) for c in msg)

    def parse_keys(self, keys_data):
        self.router_pub_keys = {}
        for info in keys_data.split("|"):
            name, key = info.split(":")
            self.router_pub_keys[name] = int(key)
        self.log(f"Clés: {list(self.router_pub_keys.values())}")

    def build_onion(self, path, dest, message):

        hops = [h.strip() for h in path.split(",") if h.strip()]
        inner = f"TO:{dest};MSG:{message}"  # ce que voit le dernier routeur
        current = inner


        for i, router in enumerate(reversed(hops)):
            key = self.router_pub_keys[router]  # même valeur que côté routeur


            if i == 0:

                next_hop = ""  #vide, signifiera "plus de routeur"
            else:
                # pour R2, R1, etc.
                next_hop = hops[len(hops) - i]


            layer = f"NEXT:{next_hop}|{current}"

            current = self.simple_encrypt(layer, key)


        return current

    def connect_loop(self):
        while True:
            master_addr = self.master_input.text().strip()
            if ":" not in master_addr:
                self.status_signal.emit("Format Master invalide (ex: 127.0.0.1:9000)")
                return

            host, port = master_addr.split(":", 1)
            try:
                port = int(port)
            except ValueError:
                self.status_signal.emit("Port Master invalide")
                return

            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((host, port))
                self.sock.send(f"HELLO:{self.client_name}".encode())  # écrire "Client_A" ou "Client_B" dans l'interface graphique

                data = self.sock.recv(4096).decode()
                if data.startswith("KEYS:"):
                    keys_str = data.split(":", 1)[1]
                    self.parse_keys(keys_str)
                    self.status_signal.emit(f"Connecté à {master_addr}")
                    self.listen_loop()
                    return
                else:
                    self.status_signal.emit("Réponse Master inattendue")
                    return

            except Exception as e:
                self.status_signal.emit(f"Connexion échouée: {e}")
                return

    def listen_loop(self):
        try:
            while True:
                data = self.sock.recv(4096)
                if not data: break
                msg = data.decode()
                if msg.startswith("FROM:"):
                    sender = msg.split(";")[0][5:]
                    content = msg.split(";MSG:")[1]
                    self.log(f"{sender}: {content}")
        except Exception as e:
            self.log(f"{e}")

    def send_message(self):
        msg = self.msg_input.text().strip()
        if not msg or not self.sock:
            return

        path = self.path_input.text().strip()  # exemple : "R1,R2,R3"
        dest = self.dest_input.text().strip()  # exemple : "Client_B" ou "Client_A"

        onion = self.build_onion(path, dest, msg)
        if onion is None:
            return

        relay_msg = f"ONION:{onion}"
        self.sock.send(relay_msg.encode('utf-8'))
        self.log(f"Onion [{path}] → {dest}: {msg[:30]}...")
        self.msg_input.clear()


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = ClientA()
    win.show()
    sys.exit(app.exec_())
