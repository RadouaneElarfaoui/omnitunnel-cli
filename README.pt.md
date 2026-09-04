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

### ⚡ Instalação em uma única linha (Recomendada)

```bash
curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/install.sh | sudo bash
```

Ou com `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/install.sh | sudo bash
```

> **Nota**: O instalador detecta automaticamente os pacotes existentes e o Sing-Box, baixando apenas o estritamente necessário.

### 🗑️ Desinstalação em uma linha

```bash
curl -fsSL https://raw.githubusercontent.com/RadouaneElarfaoui/omnitunnel-cli/main/uninstall.sh | sudo bash
```

---

### Instalação Manual (Debian / Ubuntu / Mint)

```bash
# 1. Dependências do sistema
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-certifi make libevent-dev
sudo apt install -y git openssh-client sshpass netcat-openbsd python3 python3-certifi iptables

# 2. Sing-Box (se não instalado)
cd /tmp && wget https://github.com/SagerNet/sing-box/releases/download/v1.14.0/sing-box_1.14.0_linux_amd64.deb && sudo apt install -y ./sing-box_1.14.0_linux_amd64.deb

# 3. Download do projeto
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
chmod +x menu.py runvpn.sh install.sh uninstall.sh
```

---

## 🖥 Uso (Método Recomendado - Modo Menu CLI)

Se instalado via instalador de uma linha, execute:

```bash
otunnel
```

*(ou `sudo otunnel`)*

Ou a partir do diretório clonado do projeto:

```bash
chmod +x menu.py runvpn.sh
./menu.py
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
