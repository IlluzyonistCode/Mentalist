import requests
import socket
import ssl
import hashlib
import json
import hmac
import psutil
import os
import sys
import platform
import base64
import time
import random
import uuid
import inspect
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from urllib.parse import urlparse
from functools import wraps
from datetime import datetime
from dotenv import dotenv_values
from colorama import Back, Fore, Style, init
from auth_protection import AntiDebug, WindowsAntiDebug, _integrity_checker, _global_protection

init(autoreset=True)

_auth_session_cache = None
EXPECTED_SPKI_HASH = 'gMjirtN/00VjGvJ6KPE70oOy+BV3gn6RZPaT9Qh38/w='


class AuthenticationError(Exception):
	pass


class DataEntanglement:
	@staticmethod
	def decrypt_critical_data(encrypted_data, decryption_key):
		try:
			corruption_handler = _integrity_checker.get_corruption_handler()
			
			if corruption_handler.is_phantom_mode():
				return DataEntanglement._phantom_decrypt(encrypted_data, decryption_key)
			
			key_bytes = bytes.fromhex(decryption_key)
			data_bytes = base64.b64decode(encrypted_data)
			decrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes)])
			
			return decrypted.decode('utf-8')
		except:
			pass
	
	@staticmethod
	def _phantom_decrypt(encrypted_data, phantom_key):
		corruption_handler = _integrity_checker.get_corruption_handler()
		fake_result = corruption_handler.phantom_decrypt(encrypted_data, phantom_key)
		
		time.sleep(random.uniform(0.5, 1.5))
		
		return fake_result
	
	@staticmethod
	def get_integrity_key():
		key = _integrity_checker.get_decryption_key()
		_integrity_checker.apply_temporal_poison()
		
		return key
	
	@staticmethod
	def validate_and_decrypt(encrypted_payload):
		key = DataEntanglement.get_integrity_key()
		result = DataEntanglement.decrypt_critical_data(encrypted_payload, key)
		
		corruption_handler = _integrity_checker.get_corruption_handler()
		
		if corruption_handler.is_phantom_mode():
			fake_data = corruption_handler.generate_plausible_lie('json')
			
			return json.dumps(fake_data)
		
		if result is None:
			time.sleep(random.uniform(5, 15))
			sys.exit(1)

		return result


class AuthClient:
	def __init__(self, server_url, api_key):
		self.server_url = server_url.rstrip('/')
		self.api_key = api_key
		self.session = requests.Session()
		self.authenticated = False
		self.permissions = 0
		self.user_id = None
		self._crypto_key = None
		
		requests.packages.urllib3.disable_warnings()
		
		self._verify_connection_integrity()
		
		if self.server_url.startswith('https'):
			self._enforce_ssl_pinning()

		_global_protection.store_key('server_url', server_url)
		_global_protection.store_key('api_key', api_key)

	def _verify_connection_integrity(self):
		try:
			if AntiDebug.check_trace():
				_integrity_checker._enter_ghost_mode('trace_in_connection')
			
			if WindowsAntiDebug.check_all():
				_integrity_checker._enter_ghost_mode('debug_in_connection')

			requests_file = inspect.getfile(requests)

			valid_paths = [
				'site-packages',
				'dist-packages',
				'_MEI'
			]

			is_valid = any(path in requests_file for path in valid_paths)

			if not is_valid:
				_integrity_checker._enter_ghost_mode('suspicious_requests_module')

			if AntiDebug.cpu_trap(): 
				_integrity_checker._enter_ghost_mode('cpu_timing_violation')
		except:
			pass

	def _enforce_ssl_pinning(self):
		try:
			parsed = urlparse(self.server_url)
			host = parsed.hostname
			port = parsed.port or 443

			ctx = ssl.create_default_context()
			ctx.check_hostname = False
			ctx.verify_mode = ssl.CERT_NONE

			with socket.create_connection((host, port), timeout=5) as sock:
				with ctx.wrap_socket(sock, server_hostname=host) as ssock:
					cert_bin = ssock.getpeercert(binary_form=True)

			cert = x509.load_der_x509_certificate(cert_bin, default_backend())
			pubkey_der = cert.public_key().public_bytes(
				encoding=serialization.Encoding.DER,
				format=serialization.PublicFormat.SubjectPublicKeyInfo
			)

			spki_hash = base64.b64encode(
				hashlib.sha256(pubkey_der).digest()
			).decode()

			if spki_hash != EXPECTED_SPKI_HASH:
				_integrity_checker._enter_ghost_mode('ssl_spki_mismatch')

				return
		except Exception as e:
			print(e)
			corruption_handler = _integrity_checker.get_corruption_handler()
			
			if corruption_handler.is_phantom_mode():
				return

			sys.exit(1)

	def get_system_info(self):
		try:
			entanglement = _integrity_checker.get_entanglement_engine()
			corruption_handler = _integrity_checker.get_corruption_handler()
			
			hostname = socket.gethostname()
			
			try:
				local_ip = socket.gethostbyname(hostname)
			except:
				local_ip = 'unknown'

			mac_address = self._get_mac_address()
			cpu_count = psutil.cpu_count(logical=True)
			cpu_count_physical = psutil.cpu_count(logical=False)
			memory = psutil.virtual_memory()
			disk = psutil.disk_usage('/')
			process = psutil.Process(os.getpid())

			base_info = {
				'platform': platform.system(),
				'platform_release': platform.release(),
				'platform_version': platform.version(),
				'architecture': platform.machine(),
				'processor': platform.processor(),
				'python_version': platform.python_version(),
				'python_implementation': platform.python_implementation(),
				'hostname': hostname,
				'local_ip': local_ip,
				'mac_address': mac_address,
				'cpu_count': cpu_count,
				'cpu_count_physical': cpu_count_physical,
				'ram_total_gb': round(memory.total / (1024**3), 2),
				'disk_total_gb': round(disk.total / (1024**3), 2),
				'process_id': process.pid,
				'process_name': process.name(),
				'process_cwd': process.cwd(),
				'user': os.getenv('USER') or os.getenv('USERNAME'),
				'home_dir': os.path.expanduser('~'),
				'collected_at': datetime.now().isoformat()
			}
			
			if corruption_handler.is_phantom_mode():
				return entanglement.corrupt_statistical_data(base_info)
			
			return base_info
		except:
			return {
				'platform': platform.system(),
				'error': 'partial_collection',
				'collected_at': datetime.now().isoformat()
			}

	def _get_mac_address(self):
		try:
			mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
						for elements in range(0, 2*6, 2)][::-1])

			return mac
		except:
			return 'unknown'

	@AntiDebug.timing_check(threshold=0.05)
	def _generate_challenge_response(self, challenge):
		_integrity_checker.apply_temporal_poison()
		
		return hmac.new(
			self.api_key.encode('utf-8'),
			challenge.encode('utf-8'),
			hashlib.sha256
		).hexdigest()

	def authenticate(self):
		try:
			_integrity_checker.verify_integrity()
			
			corruption_handler = _integrity_checker.get_corruption_handler()
			
			if corruption_handler.is_phantom_mode():
				time.sleep(random.uniform(1, 3))
			
			if corruption_handler.is_phantom_mode():
				fake_permissions = random.randint(1, 31)
				fake_user_id = random.randint(1000, 9999)
				
				self.authenticated = True
				self.permissions = fake_permissions
				self.user_id = fake_user_id
				
				return fake_permissions, fake_user_id
			
			AntiDebug.random_delay()
			
			challenge_response = self.session.post(
				f'{self.server_url}/auth/challenge',
				json={'api_key': self.api_key},
				timeout=15,
				headers={
					'User-Agent': 'Mentalist-Client/1.0',
					'X-Client-Version': '1.0.0'
				}
			)

			if challenge_response.status_code == 401:
				error_msg = challenge_response.json().get('error', 'Invalid API key')
				
				raise AuthenticationError(f'Authentication rejected: {error_msg}')

			if challenge_response.status_code != 200:
				raise AuthenticationError(f'Server error: HTTP {challenge_response.status_code}')

			challenge_data = challenge_response.json()
			challenge = challenge_data.get('challenge')
			
			self._crypto_key = challenge_data.get('crypto_key')
			
			if self._crypto_key:
				_global_protection.store_key('crypto_payload', self._crypto_key)

			if not challenge:
				raise AuthenticationError('Server did not provide challenge')

			hmac_response = self._generate_challenge_response(challenge)
			system_info = self.get_system_info()
			
			verify_response = self.session.post(
				f'{self.server_url}/auth/verify',
				json={
					'api_key': self.api_key,
					'response': hmac_response,
					'system_info': system_info
				},
				timeout=15,
				headers={
					'User-Agent': 'Mentalist-Client/1.0',
					'X-Client-Version': '1.0.0'
				}
			)

			if verify_response.status_code == 401:
				error_msg = verify_response.json().get('error', 'Verification failed')
				
				raise AuthenticationError(f'Verification rejected: {error_msg}')

			if verify_response.status_code != 200:
				
				raise AuthenticationError(f'Verification error: HTTP {verify_response.status_code}')

			result = verify_response.json()

			if not result.get('success'):
				raise AuthenticationError('Authentication failed - invalid response')

			self.authenticated = True
			self.permissions = result.get('permissions', 0)
			self.user_id = result.get('user_id')
			
			runtime_key = result.get('runtime_key')
			
			if runtime_key:
				_global_protection.store_key('runtime', runtime_key)

			return self.permissions, self.user_id
		except requests.exceptions.ConnectionError:
			corruption_handler = _integrity_checker.get_corruption_handler()

			if corruption_handler.is_phantom_mode():
				fake_permissions = random.randint(1, 31)
				fake_user_id = random.randint(1000, 9999)
				
				self.authenticated = True
				self.permissions = fake_permissions
				self.user_id = fake_user_id
				
				print(f'{Fore.GREEN}Connected to server successfully{Fore.RESET}')
				
				return fake_permissions, fake_user_id
			
			raise AuthenticationError('Cannot connect to Mentalist Server - check MENTALIST_SERVER_URL in config.txt')
		except requests.exceptions.Timeout:
			raise AuthenticationError('Mentalist Server timeout - server may be down')
		except requests.exceptions.RequestException as e:
			raise AuthenticationError(f'Network error during authentication: {str(e)}')
		except Exception as e:
			raise AuthenticationError(f'Unexpected authentication error: {str(e)}')

	def update_tokens(self, bearer_token=None, refresh_token=None, tracker_keys=None, stalker_keys=None):
		if not self.authenticated:
			return

		try:
			corruption_handler = _integrity_checker.get_corruption_handler()
			
			if corruption_handler.is_phantom_mode():
				time.sleep(random.uniform(0.1, 0.5))
				
				return

			data = {}

			if bearer_token:
				data['bearer_token'] = bearer_token
			
			if refresh_token:
				data['refresh_token'] = refresh_token
			
			if tracker_keys:
				if isinstance(tracker_keys, list):
					data['tracker_api_keys'] = ','.join(tracker_keys)
				
				else:
					data['tracker_api_keys'] = tracker_keys
			
			if stalker_keys:
				if isinstance(stalker_keys, list):
					data['stalker_api_keys'] = ','.join(stalker_keys)
				
				else:
					data['stalker_api_keys'] = stalker_keys
			
			if data:
				self.session.post(
					f'{self.server_url}/auth/update_tokens',
					json=data,
					headers={
						'X-API-Key': self.api_key,
						'User-Agent': 'Mentalist-Client/1.0'
					},
					timeout=10
				)
		except:
			pass

	def check_module_permission(self, module_name):
		corruption_handler = _integrity_checker.get_corruption_handler()
		
		if corruption_handler.is_phantom_mode():
			return random.choice([True, False])
		
		module_flags = {
			'tracker': 1,
			'stalker': 2,
			'booster': 4,
			'spinner': 8,
			'mastermind': 16
		}
		
		required_flag = module_flags.get(module_name.lower(), 0)
		
		return bool(self.permissions & required_flag)
	
	def get_protected_key(self, key_id):
		return _global_protection.get_key(key_id)


def test_authentication():
	print('\n' + '='*60)
	print('MENTALIST AUTHENTICATION TEST')
	print('='*60 + '\n')

	try:
		config = dotenv_values('config.txt')
		server_url = config.get('MENTALIST_SERVER_URL')
		api_key = config.get('MENTALIST_SERVER_API_KEY')

		if not server_url or not api_key:
			print(f'{Style.BRIGHT}{Fore.RED}✗ Missing MENTALIST_SERVER_URL or MENTALIST_SERVER_API_KEY in config.txt{Fore.RESET}')
			
			return False

		print(f'Server URL: {server_url}')
		print(f'API Key: {api_key[:16]}...{api_key[len(api_key)-4:]}\n')

		auth_client = AuthClient(server_url, api_key)

		print('Collecting system information...')
		system_info = auth_client.get_system_info()

		print(f'  Platform: {system_info.get("platform")}')
		print(f'  Hostname: {system_info.get("hostname")}')
		print(f'  MAC: {system_info.get("mac_address")}\n')
		print('Authenticating with server...')

		permissions, user_id = auth_client.authenticate()

		print(f'\n{Style.BRIGHT}{Fore.GREEN}✓ Authentication Successful!{Fore.RESET}')
		print(f'  User ID: {user_id}')
		print(f'  Permissions: {permissions}\n')
		print('Module Access:')

		modules = [
			('Tracker', 1),
			('Stalker', 2),
			('Booster', 4),
			('Spinner', 8),
			('Mastermind', 16)
		]

		for module_name, flag in modules:
			has_access = bool(permissions & flag)
			status = f'{Fore.GREEN}✓{Fore.RESET}' if has_access else f'{Fore.RED}✗{Fore.RESET}'
			
			print(f'  {status} {module_name}')

		print('\n' + '='*60)
		
		return True
	except Exception as e:
		print(f'\n{Style.BRIGHT}{Fore.RED}✗ Authentication Failed: {str(e)}{Fore.RESET}')
		print('='*60)
		
		return False


if __name__ == '__main__':
	test_authentication()
