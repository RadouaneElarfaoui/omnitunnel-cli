import sys,os,re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import subprocess
import socket
import time
import configparser
import random
import threading
from src.logger import log_ssh, log_singbox, log_tunnel, log_error


# colors
bg=''
G = bg+'\033[32m'
O = bg+'\033[33m'
GR = bg+'\033[37m'
R = bg+'\033[31m'

class sshRunn:
    def __init__(self,inject_port):
        self.inject_host = '127.0.0.1'
        self.inject_port = inject_port
        self.connected = None
        self.path = os.path.abspath(os.path.curdir)

    def LogServeMsg(self,lines):
        slicemsg = lines[lines.index("debug1: SSH2_MSG_SERVICE_ACCEPT received\r\n") : lines.index('debug1: Next authentication method: publickey\r\n')]
        msg = "".join(x for x in slicemsg)
        self.logs(msg)

    def ssh_client(self,host,port,password,mode,auth_methode):
            try:
                socks5_port = 1080
                dynamic_port_forwarding = '-CND {}'.format(socks5_port)	
                inject_host= self.inject_host
                inject_port= self.inject_port
                nc_proxies_mode = [f'nc -X CONNECT -x {inject_host}:{inject_port} %h %p',f'corkscrew {inject_host} {inject_port} %h %p']


                if mode =='0':
                    self.logs("Connecting Using Direct SSH " )
                    proxycmd =''
                else:
                    proxycmd = random.choice([f'-o "ProxyCommand={nc_proxies_mode[1]}"',f'-o "ProxyCommand={nc_proxies_mode[0]}"'])

                if self.enableCompress=='y':
                        compress = "-C"
                else:
                    compress =""
                if str(auth_methode) == "publickey":  
                    sshcmd = f"ssh -i {password} cfgs/publickey.pem {proxycmd} useless@{host}"
                    ssh_env = os.environ.copy()
                else:
                    sshcmd = f"sshpass -e ssh {proxycmd} -F configFile host1"
                    ssh_env = {**os.environ, 'SSHPASS': password}
                perf_opts = "-o Ciphers=chacha20-poly1305@openssh.com,aes128-gcm@openssh.com,aes256-gcm@openssh.com"
                response = subprocess.Popen(
                (
                        f'{sshcmd} {compress} {perf_opts} -p {port} -v {dynamic_port_forwarding} -o ConnectTimeout=3 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                ),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=ssh_env)
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
                    elif 'Next authentication method: password' in line:self.logs(G+'Authenticate to password'+GR)
                    elif 'Authentication succeeded (password).' in line:self.logs('Authentication Comleted')
                    elif 'Permission denied' in line:self.logs(R+'username or password are inncorect '+GR)
                    elif 'Connection closed' in line:self.logs(R+'Connection closed ' +GR)
                    elif 'Could not request local forwarding' in line:self.logs(R+'Port used by another programs '+GR)
                    elif 'Next authentication method: publickey' in line:
                        self.logs(line)
                    elif 'Entering interactive session.' in line:
                        self.logs(f'{G}connected{GR}')
                        self.connected=True
                    elif not re.match(r'^debug\d*:', stripped) and (
                              'error' in line.lower() or 'refused' in line.lower()
                              or 'not found' in line.lower() or 'could not resolve' in line.lower()
                              or 'no route' in line.lower() or 'timed out' in line.lower()
                              or 'invalid' in line.lower() or 'disabled' in line.lower()
                              or 'no such file' in line.lower()):
                        self.logs(R + stripped + GR)

                    if self.connected:
                        self._launch_engine()
                        self.connected=False

                # ssh process ended; if we never connected and it failed, show why
                response.wait()
                if not self.connected and response.returncode:
                    self.logs(R + f"SSH exited with code {response.returncode}" + GR)

            except KeyboardInterrupt:
                return None
            except Exception as error:
                print(error)
    def createConf(self,host,user):
            _=subprocess.run(["sh","ConfMake",host,user])

    def _launch_engine(self):
        engine = getattr(self, 'engine_mode', 'singbox')
        if engine == 'singbox':
            script = "vpn/singbox_proxification"
            logger = log_singbox
        else:
            script = "vpn/proxification"
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

    def create_connection(self,host,port,user,password,mode,auth_methode ):
        try:
            regx = r'[a-zA-Z0-9_]'
            if mode in ('0', '2') or not (self.proxy[0] and self.proxy[0].strip()):
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
                self.logs(f"Connected to : {O}{remote_addr}\n{GR}sending Payload :{O}{payload}{GR}")
            else:
                self.logs(f"Connected to : {O}{remote_addr}{GR}")

            if re.match(regx,host):
                try:
                    host = socket.gethostbyname(host)
                except socket.gaierror as e:
                    self.logs(f"DNS resolution warning for '{host}': {e}")

            self.createConf(host,user)					

            self.ssh_client(host,port,password,mode, auth_methode)

        except ConnectionRefusedError:     
            self.logs("CONNECTION REFUSED")
        except Exception as e:
            print(e)    


    def logs(self,log):
        log_ssh(str(log))

    def main(self):

        currentdir = os.path.abspath(os.path.curdir)
        config = configparser.ConfigParser()
        with open(f'{currentdir}/cfgs/settings.ini') as _cfg_fh:
            config.read_file(_cfg_fh)	
        host = config['ssh']['host']
        mode = config['mode']['connection_mode']
        port = config['ssh']['port']
        user = config['ssh']['username']
        password = config['ssh']['password']
        self.enableCompress = config['ssh']['enable_compression']
        auth_methode = config['ssh']['auth_methode']
        self.engine_mode = config.get('engine', 'engine_mode', fallback='singbox')

        self.payload = config['Payload']['payload']
        self.proxy =(config['Payload']['proxyip'],config['Payload']['proxyport'])
        if mode in ("2" , "3"):
            self.sni = config['sni']['server_name']
        else:
            self.sni = False
        self.create_connection(host,port,user,password,mode,auth_methode)



localport= sys.argv[1]
start = sshRunn(localport)
start.main()

