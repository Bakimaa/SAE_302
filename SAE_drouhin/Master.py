import socket
import threading
import random
from PyQt5 import QtWidgets


class MasterServer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Master - Onion Chiffré")
        self.resize(700, 600)

        # Central widget obligatoire
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        # Tous tes widgets
        self.port_label = QtWidgets.QLabel("Port:")
        self.port_input = QtWidgets.QLineEdit("9000")
        self.start_btn = QtWidgets.QPushButton("Démarrer")
        self.clients_label = QtWidgets.QLabel("Clients: 0")
        self.routers_label = QtWidgets.QLabel("Routeurs: 0")
        self.text_log = QtWidgets.QTextEdit()
        self.text_log.setReadOnly(True)

        # Layout sur le central widget
        layout = QtWidgets.QVBoxLayout(central)
        layout.addWidget(self.port_label)
        layout.addWidget(self.port_input)
        layout.addWidget(self.start_btn)
        layout.addWidget(self.clients_label)
        layout.addWidget(self.routers_label)
        layout.addWidget(self.text_log)

        self.start_btn.clicked.connect(self.start_server)

        # Variables d'état
        self.clients = {}
        self.routers = {}
        self.lock = threading.Lock()
        self.router_priv_keys = {}
        self.router_pub_keys = {}
        self.db = None  # Initialisé plus tard

    def log(self, msg):
        self.text_log.append(msg)
        print(msg)

    def init_db(self):
        try:
            import mariadb
            conn = mariadb.connect(
                host="localhost",
                port=3306,
                user="onionadmin",
                password="adminonion",
                database="onion"
            )
            print("✅ Connexion MariaDB OK")
            return conn
        except Exception as e:
            print(f"❌ Erreur MariaDB: {e}")
            return None

    def save_entity_to_db(self, name):
        """Sauvegarde routeur ou client en base"""
        if not self.db:
            return

        try:
            cur = self.db.cursor()

            if name.startswith("Client"):
                # Sauvegarde client
                cur.execute(
                    """
                    INSERT INTO clients(name, last_ip, last_seen)
                    VALUES (%s, %s, NOW()) ON DUPLICATE KEY
                    UPDATE
                        last_ip =
                    VALUES (last_ip), last_seen = NOW()
                    """,
                    (name, "0.0.0.0")
                )
                self.log(f" Client {name} sauvé en DB")

            elif name.startswith("R"):
                # Sauvegarde routeur avec sa clé
                key = self.router_priv_keys.get(name)
                if key:
                    cur.execute(
                        """
                        INSERT INTO routers(name, ip, port, key_value)
                        VALUES (%s, %s, %s, %s) ON DUPLICATE KEY
                        UPDATE
                            ip =
                        VALUES (ip), port =
                        VALUES (port), key_value =
                        VALUES (key_value), updated_at = NOW()
                        """,
                        (name, "0.0.0.0", 0, key)
                    )
                    self.log(f" Routeur {name} (clé {key}) sauvé en DB")

            self.db.commit()

        except Exception as e:
            self.log(f"❌ Erreur sauvegarde DB {name}: {e}")

    def generate_keys(self):
        self.router_priv_keys = {
            "R1": random.randint(10000, 99999),
            "R2": random.randint(10000, 99999),
            "R3": random.randint(10000, 99999)
        }
        self.router_pub_keys = {
            "R1": self.router_priv_keys["R1"],
            "R2": self.router_priv_keys["R2"],
            "R3": self.router_priv_keys["R3"]
        }
        self.log(
            f" Clés générées: "
            f"R1={self.router_pub_keys['R1']}, "
            f"R2={self.router_pub_keys['R2']}, "
            f"R3={self.router_pub_keys['R3']}"
        )

        # Sauvegarde des clés dans MariaDB
        if not self.db:
            self.log("⚠️ MariaDB non disponible, clés non persistées")
            return

        try:
            cur = self.db.cursor()
            for name, key in self.router_priv_keys.items():
                cur.execute(
                    """
                    INSERT INTO routers(name, ip, port, key_value)
                    VALUES (%s, %s, %s, %s) ON DUPLICATE KEY
                    UPDATE
                        key_value =
                    VALUES (key_value), updated_at = NOW()
                    """,
                    (name, "0.0.0.0", 0, key),
                )
            self.db.commit()
            self.log(" Clés routeurs sauvegardées dans MariaDB")
        except Exception as e:
            self.log(f"❌ Erreur sauvegarde clés MariaDB: {e}")

    def load_or_generate_keys(self):
        if not self.db:
            self.log("⚠️ MariaDB non dispo, génération de nouvelles clés")
            self.generate_keys()
            return

        try:
            cur = self.db.cursor()
            cur.execute("SELECT name, key_value FROM routers WHERE name IN ('R1','R2','R3')")
            rows = cur.fetchall()
            if rows:
                self.router_priv_keys = {name: key for (name, key) in rows}
                self.router_pub_keys = dict(self.router_priv_keys)
                self.log(f" Clés chargées depuis MariaDB: {self.router_pub_keys}")
            else:
                self.log("ℹ️ Aucune clé en base, génération de nouvelles clés")
                self.generate_keys()
        except Exception as e:
            self.log(f"❌ Erreur chargement clés MariaDB: {e}")
            self.generate_keys()

    def update_counts(self):
        with self.lock:
            self.clients_label.setText(f"Clients: {len(self.clients)}")
            self.routers_label.setText(f"Routeurs: {len(self.routers)}")

    def start_server(self):
        self.db = self.init_db()
        if self.db:
            self.log("✅ MariaDB connecté")
        self.load_or_generate_keys()
        threading.Thread(target=self.run_server, daemon=True).start()
        self.start_btn.setEnabled(False)
        self.log(" Master démarré")

    def run_server(self):
        port = int(self.port_input.text() or "9000")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        self.log(f"Écoute: 0.0.0.0:{port}")
        s.listen()
        while True:
            conn, addr = s.accept()
            threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()

    def handle_client(self, conn):
        name = None
        try:
            ident = conn.recv(1024).decode()
            if not ident.startswith("HELLO:"):
                conn.close()
                return
            name = ident.split(":", 1)[1]

            with self.lock:
                if name.startswith("Client"):
                    self.clients[name] = conn
                elif name.startswith("R"):
                    self.routers[name] = conn

            # ✅ SAUVEGARDE ROUTEUR/CLIENT EN BASE
            self.save_entity_to_db(name)

            self.update_counts()
            self.log(f"✅ {name} connecté")

            if name.startswith("Client"):
                keys = f"R1:{self.router_pub_keys['R1']}|R2:{self.router_pub_keys['R2']}|R3:{self.router_pub_keys['R3']}"
                conn.send(f"KEYS:{keys}".encode('utf-8'))
            elif name.startswith("R"):
                priv_key = self.router_priv_keys.get(name)
                if priv_key is None:
                    self.log(f"❌ Pas de clé privée pour {name}")
                else:
                    conn.send(f"PRIVKEY:{priv_key}".encode('utf-8'))

            while True:
                data = conn.recv(4096)
                if not data:
                    break
                self.handle_message(name, data.decode('utf-8', errors='ignore'))
        except Exception as e:
            if name:
                self.log(f"❌ {name}: {e}")
        finally:
            self.cleanup(name)

    def handle_message(self, sender, msg):
        self.log(f" {sender}: {msg[:80]}")

        if msg.startswith("ONION:"):
            _, payload = msg.split(":", 1)
            first = "R1"
            if first in self.routers:
                self.routers[first].send(f"NEXT:{payload}".encode('utf-8'))
                self.log(f" Master → {first}")
            else:
                self.log(f"❌ Routeur {first} non connecté")
            return

        if msg.startswith("HOP:"):
            parts = msg.split(":", 2)
            if len(parts) < 3:
                self.log(f"❌ HOP mal formé: {repr(msg)}")
                return

            _, next_hop, payload = parts

            if next_hop:
                if next_hop in self.routers:
                    self.routers[next_hop].send(f"NEXT:{payload}".encode('utf-8'))
                    self.log(f" {sender} → {next_hop}")
                else:
                    self.log(f"❌ Routeur inconnu: {next_hop}")
            else:
                if payload.startswith("TO:") and ";MSG:" in payload:
                    dest = payload.split(";")[0][3:]
                    msg_text = payload.split(";MSG:")[1]
                    if dest in self.clients:
                        self.clients[dest].send(f"FROM:{sender};MSG:{msg_text}".encode('utf-8'))
                        self.log(f" Master → {dest}")
                    else:
                        self.log(f"❌ Client inconnu: {dest}")
                else:
                    self.log(f"❌ Payload final inattendu: {repr(payload)[:80]}")
            return

    def cleanup(self, name):
        if name:
            with self.lock:
                self.clients.pop(name, None)
                self.routers.pop(name, None)
                self.update_counts()
            self.log(f" {name}")


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    win = MasterServer()
    win.show()
    sys.exit(app.exec_())