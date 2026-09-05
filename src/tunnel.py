import socket 
import time
import select
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
		self.LISTEN_PORT = int(sys.argv[1])

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
		return [s['proxy_ip'], int(s['proxy_port'])]

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
		client.close()
		sockt.close()
		self.logs("**connection reset by peer")
		return
		
	def destination(self,client, address):
		config = self.conf()
		mode = int(self.conn_mode(config))
		sockt = None
		try:
			request = client.recv(1024*4).decode()
			host = self.gethost(config)
			port = request.split(':')[-1].split()[0]
			if mode == 2:
				# SNI-only: direct TLS to SSH server (ignore Payload proxy)
				proxip = host
				proxport = port
			else:
				try:
					proxip=self.proxy(config)[0] 
					proxport=self.proxy(config)[1]
				except (ValueError, KeyError):
					proxip = host
					proxport = port
			sockt = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
			sockt.settimeout(10)
			sockt.connect((proxip,int(proxport)))
			
			if mode == 2 or mode == 3  :
				SNI_HOST = self.extraxt_sni(config)
				context = ssl.SSLContext(ssl.PROTOCOL_TLS)
				context.verify_mode  = ssl.CERT_REQUIRED
				context.load_verify_locations(
				cafile=os.path.relpath(certifi.where()),
				capath=None,cadata=None)
				sockt = context.wrap_socket(sockt,server_hostname=str(SNI_HOST))
				self.logs(f'Handshaked successfully to {SNI_HOST}')
				try:
					self.logs(f"{O}[TCP] Protocol :{G}{sockt.version()} Ciphersuite :{G} {sockt.cipher()[0]} CN={sockt.getpeercert()['subject'][4][0][1]}{GR}")
				except:
					self.logs(f"{O}[TCP] Protocol :{G}{sockt.version()} Ciphersuite :{G} {sockt.cipher()[0]}{GR}")
				
			if mode == 2:
				client.send(b"HTTP/1.1 200 OK\r\n\r\n")
			packet = injector.connection(self,client, sockt,str(host),str(port))
			if packet:
				self.tunneling(client,sockt)
			else:
				client.close()
				if sockt:
					sockt.close()
		except Exception as e:
			self.logs(f'{e}')
			client.close()
			if sockt:
				sockt.close()
			return
			
	def create_connection(self):
		for res in socket.getaddrinfo(socket.gethostbyname("localhost"), self.LISTEN_PORT, socket.AF_UNSPEC,socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
			af, socktype, proto, canonname, sa = res
			try:
				sockt = socket.socket(af, socktype, proto)
				sockt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			except OSError as msg:
				sockt = None
				continue
			try:
				localAddress = socket.gethostbyname("localhost")
				sockt.bind((localAddress,self.LISTEN_PORT))
				sockt.listen(1)
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
				destination_thread = self.destination(client,address)
			except Exception as e:
				self.logs(f"Accept loop error: {e}")
				sys.exit(0)
				   
	def logs(self,log):
		log_tunnel(str(log))
if __name__=='__main__':
	start = Tun()
	start.create_connection()
