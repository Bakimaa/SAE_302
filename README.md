# SAE_302
Onion

Fonctionnalités
  Interface graphique (PyQt) avec logs et compteurs
  
  Routage multi-sauts (ONION → HOP)
  
  Clés par routeur (R1,R2,R3)
  
  Persistance MariaDB (routeurs + clients)

Installation
  MariaDB :
  
  sql
  CREATE DATABASE onion;
  CREATE USER 'onionadmin'@'localhost' IDENTIFIED BY 'adminonion';
  GRANT ALL ON onion.* TO 'onionadmin'@'localhost';
  
  USE onion;
  -- Créer tables routers/clients (voir code)
  
Utilisation
  Saisir port (9000)
  
  Cliquer Démarrer
  
  Lancer routeurs/clients (HELLO:R1, HELLO:Client_A...)

Protocole
  text
  HELLO:<nom>          # Identification
  KEYS:R1:123|R2:456   # Clés client
  PRIVKEY:123          # Clé routeur
  ONION:<payload>      # Message chiffré
  HOP:R2:<payload>     # Prochain saut
  FROM:sender;MSG:txt  # Final
Base de données
  Tables : routers (nom,clé,IP,port), clients (nom,IP,last_seen)
Limitations
  possible de retirer des routeurs du chemin, mais impossible de modifier l'ordre (R1 restera toujours le premier routeur)
