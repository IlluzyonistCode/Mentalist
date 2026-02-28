import hashlib
import base64
import json
import os
import sys
import platform
import time
import uuid
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class _KeyObfuscator:
	@staticmethod
	def _get_machine_fingerprint():
		components = [
			platform.node(), 
			platform.machine(),
			platform.processor(),
			sys.version
		]

		if sys.platform.startswith('win'):
			try:
				import winreg

				key = winreg.OpenKey(
					winreg.HKEY_LOCAL_MACHINE,
					r'SOFTWARE\Microsoft\Cryptography'
				)
				guid = winreg.QueryValueEx(key, 'MachineGuid')[0]
				components.append(guid)
				winreg.CloseKey(key)
			except:
				pass

		if sys.platform.startswith('linux'):
			try:
				with open('/etc/machine-id', 'rt', encoding='ascii') as f:
					components.append(f.read().strip())
			except:
				pass

		try:
			mac = uuid.getnode()
			components.append(f'{mac:012x}')
		except:
			pass

		fingerprint = ''.join(components).encode('utf-8')

		return hashlib.sha512(fingerprint).digest()
	
	@staticmethod
	def _obfuscate_layers():
		_s1 = bytes([
			0x4d, 0x65, 0x6e, 0x74, 0x61, 0x6c, 0x69, 0x73, 
			0x74, 0x5f, 0x53, 0x65, 0x63, 0x72, 0x65, 0x74
		])

		_s2 = bytes([b ^ 0xAA for b in _s1])

		_s3 = _s2 + hashlib.md5(_s2).digest()

		_s4 = base64.b85encode(_s3)
		
		return _s4
	
	@staticmethod
	def derive_key(context=b'default'):
		obfuscated = _KeyObfuscator._obfuscate_layers()
		fingerprint = _KeyObfuscator._get_machine_fingerprint()

		combined = obfuscated + fingerprint + context

		kdf = PBKDF2HMAC(
			algorithm=hashes.SHA256(),
			length=32,
			salt=b'Hannibal',
			iterations=100000,
			backend=default_backend()
		)
		
		key = base64.urlsafe_b64encode(kdf.derive(combined))

		return key


class SecureDataStore:
	def __init__(self, file_path, context=b'default'):
		self.file_path = file_path
		self.encrypted_path = file_path.replace('.json', '.enc')
		self.context = context
		self._key = None
	
	def _get_key(self):
		if self._key is None:
			self._key = _KeyObfuscator.derive_key(self.context)

		return self._key
	
	def _get_cipher(self):
		return Fernet(self._get_key())
	
	def encrypt_and_save(self, data):
		try:
			json_data = json.dumps(data, ensure_ascii=False, indent=2)
			json_bytes = json_data.encode('utf-8')

			metadata = {
				'version': '1.0',
				'timestamp': int(time.time()),
				'checksum': hashlib.sha256(json_bytes).hexdigest(),
				'data': base64.b64encode(json_bytes).decode('ascii')
			}
			
			metadata_bytes = json.dumps(metadata).encode('utf-8')

			cipher = self._get_cipher()
			encrypted_data = cipher.encrypt(metadata_bytes)
			
			os.makedirs(os.path.dirname(self.encrypted_path) or '.', exist_ok=True)

			with open(self.encrypted_path, 'wb') as f:
				f.write(encrypted_data)

			if os.path.exists(self.file_path) and self.file_path != self.encrypted_path:
				try:
					os.remove(self.file_path)
				except:
					pass
			
			return True
		except Exception as e:
			print(f'Encryption error: {type(e).__name__}: {str(e) or "(no message)"}')

			return False
	
	def load_and_decrypt(self):
		try:
			if not os.path.exists(self.encrypted_path):
				if os.path.exists(self.file_path):
					with open(self.file_path, 'r', encoding='utf-8') as f:
						data = json.load(f)

					self.encrypt_and_save(data)
					
					return data

				else:
					return

			with open(self.encrypted_path, 'rb') as f:
				encrypted_data = f.read()

			cipher = self._get_cipher()
			
			try:
				decrypted_bytes = cipher.decrypt(encrypted_data)
			except InvalidToken:
				print('Decryption error: InvalidToken (file corrupted or tampered)')

				return

			metadata = json.loads(decrypted_bytes.decode('utf-8'))

			if metadata.get('version') != '1.0':
				raise ValueError('Unsupported encryption version')

			json_bytes = base64.b64decode(metadata['data'])
			checksum = hashlib.sha256(json_bytes).hexdigest()

			if checksum != metadata.get('checksum'):
				raise ValueError('Data integrity check failed')

			data = json.loads(json_bytes.decode('utf-8'))
			
			return data
		except Exception as e:
			print(f'Decryption error: {type(e).__name__}: {str(e) or "(no message)"}')
	
	def migrate_from_plaintext(self):
		if os.path.exists(self.file_path) and not os.path.exists(self.encrypted_path):
			try:
				with open(self.file_path, 'r', encoding='utf-8') as f:
					data = json.load(f)
				
				success = self.encrypt_and_save(data)
				
				if success:
					print(f'✓ Migrated {self.file_path} to encrypted format')

					return True
			except Exception as e:
				print(f'Migration failed for {self.file_path}: {str(e)}')
		
		return False


def get_secure_store(file_type):
	contexts = {
		'cards': b'mentalist_cards_context_v1',
		'icons': b'mentalist_icons_context_v1',
		'role_profiles': b'mentalist_profiles_context_v1',
		'hosts': b'mentalist_hosts_context_v1',
		'targets': b'mentalist_targets_context_v1'
	}
	
	paths = {
		'cards': '.mentalist_data/cards.json',
		'icons': '.mentalist_data/icons.json',
		'role_profiles': '.mentalist_data/role_profiles.json',
		'hosts': '.mentalist_data/hosts.json',
		'targets': '.mentalist_data/targets.json'
	}
	
	if file_type not in contexts:
		raise ValueError(f'Unknown file type: {file_type}')
	
	return SecureDataStore(paths[file_type], contexts[file_type])

def save_encrypted(file_type, data):
	store = get_secure_store(file_type)

	return store.encrypt_and_save(data)

def load_encrypted(file_type):
	store = get_secure_store(file_type)

	return store.load_and_decrypt()

def migrate_all_to_encrypted():
	for file_type in ['cards', 'icons', 'role_profiles', 'targets']:
		store = get_secure_store(file_type)
		store.migrate_from_plaintext()
