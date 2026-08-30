[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#requisitos-e-instalação)

**OmniTunnel CLI** é um cliente VPN em linha de comando baseado em túneis SSH robustos, projetado para contornar restrições de rede e otimizar a segurança da sua conexão no **Linux (Ubuntu/Debian)** e **Android (Termux)**.

---

## 🚀 Novidades da Versão v1.0.2

*   **Menu interativo em Python (`menu.py`)**: Uma interface moderna de linha de comando (CLI) para editar e gerenciar fluentemente seus perfis, payloads (cargas úteis) e credenciais SSH sem precisar editar manualmente os arquivos ini brutos.
*   **Compatibilidade SSH aprimorada**: Suporte explícito para suítes criptográficas e algoritmos de troca de chaves modernos (`+ssh-rsa`, `ssh-ed25519`, `ecdsa`, `rsa-sha2`), corrigindo bloqueios de conexão em distribuições Linux recentes (Ubuntu 22.04+, Debian 12+).
*   **Desligamento limpo e Tratamento de sinais**: Integração de manipuladores de sinal do sistema (`trap`) no script de inicialização para limpar e encerrar corretamente todos os processos filhos (`redsocks`, `dns2socks`, `ssh`) em caso de interrupção (`Ctrl+C`).
*   **Compilação robusta e isolada**: Script `runvpn.sh` atualizado para compilar dinamicamente as dependências ausentes sob demanda, isolando-as com segurança em `./bin` sem poluir a árvore de diretórios global do sistema.
*   **Resiliência de rede aprimorada**: Gerenciamento avançado do loop de escuta e detecção eficiente de sockets fechados pelo servidor remoto para evitar travamentos e vazamentos de descritores de arquivos.

---

## 🛠 Requisitos e Instalação

### 1. No Debian, Ubuntu e Linux Mint

Em conformidade com a diretiva **PEP 668** sobre ambientes Python gerenciados externamente, o uso de `pip3 install` no nível do sistema é bloqueado por padrão em distribuições Linux recentes. Para garantir a segurança e a integridade do seu sistema, instalamos o componente diretamente através do gerenciador de pacotes APT:

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev
```

### 2. No Termux (Android)

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. Download do projeto
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🚨 Limites de Privilégios de Root e Variáveis de Ambiente

Ao iniciar a VPN, os privilégios de superusuario (root) são indispensáveis:

1.  **Redefinição do `$PATH` com `sudo`**: Por padrão, o `sudo` restringe os caminhos de execução de comandos (diretiva `secure_path` no arquivo `/etc/sudoers`). Para evitar que o script de inicialização falhe ao encontrar seus utilitários locais (`bin/redsocks`, `bin/dns2socks`), sempre execute o ambiente a partir da raiz do projeto.
2.  **Direitos de administração necessários (Root)**: A orquestração dos fluxos de roteamento global, abertura de descritores de baixo nível e configuração de regras NAT do iptables exigem privilégios de superusuário (Root). No Android (Termux), o dispositivo deve obrigatoriamente possuir acesso root.

---

## 🖥 Uso (Método Recomendado - Modo Menu CLI)

O script interativo em Python **`menu.py`** permite configurar e iniciar sua conexão VPN com uma interface visual animada.

```bash
chmod +x menu.py runvpn.sh
sudo ./menu.py
```

### Editor e Gerenciamento de Perfis
Assim como no aplicativo HTTP Custom no Android, configure seus túneles e perfis com precisão:

| Menu Principal | Edição de Parámetros SSH |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| Gerenciamento de Perfis (Salvar/Carregar) |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

---

## ⚙️ Configuração Manual (Avançada / Headless)

Se preferir configurar a VPN manualmente sem usar a interface interativa, edite o arquivo [cfgs/settings.ini](cfgs/settings.ini):

### Modos de conexão suportados (`connection_mode`):
*   `mode 0`: **Direct SSH** — Túnel SSH bruto sem intermediários.
*   `mode 1`: **Payload Only** — Injeção de cabeçalhos HTTP personalizados via proxy.
*   `mode 2`: **SNI Only** — Evasão de DPI via mascaramento de SSL/TLS SNI (Server Name Indication).
*   `mode 3`: **Payload + SNI** — Nível máximo de mascaramento (Payload HTTP trafegando por um túnel SSL transparente).

Depois de aplicar as configurações, inicie o agente de segundo plano diretamente:
```bash
sudo ./runvpn.sh
```

---

## 📊 Diagnósticos e Log de Conexão

Depois de conectado, o fluxo de tráfego é estabelecido e os eventos são exibidos em tempo real no console:

![Logs de conexão bem-sucedida](docs/images/connection_logs.png)

> **Interrompendo a VPN**: Para encerrar de forma limpa todos os túneis de rede e restaurar a tabela de roteamento padrão do seu sistema operacional, basta usar a combinação de teclas `Ctrl + C`.

---

## 📄 Licença
Este projeto é distribuído sob a licença permissiva **Apache-2.0**.
