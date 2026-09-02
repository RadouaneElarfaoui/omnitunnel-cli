[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#环境要求与安装)

**OmniTunnel CLI** 是一款基于强健 SSH 隧道的命令行 VPN 客户端，旨在绕过网络限制并优化 **Linux (Ubuntu/Debian)** 和 **Android (Termux)** 下的连接安全性。

---

## 🚀 v1.0.2 版本新特性

*   **Python 交互式菜单 (`menu.py`)**：一个现代化的命令行界面 (CLI)，用于无缝编辑和管理您的配置文件、载荷 (payloads) 和 SSH 凭据，而无需手动修改原始的 ini 文件。
*   **增强的 SSH 兼容性**：显式支持现代加密套件和密钥交换算法 (`+ssh-rsa`, `ssh-ed25519`, `ecdsa`, `rsa-sha2`)，解决了在较新 Linux 发行版（如 Ubuntu 22.04+、Debian 12+）上的连接受阻问题。
*   **安全关闭与信号管理**：在启动脚本中集成了系统 `trap` 处理器，以便在发生中断 (`Ctrl+C`) 时，干净利落地清理并终止所有子进程 (`redsocks`, `dns2socks`, `ssh`)。
*   **强健的隔离编译**：更新了 `runvpn.sh` 脚本，以便在运行中动态编译缺失的依赖项，并将其安全地隔离在 `./bin` 目录中，避免污染系统的全局目录树。
*   **提高网络弹性**：先进的监听循环管理和对远程服务器关闭套接字 (sockets) 的高效检测，可防止崩溃和文件描述符泄漏。

---

## 🛠 环境要求与安装

### 1. 在 Debian、Ubuntu 和 Linux Mint 上

根据针对外部托管 Python 环境的 **PEP 668** 规程，在较新的 Linux 发行版上，默认禁用了系统级别的 `pip3 install`。为了确保您系统的安全与完整性，我们直接通过 APT 包管理器安装该组件：

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev
```

### 2. 在 Termux (Android) 上

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. 克隆/下载项目
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🖥 使用方法（推荐方法 - CLI 菜单模式）

交互式 Python 脚本 **`menu.py`** 允许您通过带动画的视觉界面配置并启动 VPN 连接。

```bash
chmod +x menu.py runvpn.sh
./menu.py
```

### 配置文件编辑与管理
就像 Android 上的 HTTP Custom 应用一样，您可以高精度地配置您的隧道和配置文件：

| 主菜单 | SSH 参数设置 |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| 配置文件管理（保存/加载） |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

---

## ⚙️ 手动配置（高级 / 无头模式）

如果您更喜欢在不使用交互式界面的情况下手动配置 VPN，请编辑 [cfgs/settings.ini](cfgs/settings.ini) 文件：

### 支持的连接模式 (`connection_mode`)：
*   `mode 0`：**Direct SSH** — 无中介的原始 SSH 隧道。
*   `mode 1`：**Payload Only** — 通过代理注入自定义 HTTP 头部。
*   `mode 2`：**SNI Only** — 通过伪装 SSL/TLS SNI (Server Name Indication) 绕过深度 packet 检测 (DPI)。
*   `mode 3`：**Payload + SNI** — 最高级别的伪装（HTTP 载荷穿过透明的 SSL 隧道）。

应用配置后，直接启动后台代理：
```bash
sudo ./runvpn.sh
```

---

## 📊 诊断与连接日志

一旦连接，流量传输随即建立，事件将实时显示在您的控制台中：

![成功连接日志](docs/images/connection_logs.png)

> **停止 VPN**：要干净地关闭所有网络隧道并恢复操作系统的默认路由表，只需使用组合键 `Ctrl + C` 即可。

---

## 📄 许可证
该项目采用宽松的 **Apache-2.0** 许可证进行分发。
