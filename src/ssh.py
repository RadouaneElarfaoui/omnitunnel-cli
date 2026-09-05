import sys,os,re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import subprocess
import socket
import time
import configparser
import random
import shutil
import threading
from src.logger import log_ssh, log_singbox, log_tunnel, log_error
from src.paths import PROJECT_DIR
from src.menu_common import read_config, status_snapshot


# colors
bg=''
G = bg+'\033[32m'
O = bg+'\033[33m'
GR = bg+'\033[37m'
R = bg+'\033[31m'

# placeholders that indicate unconfigured profile
PLACEHOLDERS = {"vps.example.com", "proxy.example.com", "your_username", "your_password", "None", "", "—"}

MODE_LABELS = {
    '0': 'Direct SSH',
    '1': 'HTTP Payload',
    '2': 'TLS/SNI',
    '3': 'TLS + HTTP Payload',
}

class sshRunn:
    def __init__(self,inject_port):
        self.inject_host = '127.0.0.1'
        self.inject_port = inject_port
        self.connected = False
        self.ever_connected = False
        self._engine_launched = False
        self.path = PROJECT_DIR

    def LogServeMsg(self,lines):
        try:
            slicemsg = lines[lines.index("debug1: SSH2_MSG_SERVICE_ACCEPT received\r\n") : lines.index('debug1: Next authentication method: publickey\r\n')]
            msg = "".join(x for x in slicemsg)
            self.logs(msg)
        except Exception:
            pass

    def _resolve_key_file(self, password_field):
        """Resolve private key path for publickey auth.

        Priority:
          1) if password_field is an existing file path, use it
          2) common project locations
          3) ~/.ssh/ keys
        Returns path or None.
        """
        candidates = []
        if password_field:
            expanded = os.path.expanduser(password_field.strip())
            if os.path.isfile(expanded):
                return expanded
            # also check as relative to PROJECT_DIR
            rel = os.path.join(PROJECT_DIR, expanded)
            if os.path.isfile(rel):
                return rel
        # project candidates
        for name in ["privatekey.pem", "publickey.pem", "id_rsa", "id_ed25519", "id_ecdsa"]:
            p = os.path.join(PROJECT_DIR, "cfgs", name)
            if os.path.isfile(p):
                candidates.append(p)
            p2 = os.path.join(PROJECT_DIR, name)
            if os.path.isfile(p2):
                candidates.append(p2)
        # home ssh candidates
        home = os.path.expanduser("~")
        for name in ["id_ed25519", "id_rsa", "id_ecdsa", "id_ed25519_sk", "id_rsa_sk"]:
            p = os.path.join(home, ".ssh", name)
            if os.path.isfile(p):
                candidates.append(p)
        if candidates:
            return candidates[0]
        return None

    def _is_placeholder(self, val):
        return not val or str(val).strip() in PLACEHOLDERS

    def _validate_config(self, host, port, user, password, mode, auth_method):
        errors = []
        if self._is_placeholder(host):
            errors.append(f"SSH host is placeholder '{host}' — edit SSH Host")
        if self._is_placeholder(str(port)) or str(port) == "None":
            errors.append(f"SSH port is placeholder '{port}' — edit SSH Port")
        else:
            try:
                p = int(port)
                if not (1 <= p <= 65535):
                    errors.append(f"SSH port out of range: {port}")
            except ValueError:
                errors.append(f"SSH port is not numeric: {port}")
        if self._is_placeholder(user):
            errors.append(f"SSH username is placeholder '{user}' — edit SSH Username")
        if auth_method == "password" and self._is_placeholder(password):
            errors.append("SSH password is placeholder — edit SSH Password")
        if auth_method == "publickey":
            key = self._resolve_key_file(password)
            if not key:
                errors.append("Publickey auth selected but no private key file found (checked cfgs/privatekey.pem, cfgs/publickey.pem, ~/.ssh/id_* and password field as path)")
            else:
                # check permissions
                try:
                    if os.stat(key).st_mode & 0o077:
                        self.logs(f"{O}Warning: key {key} is group/world readable — ssh may reject it (chmod 600){GR}")
                except Exception:
                    pass
        if mode in ("2", "3") and self._is_placeholder(self.sni):
            errors.append(f"SNI host is placeholder '{self.sni}' — edit SNI Host for TLS modes")
        if mode in ("1", "3") and (self._is_placeholder(self.proxy[0]) or self._is_placeholder(str(self.proxy[1]))):
            # proxy placeholder is common in example; warn not hard fail for mode 3 TLS+HTTP
            self.logs(f"{O}Warning: Proxy is placeholder {self.proxy} — HTTP payload modes 1/3 will fail{GR}")
        return errors

    def ssh_client(self,host,port,user,password,mode,auth_method):
            try:
                socks5_port = 1080
                dynamic_port_forwarding = '-CND {}'.format(socks5_port)
                inject_host= self.inject_host
                inject_port= self.inject_port
                nc_proxies_mode = [f'nc -X CONNECT -x {inject_host}:{inject_port} %h %p',f'corkscrew {inject_host} {inject_port} %h %p']

                mode_label = MODE_LABELS.get(str(mode), str(mode))
                if mode == '0':
                    self.logs(f"Mode: {O}{mode_label} (direct) {GR}— connecting directly to {O}{host}:{port}{GR}")
                    proxycmd =''
                else:
                    # fallback to nc if corkscrew not installed
                    proxy_cmd = nc_proxies_mode[0] if shutil.which("corkscrew") is None else random.choice(nc_proxies_mode)
                    proxycmd = f'-o ProxyCommand="{proxy_cmd}"'
                    via = f"{inject_host}:{inject_port}"
                    self.logs(f"Mode: {O}{mode_label}{GR} via injector {O}{via}{GR} ProxyCommand={proxy_cmd}")

                if str(self.enableCompress).lower() == 'y':
                    compress = "-C"
                else:
                    compress =""

                # Build ssh command correctly
                perf_opts = "-o Ciphers=chacha20-poly1305@openssh.com,aes128-gcm@openssh.com,aes256-gcm@openssh.com"
                base_opts = f"{perf_opts} -p {port} -v {dynamic_port_forwarding} -o ConnectTimeout=8 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -o ServerAliveCountMax=3"

                if str(auth_method) == "publickey":
                    key_file = self._resolve_key_file(password)
                    if not key_file:
                        self.logs(R + "Publickey auth selected but no private key file found — aborting" + GR)
                        self.logs(R + "Hint: place key at cfgs/privatekey.pem or set password field to key path, or switch auth to password" + GR)
                        return
                    self.logs(f"Auth: {O}publickey{GR} user={O}{user}{GR} key={O}{key_file}{GR} host={O}{host}:{port}{GR}")
                    sshcmd = f"ssh -i {key_file} -o IdentitiesOnly=yes {proxycmd} {compress} {base_opts} {user}@{host}"
                    ssh_env = os.environ.copy()
                    # clear SSHPASS if present
                    ssh_env.pop('SSHPASS', None)
                else:
                    self.logs(f"Auth: {O}password{GR} user={O}{user}{GR} host={O}{host}:{port}{GR}")
                    # sshpass -e reads SSHPASS env
                    sshcmd = f"sshpass -e ssh {proxycmd} {compress} {base_opts} {user}@{host}"
                    ssh_env = {**os.environ, 'SSHPASS': password}

                # Debug: log the effective command without password
                safe_cmd = sshcmd
                if 'SSHPASS' in ssh_env:
                    safe_cmd = sshcmd + "  [SSHPASS=***]"
                self.logs(f"Executing: {safe_cmd}")

                response = subprocess.Popen(
                    sshcmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    env=ssh_env)

                # Track whether we ever reached interactive session
                self.connected = False
                self.ever_connected = False
                self._engine_launched = False

                for line in response.stdout:
                    line = line.decode('utf-8',errors='ignore')
                    stripped = line.strip()
                    if not stripped:
                        continue

                    if 'compat_banner: no match:' in line:
                        self.logs(f"{G}handshake starts\nserver :{line.split(':')[2]}")
                    elif 'Server host key' in line:self.logs(line)
                    elif 'kex: algorithm:' in line:self.logs(line)
                    elif 'kex: host key algorithm:' in line:self.logs(line)
                    elif 'kex: server->client cipher:' in line:self.logs(line)
                    elif 'Next authentication method: password' in line:self.logs(G+'Authenticating with password'+GR)
                    elif 'Next authentication method: publickey' in line:self.logs(G+'Trying publickey authentication'+GR)
                    elif 'Authentication succeeded' in line:self.logs(G+'Authentication succeeded'+GR)
                    elif 'Permission denied' in line:
                        if str(auth_method) == "publickey":
                            self.logs(R+'Publickey authentication failed — check key file and username'+GR)
                        else:
                            self.logs(R+'Username or password are incorrect'+GR)
                    elif 'No such file or directory' in line and 'publickey' in auth_method:
                        # ignore benign known_hosts misses that always appear with -v + StrictHostKeyChecking=no
                        if 'load_hostkeys' in line or 'ssh_known_hosts' in line:
                            continue
                        self.logs(R+f'Key file error: {stripped}'+GR)
                    elif 'Could not resolve hostname' in line:
                        self.logs(R+f'DNS error: {stripped}'+GR)
                    elif 'Connection timed out' in line or 'timed out' in line.lower():
                        self.logs(R+f'Timeout: {stripped}'+GR)
                    elif 'Connection closed' in line:self.logs(R+'Connection closed '+GR)
                    elif 'Connection refused' in line:self.logs(R+'Connection refused — check host/port and SNI/proxy'+GR)
                    elif 'Could not request local forwarding' in line:self.logs(R+'Port 1080 already in use — another tunnel running?'+GR)
                    elif 'Entering interactive session.' in line:
                        self.logs(f'{G}Connected — entering interactive session{GR}')
                        self.connected=True
                        self.ever_connected=True
                    elif not re.match(r'^debug\d*:', stripped) and (
                              'error' in line.lower() or 'refused' in line.lower()
                              or 'not found' in line.lower() or 'could not resolve' in line.lower()
                              or 'no route' in line.lower() or 'timed out' in line.lower()
                              or 'invalid' in line.lower() or 'disabled' in line.lower()
                              or 'no such file' in line.lower()):
                        # suppress benign known_hosts probe
                        if 'load_hostkeys' in stripped or 'ssh_known_hosts' in stripped:
                            continue
                        self.logs(R + stripped + GR)

                    if self.connected and not self._engine_launched:
                        self._launch_engine()
                        self._engine_launched = True

                response.wait()
                if self.ever_connected:
                    if response.returncode == 0:
                        self.logs(G + "SSH session ended cleanly" + GR)
                    else:
                        self.logs(R + f"SSH session ended with code {response.returncode}" + GR)
                else:
                    if response.returncode:
                        self.logs(R + f"SSH failed with code {response.returncode} — check host/port/auth/SNI/proxy" + GR)
                        # hint for common misconfig
                        if str(mode) in ('2','3') and self._is_placeholder(self.sni):
                            self.logs(R + "TLS mode selected but SNI is placeholder — set real SNI host" + GR)
                        if str(auth_method) == "publickey" and response.returncode == 255:
                            self.logs(R + "Publickey failure: verify key permissions (chmod 600) and username" + GR)

            except KeyboardInterrupt:
                return None
            except Exception as error:
                log_error(f"SSH client error: {error}")
                print(error)

    def _launch_engine(self):
        engine = getattr(self, 'engine_mode', 'singbox')
        if engine == 'singbox':
            script = os.path.join(PROJECT_DIR, "vpn/singbox_proxification")
            logger = log_singbox
        else:
            script = os.path.join(PROJECT_DIR, "vpn/proxification")
            logger = log_tunnel
        self.logs(f"Launching {engine} engine...")
        # Engine needs root (iptables/TUN), so elevate via sudo; run in background
        # and stream its output through the logger instead of discarding it.
        proc = subprocess.Popen(
            ["sudo", "-E", "bash", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        def _stream():
            try:
                for line in proc.stdout:
                    line = line.rstrip()
                    if line:
                        logger(line)
            except Exception as e:
                log_error(f"Engine output error: {e}")

        threading.Thread(target=_stream, daemon=True).start()
        return proc

    def create_connection(self,host,port,user,password,mode,auth_method ):
        try:
            # Determine remote display
            if mode in ('0', '2') or not (self.proxy[0] and str(self.proxy[0]).strip()):
                remote_addr = (host, port)
            else:
                remote_addr = self.proxy
            if mode in ("1" ,"3"):
                payload = self.payload.replace("[host]",host)
            else:
                payload = ""
            if self.sni:
                self.logs(f"SNI : {O}{self.sni}{GR}")
            if payload:
                self.logs(f"Target : {O}{remote_addr}{GR} via {O}{MODE_LABELS.get(str(mode),mode)}{GR}")
                self.logs(f"Sending Payload :{O}{payload[:120]}{GR}")
            else:
                self.logs(f"Target : {O}{remote_addr}{GR} via {O}{MODE_LABELS.get(str(mode),mode)}{GR}")

            # Validate before network ops
            errors = self._validate_config(host, port, user, password, mode, auth_method)
            for err in errors:
                self.logs(R + err + GR)
            if errors:
                # hard errors block connection; warnings already logged
                if any("placeholder" in e and "Proxy" not in e for e in errors):
                    self.logs(R + "Aborting: fix placeholder config before connecting (Edit menu)" + GR)
                    return
                if any("no private key" in e.lower() for e in errors):
                    return

            # DNS pre-check: only for direct modes, and only if host is not IP
            # Keep original hostname for SSH; log IP if resolvable
            try:
                # check if host is already IP
                socket.inet_aton(host)
                # is IP, skip
            except OSError:
                # is hostname - try to resolve for early feedback, but don't replace host
                # (keep hostname for SNI/ProxyCommand %h)
                try:
                    ip = socket.gethostbyname(host)
                    self.logs(f"DNS: {O}{host} -> {ip}{GR}")
                except socket.gaierror as e:
                    self.logs(R + f"DNS resolution failed for '{host}': {e} — check host/SNI/proxy" + GR)
                    # continue anyway; ssh will report better

            self.ssh_client(host,port,user,password,mode, auth_method)

        except ConnectionRefusedError:     
            self.logs("CONNECTION REFUSED")
        except Exception as e:
            log_error(f"create_connection error: {e}")
            print(e)    


    def logs(self,log):
        log_ssh(str(log))

    def main(self):
        config = read_config()
        s = status_snapshot(config)
        host = s['ssh_host']
        mode = s['mode']
        port = s['ssh_port']
        user = s['ssh_user']
        password = config.get('ssh', 'password', fallback='')
        self.enableCompress = s['ssh_compress']
        auth_method = s['ssh_auth']
        self.engine_mode = s['engine_mode']
        self.payload = s['payload']
        self.proxy = (s['proxy_ip'], s['proxy_port'])
        self.sni = s['sni_server'] if mode in ("2", "3") else False
        self.create_connection(host,port,user,password,mode,auth_method)



localport= sys.argv[1] if len(sys.argv) > 1 else "0"
start = sshRunn(localport)
start.main()
