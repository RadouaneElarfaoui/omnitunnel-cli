[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#requisitos-e-instalación)

**OmniTunnel CLI** es un cliente VPN en línea de comandos basado en túneles SSH robustos, diseñado para eludir las restricciones de red y optimizar la seguridad de su conexión en **Linux (Ubuntu/Debian)** y **Android (Termux)**.

---

## 🚀 Novedades de la Versión v1.0.2

*   **Menú interactivo en Python (`menu.py`)**: Una interfaz moderna en línea de comandos (CLI) para editar y gestionar fluidamente sus perfiles, cargas útiles (payloads) y credenciales SSH sin tener que modificar manualmente los archivos ini brutos.
*   **Compatibilidad SSH mejorada**: Soporte explícito para suites criptográficas y algoritmos de intercambio de claves modernos (`+ssh-rsa`, `ssh-ed25519`, `ecdsa`, `rsa-sha2`), solucionando los bloqueos de conexión en distribuciones Linux recientes (Ubuntu 22.04+, Debian 12+).
*   **Apagado limpio y Gestión de señales**: Integración de manejadores del sistema `trap` en el script de inicio para limpiar y finalizar de forma limpia todos los procesos hijos (`redsocks`, `dns2socks`, `ssh`) en caso de interrupción (`Ctrl+C`).
*   **Compilación robusta e aislada**: Script `runvpn.sh` actualizado para compilar dinámicamente sobre la marcha las dependencias faltantes, aislándolas de forma segura en `./bin` sin ensuciar el árbol de directorios global del sistema.
*   **Resiliencia de red mejorada**: Gestión avanzada del bucle de escucha y detección eficiente de sockets cerrados por el servidor remoto para evitar bloqueos y fugas de descriptores de archivos.

---

## 🛠 Requisitos e Instalación

### 1. En Debian, Ubuntu y Linux Mint

De acuerdo con la directiva **PEP 668** sobre entornos Python gestionados externamente, el uso de `pip3 install` a nivel de sistema está bloqueado por defecto en las distribuciones de Linux recientes. Para garantizar la seguridad e integridad de su sistema, instalamos el componente directamente a través del gestor de paquetes APT:

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev
```

### 2. En Termux (Android)

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. Descarga del proyecto
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🚨 Límites de Privilegios de Root y Variables de Entorno

Al iniciar la VPN, los privilegios de superusuario (root) son indispensables:

1.  **Restablecimiento de `$PATH` con `sudo`**: Por defecto, `sudo` restringe las rutas de ejecución de comandos (directiva `secure_path` en `/etc/sudoers`). Para evitar que el script de inicio no encuentre sus utilidades locales (`bin/redsocks`, `bin/dns2socks`), ejecute siempre el entorno desde la raíz del proyecto.
2.  **Derechos de administración requeridos (Root)**: La orquestación de los flujos de enrutamiento global, la apertura de descriptores de bajo nivel y la configuración de las reglas NAT de iptables requieren privilegios de superusuario (Root). En Android (Termux), el dispositivo debe estar obligatoriamente rooteado.

---

## 🖥 Uso (Método Recomendado - Modo de Menú CLI)

El script interactivo de Python **`menu.py`** le permite configurar e iniciar su conexión VPN con una interfaz visual animada.

```bash
chmod +x menu.py runvpn.sh
sudo ./menu.py
```

### Editor y Gestión de Perfiles
Al igual que la aplicación HTTP Custom en Android, configure sus túneles y perfiles con precisión:

| Menú Principal | Edición de Parámetros SSH |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| Gestión de Perfiles (Guardar/Cargar) |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

---

## ⚙️ Configuración Manual (Avanzada / Headless)

Si prefiere configurar la VPN manualmente sin utilizar la interfaz interactiva, edite el archivo [cfgs/settings.ini](cfgs/settings.ini):

### Modos de conexión admitidos (`connection_mode`):
*   `mode 0`: **Direct SSH** — Túnel SSH nativo/bruto sin intermediarios.
*   `mode 1`: **Payload Only** — Inyección de encabezados HTTP personalizados a través de proxy.
*   `mode 2`: **SNI Only** — Evasión de DPI mediante falsificación de SSL/TLS SNI (Server Name Indication).
*   `mode 3`: **Payload + SNI** — Nivel de enmascaramiento máximo (Carga útil HTTP que viaja a través de un túnel SSL transparente).

Una vez aplicadas las configuraciones, inicie el agente en segundo plano directamente:
```bash
sudo ./runvpn.sh
```

---

## 📊 Diagnóstico y Registro de Conexión

Una vez conectado, el flujo se establece y los eventos se muestran en tiempo real en su consola:

![Logs de conexión exitosa](docs/images/connection_logs.png)

> **Detener la VPN**: Para detener de forma limpia todos los túneles de red y restaurar la tabla de enrutamiento predeterminada de su sistema operativo, simplemente use la combinación de teclas `Ctrl + C`.

---

## 📄 Licencia
Este proyecto se distribuye bajo la licencia permisiva **Apache-2.0**.
