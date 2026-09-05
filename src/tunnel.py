import socket 
import time
import select
import re
import configparser,sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ssl,certifi
from src.menu_common import read_config, status_snapshot
from .pidkill import handler
from .inject import injector
from src.logger import log_tunnel


bg=''
G = bg+'\033[32m'
O = bg+'\033[33m'
GR = bg+'\033[37m'
R = bg+'\033[31m'
Buffer_lenght = 1024 * 4

class Tun(injector):
	def __init__(self):
		try:
			self.LISTEN_PORT = int(sys.argv[1])
		except (IndexError, ValueError):
			self.LISTEN_PORT = 0
			self.logs(f"{R}Invalid listen port arg '{sys.argv[1] if len(sys.argv)>1 else ''}' — using 0{GR}")

	def conf(self):
		try:
			return read_config()
		except Exception as e:
			self.logs(e)
			raise
		return read_config()

	def extraxt_sni(self,config):
		return status_snapshot(config)['sni_server']

	def gethost(self,config):
		return status_snapshot(config)['ssh_host']

	def proxy(self,config):
		s = status_snapshot(config)
		return [s['proxy_ip'], int(s['proxy_port']) if str(s['proxy_port']).isdigit() else 0]

	def conn_mode(self,config):
		return status_snapshot(config)['mode']
		
	def tunneling(self,client,sockt):
		connected = True
		while connected == True:
			r, _, x = select.select([client,sockt], [], [client,sockt],3)
			for i in r:
				try:
					data = i.recv(Buffer_lenght)
					if not data: connected = False;break
					if i is sockt:
						client.send(data)
					else:
						sockt.send(data)
				except Exception as e:
					self.logs(f'{R} {e}{GR}')
					connected = False;break
		try:
			client.close()
		except: pass
		try:
			sockt.close()
		except: pass
		self.logs("**connection reset by peer")
		return
		
	def destination(self,client, address):
		config = self.conf()
		mode_raw = self.conn_mode(config)
		# v2ray mode should not use injector; if reached here, bail
		if mode_raw == 'v2ray':
			self.logs(f"{R}Injector reached in v2ray mode — closing (v2ray uses sing-box directly){GR}")
			client.close()
			return
		try:
			mode = int(mode_raw)
		except ValueError:
			self.logs(f"{R}Unknown connection mode '{mode_raw}' — closing{GR}")
			client.close()
			return
		sockt = None
		try:
			request = client.recv(1024*4).decode(errors='ignore')
			if not request:
				self.logs(f"{R}Empty request from {address} — closing{GR}")
				client.close()
				return
			# Extract target host:port from CONNECT request
			# CONNECT host:port HTTP/1.1 or similar
			host = self.gethost(config)
			port = None
			# Try to parse CONNECT line
			m = re.search(r'CONNECT\s+([^\s:]+):(\d+)', request)
			if m:
				# Use port from request; host from config is authoritative for SNI/payload routing
				# but keep request host for fallback
				port = m.group(2)
			else:
				# Fallback: last colon split (legacy)
				try:
					port = request.split(':')[-1].split()[0]
					# validate numeric
					int(port)
				except Exception:
					port = None
			if not port:
				# Fallback to ssh port from config
				try:
					port = str(status_snapshot(config)['ssh_port'])
				except:
					port = "22"
			if mode == 2:
				# SNI-only: direct TLS to SSH server (ignore Payload proxy)
				proxip = host
				proxport = port
			else:
				try:
					p = self.proxy(config)
					if p[0] and str(p[0]).strip() and p[1]:
						proxip, proxport = p[0], p[1]
					else:
						raise ValueError("proxy empty")
				except (ValueError, KeyError, TypeError) as e:
					self.logs(f"{O}Proxy config invalid ({e}) — falling back to direct {host}:{port}{GR}")
					proxip = host
					proxport = port
			# Validate proxip/port
			try:
				proxport = int(proxport)
			except:
				proxport = int(port)
			sockt = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			sockt.settimeout(10)
			self.logs(f"Connecting to {O}{proxip}:{proxport}{GR} for mode {mode} (target {host}:{port})")
			sockt.connect((proxip,proxport))
			
			if mode == 2 or mode == 3  :
				SNI_HOST = self.extraxt_sni(config)
				if not SNI_HOST or SNI_HOST in ("None", "—", ""):
					self.logs(f"{R}SNI mode {mode} but SNI host is empty — using {host} as SNI{GR}")
					SNI_HOST = host
				# SNI fronting often uses mismatched certs (e.g. SNI=example.com fronting VPS)
				# Default to insecure (no verify) to allow domain-fronting; user asked to ignore cert
				context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
				context.check_hostname = False
				context.verify_mode = ssl.CERT_NONE
				# still set SNI via server_hostname for fronting, but don't verify
				sockt = context.wrap_socket(sockt,server_hostname=str(SNI_HOST))
				self.logs(f'Handshaked successfully to {SNI_HOST}')
				try:
					self.logs(f"{O}[TCP] Protocol :{G}{sockt.version()} Ciphersuite :{G} {sockt.cipher()[0]} CN={sockt.getpeercert()['subject'][4][0][1]}{GR}")
				except:
					try:
						self.logs(f"{O}[TCP] Protocol :{G}{sockt.version()} Ciphersuite :{G} {sockt.cipher()[0]}{GR}")
					except Exception as e:
						self.logs(f"{R}TLS handshake ok but cipher log failed: {e}{GR}")
				
			if mode == 2:
				client.send(b"HTTP/1.1 200 OK\r\n\r\n")
			packet = injector.connection(self,client, sockt,str(host),str(port))
			if packet:
				self.tunneling(client,sockt)
			else:
				client.close()
				if sockt:
					try: sockt.close()
					except: pass
		except Exception as e:
			self.logs(f'{R}destination error: {e}{GR}')
			try:
				client.close()
			except: pass
			if sockt:
				try: sockt.close()
				except: pass
			return
			
	def create_connection(self):
		# Bind to 127.0.0.1 explicitly — localhost may resolve to ::1 on some hosts
		bind_host = "127.0.0.1"
		sockt = None
		for res in socket.getaddrinfo(bind_host, self.LISTEN_PORT, socket.AF_UNSPEC,socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
			af, socktype, proto, canonname, sa = res
			try:
				sockt = socket.socket(af, socktype, proto)
				sockt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			except OSError as msg:
				sockt = None
				continue
			try:
				sockt.bind((bind_host,self.LISTEN_PORT))
				sockt.listen(128)
				self.logs(f"Injector listening on {bind_host}:{self.LISTEN_PORT}")
			except OSError as msg:
				try:
					sockt.close()
				except Exception:
					pass
				sockt = None
				continue
			break
		if sockt is None:
			self.logs(f'{R}Coudn\'t open socket on port {self.LISTEN_PORT}: address in use{GR}')
			print('Coudn\'t open socket ')
			sys.exit(1)
		
		while True:
			try:
				client, address = sockt.accept()
				self.logs("Connected to local address")
				# handle in same thread (sequential) — matches original behavior
				# For concurrency, could spawn thread, but keep simple
				self.destination(client,address)
			except Exception as e:
				self.logs(f"Accept loop error: {e}")
				sys.exit(0)
				   
	def logs(self,log):
		log_tunnel(str(log))
if __name__=='__main__':
	start = Tun()
	start.create_connection()
