import time
import configparser
import re


bg=''
G = bg+'\033[32m'
O = bg+'\033[33m'
GR = bg+'\033[37m'
R = bg+'\033[31m'



class injector():
	def __init__(self):
		pass

	def getpayload(self,config):
		payload = config['Payload']['payload']
		return payload 

	def payloadformating(self,payload,host,port):
		
		payload = payload.replace('[crlf]','\r\n')
		payload = payload.replace('[crlf*2]','\r\n\r\n')
		payload = payload.replace('[cr]','\r')
		payload = payload.replace('[lf]','\n')
		payload = payload.replace('\\r','\r')
		payload = payload.replace('\\n','\n')
		payload = payload.replace('[protocol]','HTTP/1.0')
		payload = payload.replace('[ua]','Dalvik/2.1.0')  
		payload = payload.replace('[raw]',f'CONNECT {host}:{port} HTTP/1.0\r\n\r\n')
		payload = payload.replace('[real_raw]',f'CONNECT {host}:{port} HTTP/1.0\r\n\r\n') 
		payload = payload.replace('[netData]',f'CONNECT {host}:{port} HTTP/1.0')
		payload = payload.replace('[realData]',f'CONNECT {host}:{port} HTTP/1.0')               	
		payload = payload.replace('[split_delay]','[delay_split]')
		payload = payload.replace('[split_instant]','[instant_split]')
		payload = payload.replace('[method]','CONNECT')
		payload = payload.replace('[ssh]',f'{host}:{port}')
		payload = payload.replace('[lfcr]','\n\r')
		payload = payload.replace('[host_port]',f'{host}:{port}')
		payload = payload.replace('[host]',host)
		payload = payload.replace('[port]',port)
		payload = payload.replace('[auth]','')
		payload = payload.replace('[split]' ,'=0.1=')
		payload = payload.replace('[delay_split]'  ,'=0.5=')
		payload = payload.replace('[instant_split]','=0.0=')
		return payload

	def connection(self,client, server,host,port):
	        if int(self.conn_mode(self.conf())) in [ 0, 2]:
	        	return self.get_resp(server=server,client=client)
	        else:
	        	payloads = self.payloadformating(self.getpayload(self.conf()),host,port).split('=')
	        	for payload in payloads:
	        	    if payload in ['0.0','0.5','0.1'] :
	        	        time.sleep(float(payload))
	        	    else:
	        	        server.send(payload.encode())
	        	return self.get_resp(server=server,client=client)

	def get_resp(self,server,client) :
		max_retries = 5
		for attempt in range(max_retries):
			packet = server.recv(2048)
			if not packet:
				self.logs(f'{R}Connection closed by server{GR}')
				return None
			# Direct SSH banner (no HTTP front)
			if packet.startswith(b'SSH-'):
				try:
					status = packet.decode('utf-8','ignore').split('\n')[0]
				except:
					status = packet[:40].decode('utf-8','ignore')
				self.logs(f'{G}response{GR} : {status}')
				return client.send(packet)
			res = packet.decode('utf-8','ignore')
			status = res.split('\n')[0]
			if re.match(r'HTTP/\d(\.\d)? ',status):
				self.logs(f'{G}response{GR} : {status}')
				self.logs("sending auto response \nHTTP/1.1 200 OK")
				client.send(b'HTTP/1.1 200 Ok\r\n\r\n')
				# Server (nginx) often piggybacks SSH banner after HTTP headers
				# in the same segment (curl shows HTTP 200 + SSH-2.0 together).
				# Forward any bytes after \r\n\r\n so SSH banner exchange succeeds.
				header_end = -1
				for sep in (b'\r\n\r\n', b'\n\n'):
					idx = packet.find(sep)
					if idx != -1:
						header_end = idx + len(sep)
						break
				if header_end != -1 and header_end < len(packet):
					remainder = packet[header_end:]
					if remainder.strip():
						# If remainder starts with SSH banner, log it
						if remainder.startswith(b'SSH-'):
							try:
								ssh_line = remainder.decode('utf-8','ignore').split('\n')[0]
								self.logs(f'{G}response{GR} : {ssh_line}')
							except:
								pass
						client.send(remainder)
						return len(remainder)
				continue
			else:
				# Unknown non-HTTP/non-SSH: still unblock corkscrew and wait for SSH
				if status.strip().split('-')[0]=='SSH':
					self.logs(f'{G}response{GR} : {status}')
					return client.send(packet)
				client.send(b'HTTP/1.1 200 Ok\r\n\r\n')
		self.logs(f'{R}Max retries reached waiting for SSH handshake{GR}')
		return None



	
