[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#exigences-et-installation)

**OmniTunnel CLI** est un client VPN puissant en ligne de commande basé sur les tunnels SSH, les protocoles V2Ray/Xray et l'injection de Payloads HTTP, conçu pour contourner les restrictions réseau et optimiser la sécurité sous **Linux (Ubuntu/Debian)** et **Android (Termux)**.

---

## 🚀 Nouveautés de la version v1.1.0

*   **Support des protocoles V2Ray / Xray / Sing-Box** : Importation directe de liens de partage (`vless://`, `vmess://`, `trojan://`, `ss://`, `hy2://` / `hysteria2://`) avec support de REALITY, uTLS, WebSocket et gRPC.
*   **Moteur Sing-Box TUN Nouvelle Génération** : Interface TUN **`sing-box`** (`tun0`) haute performance avec résolution DNS-over-HTTPS (DoH) et débit multiplié par 3 à 5.
*   **Format de profil chiffré `.ot`** : Exportation et importation de profils `.ot` (OmniTunnel) avec chiffrement sécurisé PBKDF2-HMAC-SHA256.
*   **Journalisation centralisée des sessions** : Logs diffusés en direct sur la console et enregistrés dans `logs/session.log` avec horodatage et suppression des codes ANSI.
*   **Raccourci Terminal Système `ot`** : Lancement instantané depuis n'importe quel dossier via la commande **`ot`**.
*   **Optimisation Kernel TCP BBR** : Contrôle de congestion Linux Kernel BBR avec script d'activation intégré (`vpn/tcp_bbr.sh`).

---

## 🛠 Prérequis et Installation

### 1. Sur Debian, Ubuntu et Linux Mint

Conformément à la directive **PEP 668** sur les environnements Python gérés en externe, l'usage de `pip3 install` au niveau système est bloqué par défaut sur les distributions Linux récentes. Pour garantir la sécurité et l'intégrité de votre système, nous installons le composant directement via le gestionnaire de paquets APT :

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev sing-box
```

### 2. Sur Termux (Android)

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. Téléchargement du projet
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🚨 Limites de Droits Root & Variables d'Environnement

Lorsque vous lancez le VPN, des privilèges de superutilisateur sont indispensables :

1.  **Réinitialisation du `$PATH` avec `sudo`** : Par défaut, `sudo` restreint les chemins d'exécution de commande (directive `secure_path` dans `/etc/sudoers`). Pour éviter que le script de démarrage ne trouve pas vos utilitaires locaux (`bin/redsocks`, `bin/dns2socks`), lancez toujours l'environnement depuis la racine du projet.
2.  **Droits d'administration requis (Root)** : L'orchestration des flux de routage global, l'ouverture de descripteurs bas niveau et la configuration des règles NAT iptables requièrent d'être superutilisateur (Root). Sur Android (Termux), l'appareil doit impérativement être rooté.

---

## 🖥 Utilisation (Méthode Recommandée - Mode CLI Menu)

Le script interactif Python **`menu.py`** vous permet de configurer et de lancer votre connexion VPN avec une interface visuelle animée.

```bash
chmod +x menu.py runvpn.sh
sudo ./menu.py
```

### Éditeur et Gestion de Profils
Tout comme l'application HTTP Custom sur Android, configurez vos tunnels et profils avec précision :

| Menu Principal | Édition des Paramètres SSH |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| Gestion des Profils (Sauvegarde/Chargement) |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

### 📦 Partage de Profils (Format .ot)

OmniTunnel CLI intègre le support d'exportation et d'importation de fichiers de profil `.ot` (OmniTunnel) pour partager facilement vos configurations (SSH, Payloads, IPs Proxy et SNI) avec d'autres utilisateurs.

* **Protection par Mot de Passe** : Chiffrement sécurisé (PBKDF2-HMAC-SHA256) pour protéger vos identifiants SSH lors du partage.
* **Commandes CLI** :
  ```bash
  # Exporter la configuration active vers un fichier .ot
  python3 src/omni_profile.py export -i cfgs/settings.ini -o MyProfile.ot --name "MonServeur" --password "secret"

  # Importer un fichier .ot vers settings.ini
  python3 src/omni_profile.py import -i MyProfile.ot -o cfgs/settings.ini --password "secret"
  ```

---

## ⚙️ Configuration Manuelle (Advanced / Headless)

Si vous préférez configurer manuellement le VPN sans utiliser l'interface interactive, éditez le fichier [cfgs/settings.ini](cfgs/settings.ini) :

### Modes de connexion supportés (`connection_mode`) :
*   `mode 0` : **Direct SSH** — Tunnel SSH brut sans intermédiaire.
*   `mode 1` : **Payload Only** — Injection d'en-têtes HTTP personnalisés via proxy.
*   `mode 2` : **SNI Only** — Évasion DPI via masquage SSL/TLS SNI (Server Name Indication).
*   `mode 3` : **Payload + SNI** — Niveau de masquage maximal (Payload HTTP traversant un tunnel SSL transparent).

Une fois les configurations appliquées, lancez directement l'agent d'arrière-plan :
```bash
sudo ./runvpn.sh
```

---

## 📊 Diagnostics & Journal de Connexion

Une fois connecté, le flux s'établit et les événements s'affichent en temps réel dans votre console :

![Logs de connexion réussie](docs/images/connection_logs.png)

> **Arrêt du VPN** : Pour stopper proprement tous les tunnels réseau et restaurer la table de routage par défaut de votre système d'exploitation, utilisez simplement la combinaison de touches `Ctrl + C`.

---

## 📄 Licence
Ce projet est distribué sous la licence permissive **Apache-2.0**.
