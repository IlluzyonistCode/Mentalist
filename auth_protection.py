import hashlib
import ctypes
import psutil
import os
import sys
import time
import random
from pathlib import Path
from functools import wraps
from datetime import datetime

def is_frozen():
	return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def get_application_path():
	if is_frozen():
		return Path(sys._MEIPASS)

	else:
		return Path(os.path.abspath('.'))

def find_pyd_files():
	app_path = get_application_path()
	pyd_files = {}

	extensions = ['.pyd', '.so', '.dll']

	critical_modules = [
		'auth_client',
		'auth_decorator',
		'auth_protection',
		'mentalist'
	]
	
	for ext in extensions:
		for module in critical_modules:
			patterns = [
				f'{module}{ext}',
				f'{module}.cp*{ext}',
			]
			
			for pattern in patterns:
				if '*' in pattern:
					matches = list(app_path.glob(pattern))

					if matches:
						pyd_files[module] = matches[0]

						break

				else:
					file_path = app_path / pattern

					if file_path.exists():
						pyd_files[module] = file_path

						break
	
	return pyd_files


class AdaptiveTiming:
	_baseline_established = False
	_baseline_multiplier = 1.0
	_startup_grace_period = True
	_startup_time = time.time()
	
	@classmethod
	def is_startup_phase(cls):
		elapsed = time.time() - cls._startup_time

		return elapsed < 30.0
	
	@classmethod
	def establish_baseline(cls):
		if cls._baseline_established:
			return cls._baseline_multiplier

		t1 = time.perf_counter()
		x = 0

		for i in range(50000):
			x += (i * 0xDEADBEEF) ^ (x >> 2)

		t2 = time.perf_counter()
		
		baseline_time = t2 - t1

		if baseline_time < 0.02:
			cls._baseline_multiplier = 1.0

		elif baseline_time < 0.05:
			cls._baseline_multiplier = 1.5

		else:
			cls._baseline_multiplier = 2.0
		
		cls._baseline_established = True

		return cls._baseline_multiplier
	
	@classmethod
	def get_adjusted_threshold(cls, base_threshold):
		multiplier = cls.establish_baseline()

		if cls.is_startup_phase():
			return base_threshold * multiplier * 10.0
		
		return base_threshold * multiplier * 2.0 


class WindowsAntiDebug:
	@staticmethod
	def is_debugger_present():
		try:
			kernel32 = ctypes.windll.kernel32

			return kernel32.IsDebuggerPresent() != 0
		except:
			return False
	
	@staticmethod
	def check_remote_debugger():
		try:
			kernel32 = ctypes.windll.kernel32
			is_debugged = ctypes.c_bool()
			kernel32.CheckRemoteDebuggerPresent(ctypes.c_void_p(-1), ctypes.byref(is_debugged))
			
			return is_debugged.value
		except:
			return False
	
	@staticmethod
	def check_parent_process():
		try:
			current = psutil.Process()
			parent = current.parent()

			if parent:
				parent_name = parent.name().lower()
				suspicious = ['x64dbg', 'x32dbg', 'ollydbg', 'ida', 'ida64', 'windbg', 'devenv', 'processhacker', 'cheatengine']
				
				for sus in suspicious:
					if sus in parent_name:
						return True

			return False
		except:
			return False
	
	@staticmethod
	def check_all():
		if WindowsAntiDebug.is_debugger_present():
			return True

		if WindowsAntiDebug.check_remote_debugger():
			return True

		if WindowsAntiDebug.check_parent_process():
			return True

		return False


class AntiDebug:
	@staticmethod
	def check_trace():
		return sys.gettrace() is not None
	
	@staticmethod
	def timing_check(threshold=0.1):
		def decorator(func):
			@wraps(func)
			def wrapper(*args, **kwargs):
				adjusted_threshold = AdaptiveTiming.get_adjusted_threshold(threshold)
				
				t1 = time.perf_counter()
				result = func(*args, **kwargs)
				t2 = time.perf_counter()
				execution_time = t2 - t1

				if execution_time > adjusted_threshold:
					if AdaptiveTiming.is_startup_phase():
						return result

					return

				return result

			return wrapper
		
		return decorator
	
	@staticmethod
	def random_delay():
		time.sleep(random.uniform(0.001, 0.05))
	
	@staticmethod
	def cpu_trap(iterations=100000):
		multiplier = AdaptiveTiming.establish_baseline()
		
		t1 = time.perf_counter()
		x = 0

		for i in range(iterations):
			x += (i * 0xDEADBEEF) ^ (x >> 2)

		t2 = time.perf_counter()
		
		actual_time = t2 - t1

		if multiplier <= 1.0:
			threshold = 0.3

		elif multiplier <= 1.5:
			threshold = 0.5
		else:
			threshold = 0.8

		if AdaptiveTiming.is_startup_phase():
			threshold *= 10
		
		return actual_time > threshold


class PhantomKeyGenerator:
	def __init__(self, seed_corruption):
		self._seed = seed_corruption
		self._depth = 0
		self._max_depth = random.randint(50, 100)
	
	def generate_phantom_key(self):
		layers = []

		for i in range(self._max_depth):
			layer_noise = hashlib.sha256(f'{self._seed}_{i}_{time.time()}'.encode()).hexdigest()
			layers.append(layer_noise)
		
		final_phantom = hashlib.sha256(''.join(layers).encode()).hexdigest()
		
		return final_phantom
	
	def entangle_with_noise(self, real_data):
		phantom = self.generate_phantom_key()
		noise_ratio = random.uniform(0.3, 0.7)
		result = []

		for i, char in enumerate(str(real_data)):
			if random.random() < noise_ratio:
				result.append(phantom[i % len(phantom)])

			else:
				result.append(char)

		return ''.join(result)


class MathematicalEntanglement:
	def __init__(self, integrity_key, force_corruption=False):
		self._base_key = integrity_key
		self._corruption_detected = force_corruption
		self._entropy_modifier = 1.0
		self._integrity_float = 0.999
	
	def compute_entangled_value(self, base_value, modulus=1000000):
		if not self._corruption_detected:
			return int((base_value * self._integrity_float) % modulus)

		else:
			drift = random.uniform(-0.02, 0.02)
			corrupted_float = self._integrity_float + drift

			return int((base_value * corrupted_float) % modulus)
	
	def apply_coordinate_distortion(self, x, y):
		if not self._corruption_detected:
			return x, y

		else:
			x_drift = int(x * 0.95 + random.uniform(-2, 2))
			y_drift = int(y * 0.95 + random.uniform(-2, 2))

			return x_drift, y_drift
	
	def corrupt_statistical_data(self, data_dict):
		if not self._corruption_detected:
			return data_dict
		
		corrupted = {}

		for key, value in data_dict.items():
			if isinstance(value, (int, float)):
				noise = random.uniform(0.93, 0.97)
				corrupted[key] = value * noise

			else:
				corrupted[key] = value

		return corrupted
	
	def temporal_distortion_factor(self):
		if not self._corruption_detected:
			return 1.0

		else:
			self._entropy_modifier *= 1.05

			return self._entropy_modifier


class SilentCorruptionHandler:
	def __init__(self):
		self._phantom_mode = False
		self._corruption_markers = []
		self._fake_success_rate = 0.95
	
	def enter_phantom_mode(self, reason):
		self._phantom_mode = True
		self._corruption_markers.append({
			'timestamp': datetime.now().isoformat(),
			'reason': reason,
			'entropy': random.random()
		})
	
	def is_phantom_mode(self):
		return self._phantom_mode
	
	def generate_plausible_lie(self, data_type='json'):
		if data_type == 'json':
			fake_data = {
				'ok': True,
				'status': 'success',
				'data': {
					'player_count': random.randint(5, 15),
					'game_state': random.choice(['active', 'waiting', 'in_progress']),
					'roles': [f'Role_{i}' for i in range(random.randint(3, 8))],
					'timestamp': datetime.now().isoformat()
				},
				'metadata': {
					'version': f'{random.randint(1, 3)}.{random.randint(0, 9)}.{random.randint(0, 9)}',
					'checksum': hashlib.md5(str(random.random()).encode()).hexdigest()
				}
			}

			return fake_data
		
		elif data_type == 'key':
			return hashlib.sha256(f'phantom_{random.random()}'.encode()).hexdigest()
		
		else:
			return f'PHANTOM_DATA_{random.randint(10000, 99999)}'
	
	def phantom_decrypt(self, encrypted_data, phantom_key):
		noise = hashlib.sha256(phantom_key.encode()).digest()
		result = []

		for i in range(len(encrypted_data)):
			fake_byte = noise[i % len(noise)] ^ random.randint(0, 255)
			result.append(fake_byte)

		plausible_garbage = bytes(result)

		try:
			return plausible_garbage.decode('utf-8', errors='replace')
		except:
			return str(plausible_garbage)


class MemoryProtection:
	def __init__(self):
		self._keys = {}
		self._obfuscated = True
	
	def store_key(self, key_id, key_data):
		self._keys[key_id] = self._xor_data(key_data.encode())
	
	def get_key(self, key_id):
		if key_id not in self._keys:
			return

		return self._xor_data(self._keys[key_id]).decode()
	
	def _xor_data(self, data):
		mask = hashlib.sha256(str(id(self)).encode()).digest()

		return bytes([b ^ mask[i % len(mask)] for i, b in enumerate(data)])
	
	def clear(self):
		self._keys.clear()


class IntegrityChecker:
	def __init__(self):
		self.file_hashes = {}
		self.pyd_hashes = {}
		self._corruption_flags = []
		self._silent_mode = True
		self._entanglement_key = None
		self._phantom_generator = None
		self._corruption_handler = SilentCorruptionHandler()
		self._math_entanglement = None
		self._temporal_poison_level = 0
	
	def set_entanglement_key(self, key):
		self._entanglement_key = key
		self._math_entanglement = MathematicalEntanglement(key, force_corruption=False)
	
	def add_file(self, filepath, expected_hash):
		self.file_hashes[filepath] = expected_hash
	
	def add_pyd_file(self, module_name, expected_hash):
		self.pyd_hashes[module_name] = expected_hash
	
	@AntiDebug.timing_check(threshold=0.1)
	def verify_integrity(self):
		result = self.verify_silent()

		return result is not None
	
	def verify_silent(self):
		if not AdaptiveTiming.is_startup_phase():
			if WindowsAntiDebug.check_all():
				self._enter_ghost_mode('debug_windows_detected')
				self._temporal_poison_level += 1

				return self._get_phantom_key()

		if AntiDebug.check_trace():
			self._enter_ghost_mode('trace_detected')
			self._temporal_poison_level += 1

			return self._get_phantom_key()

		if not AdaptiveTiming.is_startup_phase():
			if AntiDebug.cpu_trap():
				self._enter_ghost_mode('timing_violation')
				self._temporal_poison_level += 1

				return self._get_phantom_key()

		if is_frozen():
			return self._verify_pyd_integrity()

		return self._verify_py_integrity()
	
	def _verify_pyd_integrity(self):
		try:
			pyd_files = find_pyd_files()
			
			if len(pyd_files) == 0:
				self._enter_ghost_mode('no_pyd_files_found')

				return self._get_phantom_key()

			for module_name, expected_hash in self.pyd_hashes.items():
				if module_name not in pyd_files:
					self._enter_ghost_mode(f'missing_pyd_{module_name}')

					return self._get_phantom_key()
				
				pyd_path = pyd_files[module_name]

				try:
					with open(pyd_path, 'rb') as f:
						actual_hash = hashlib.sha256(f.read()).hexdigest()
					
					if actual_hash != expected_hash:
						self._enter_ghost_mode(f'modified_pyd_{module_name}')

						return self._get_phantom_key()
						
				except Exception as e:
					self._enter_ghost_mode(f'error_reading_pyd_{module_name}')

					return self._get_phantom_key()

			return self._entanglement_key if self._entanglement_key else hashlib.sha256(b'valid_pyd').hexdigest()
		except Exception as e:
			self._enter_ghost_mode(f'pyd_check_exception_{str(e)}')

			return self._get_phantom_key()

	def _verify_py_integrity(self):
		for filepath, expected in self.file_hashes.items():
			try:
				if not os.path.exists(filepath):
					self._enter_ghost_mode(f'missing_py_{filepath}')

					return self._get_phantom_key()
				
				with open(filepath, 'rb') as f:
					actual = hashlib.sha256(f.read()).hexdigest()

				if actual != expected:
					self._enter_ghost_mode(f'modified_py_{filepath}')

					return self._get_phantom_key()
			except Exception as e:
				self._enter_ghost_mode(f'error_checking_py_{filepath}')

				return self._get_phantom_key()
		
		return self._entanglement_key if self._entanglement_key else hashlib.sha256(b'valid_py').hexdigest()
	

	def _enter_ghost_mode(self, reason):
		self._corruption_flags.append(reason)
		self._corruption_handler.enter_phantom_mode(reason)
		
		if not self._phantom_generator:
			self._phantom_generator = PhantomKeyGenerator(reason)

		if self._math_entanglement:
			key = self._entanglement_key if self._entanglement_key else 'corrupted'
			
			self._math_entanglement = MathematicalEntanglement(key, force_corruption=True)
	
	def _get_phantom_key(self):
		if not self._phantom_generator:
			self._phantom_generator = PhantomKeyGenerator('unknown_corruption')

		return self._phantom_generator.generate_phantom_key()
	
	def is_compromised(self):
		return len(self._corruption_flags) > 0
	
	def get_decryption_key(self):
		return self.verify_silent()
	
	def get_entanglement_engine(self):
		if not self._math_entanglement:
			key = self.verify_silent()
			force_corruption = self.is_compromised()

			self._math_entanglement = MathematicalEntanglement(key, force_corruption=force_corruption)
		
		return self._math_entanglement
	
	def apply_temporal_poison(self):
		if self._temporal_poison_level > 0:
			delay = 0.05 * self._temporal_poison_level
			time.sleep(delay)

			self._temporal_poison_level = min(self._temporal_poison_level + 1, 20)
	
	def get_corruption_handler(self):
		return self._corruption_handler


_global_protection = MemoryProtection()
_integrity_checker = IntegrityChecker()
