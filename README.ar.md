[English](README.md) | [Français](README.fr.md) | [Español](README.es.md) | [العربية](README.ar.md) | [Português](README.pt.md) | [中文](README.zh.md)

# OmniTunnel CLI (v1.1.0)

[![GitHub license](https://img.shields.io/github/license/RadouaneElarfaoui/omnitunnel-cli?style=flat-square)](LICENSE)
[![Platform Compatibility](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Debian%20%7C%20Termux-blue?style=flat-square)](#المتطلبات-والتثبيت)

**OmniTunnel CLI** هو عميل VPN يعمل عبر سطر الأوامر ويعتمد على أنفاق SSH قوية، مصمم لتجاوز قيود الشبكة وتحسين أمان اتصالك على أنظمة **Linux (Ubuntu/Debian)** و **Android (Termux)**.

---

## 🚀 الجديد في الإصدار v1.0.2

*   **قائمة تفاعلية بلغة بايثون (`menu.py`)**: واجهة حديثة لسطر الأوامر (CLI) لتعديل وإدارة ملفات التعريف، الحمولة (payloads)، وبيانات اعتماد SSH بسلاسة ودون الحاجة لتعديل ملفات ini الخام يدويًا.
*   **توافقية SSH محسنة**: دعم صريح للمجموعات التشفيرية وخوارزميات تبادل المفاتيح الحديثة (`+ssh-rsa`، `ssh-ed25519`، `ecdsa`، `rsa-sha2`) لحل مشكلات حظر الاتصال على توزيعات لينكس الحديثة (Ubuntu 22.04+، Debian 12+).
*   **إغلاق آمن ومعالجة الإشارات**: دمج معالجات `trap` النظام في برمجية التشغيل لتنظيف وإنهاء جميع العمليات التابعة (`redsocks`، `dns2socks`، `ssh`) بشكل نظيف عند المقاطعة (`Ctrl+C`).
*   **بناء قوي ومعزول**: تحديث سكربت `runvpn.sh` لبناء وتجميع الاعتمادات المفقودة ديناميكيًا وتلقائيًا، وعزلها بأمان داخل المجلد `./bin` دون التأثير على شجرة المجلدات العامة للنظام.
*   **مرونة شبكة معززة**: إدارة متقدمة لحلقة الاستماع، وكشف فعال للمقابس (sockets) المغلقة من قبل الخادم البعيد لمنع الانهيارات وتسرب واصفات الملفات (file descriptors).

---

## 🛠 المتطلبات والتثبيت

### 1. على أنظمة Debian و Ubuntu و Linux Mint

وفقًا لتوجيه **PEP 668** المتعلق ببيئات بايثون المدارة خارجيًا، يتم حظر استخدام الأمر `pip3 install` على مستوى النظام افتراضيًا في توزيعات لينكس الحديثة. لضمان أمان النظام وسلامته، نقوم بتثبيت المكونات مباشرة عبر مدير الحزم APT:

```bash
sudo apt update
sudo apt install -y git openssh-client sshpass netcat-openbsd corkscrew screen python3 python3-pip python3-certifi make libevent-dev
```

### 2. على تطبيق Termux (أندرويد)

```bash
pkg update
pkg install -y git openssh sshpass netcat-openbsd corkscrew screen python3 make libevent
pip install certifi
```

### 3. تحميل المشروع
```bash
git clone https://github.com/RadouaneElarfaoui/omnitunnel-cli.git
cd omnitunnel-cli
```

---

## 🖥 الاستخدام (الطريقة الموصى بها - وضع قائمة CLI)

يتيح لك السكربت التفاعلي المكتوب بلغة بايثون **`menu.py`** تهيئة وتشغيل اتصال الـ VPN الخاص بك بواجهة مرئية متحركة.

```bash
chmod +x menu.py runvpn.sh
./menu.py
```

### محرر وإدارة ملفات التعريف
تمامًا مثل تطبيق HTTP Custom على نظام أندرويد، قم بتهيئة الأنفاق وملفات التعريف الخاصة بك بدقة عالية:

| القائمة الرئيسية | تعديل إعدادات SSH |
| :---: | :---: |
| ![Main Menu](docs/images/main_menu.png) | ![SSH Parameters](docs/images/ssh_parameters_menu.png) |

| إدارة ملفات التعريف (حفظ/تحميل) |
| :---: |
| ![Manage Configurations](docs/images/manage_configurations_menu.png) |

---

## ⚙️ الإعداد اليدوي (متقدم / بدون واجهة)

إذا كنت تفضل تهيئة الـ VPN يدويًا دون استخدام الواجهة التفاعلية، فقم بتعديل الملف [cfgs/settings.ini](cfgs/settings.ini):

### أوضاع الاتصال المدعومة (`connection_mode`):
*   `mode 0`: **Direct SSH** — نفق SSH خام مباشر بدون وسطاء.
*   `mode 1`: **Payload Only** — حقن ترويسات HTTP المخصصة عبر البروكسي.
*   `mode 2`: **SNI Only** — تجاوز فحص الحزم العميق (DPI) عبر تزييف مؤشر اسم الخادم (SNI - Server Name Indication).
*   `mode 3`: **Payload + SNI** — أقصى مستوى من التخفي (حمولة HTTP تمر عبر نفق SSL شفاف).

بمجرد تطبيق الإعدادات، قم بتشغيل عميل الخلفية مباشرة:
```bash
sudo ./runvpn.sh
```

---

## 📊 التشخيصات وسجل الاتصال

بمجرد الاتصال، يتم تأسيس تدفق البيانات وتظهر الأحداث في الوقت الفعلي على شاشتك:

![سجلات اتصال ناجح](docs/images/connection_logs.png)

> **إيقاف الـ VPN**: لإيقاف جميع أنفاق الشبكة بشكل نظيف واستعادة جدول التوجيه الافتراضي لنظام التشغيل الخاص بك، ما عليك سوى استخدام اختصار المفاتيح `Ctrl + C`.

---

## 📄 الترخيص
يتم توزيع هذا المشروع بموجب ترخيص **Apache-2.0** المرن.
