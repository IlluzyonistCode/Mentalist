import shutil
import subprocess
import os
import sys
import re
import json
import hashlib
import base64
import marshal
import zlib
import random
import string
import time
import undetected_playwright
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, Back, init

try:
	from Cython.Build import cythonize
	from setuptools import setup, Extension

	HAS_CYTHON = True
except ImportError:
	HAS_CYTHON = False

init(autoreset=True)


def get_playwright_browsers_path():
	ms_playwright = Path.home() / 'AppData' / 'Local' / 'ms-playwright'

	if ms_playwright.exists():
		print(f'{Fore.GREEN}✓ Found Playwright browsers at: {ms_playwright}{Fore.RESET}')
		
		return ms_playwright
	
	pkg_driver = Path(os.path.dirname(undetected_playwright.__file__)) / 'driver'

	if pkg_driver.exists():
		print(f'{Fore.GREEN}✓ Found Playwright driver at: {pkg_driver}{Fore.RESET}')
		
		return pkg_driver

	python_dir = Path(sys.executable).parent
	local_playwright = python_dir / 'ms-playwright'

	if local_playwright.exists():
		print(f'{Fore.GREEN}✓ Found Playwright at: {local_playwright}{Fore.RESET}')

		return local_playwright

	if sys.platform != 'win32':
		local_share = Path.home() / '.local' / 'share' / 'ms-playwright'

		if local_share.exists():
			print(f'{Fore.GREEN}✓ Found Playwright at: {local_share}{Fore.RESET}')

			return local_share
	
	print(f'{Fore.YELLOW}⚠ WARNING: Playwright browsers not found!{Fore.RESET}')
	print(f'{Fore.YELLOW}  Install with: playwright install chromium{Fore.RESET}')
	print(f'{Fore.YELLOW}  Or: python -m playwright install chromium{Fore.RESET}')


PLAYWRIGHT_DRIVER_PATH = get_playwright_browsers_path()


class DecoyInjector:
	@staticmethod
	def generate_decoy_chain(num_layers=75):
		decoys = []
		
		for depth in range(num_layers):
			class_name = f'DecoyDecryptor_Layer_{depth}_{random.randint(1000, 9999)}'
			
			methods = []
			for i in range(random.randint(5, 12)):
				method_name = f'_decrypt_stage_{i}'
				fake_key = hashlib.sha256(str(random.random()).encode()).hexdigest()
				
				methods.append(f'''
	def {method_name}(self, payload):
		key_fragment = "{fake_key}"
		intermediate = bytes([b ^ ord(key_fragment[i % len(key_fragment)]) for i, b in enumerate(payload)])
		return self._rotate_bits(intermediate, {random.randint(1, 7)})
				''')
			
			next_pointer = f'DecoyDecryptor_Layer_{depth + 1}' if depth < num_layers - 1 else 'return 0'
			
			decoy_class = f'''
class {class_name}:
	def __init__(self):
		self._master_key = "{hashlib.sha256(str(random.random()).encode()).hexdigest()}"
		self._depth = {depth}
		self._entropy = {random.random()}
	
	def _xor_layer(self, data, key):
		return bytes([b ^ ord(key[i % len(key)]) for i, b in enumerate(data)])
	
	def _rotate_bits(self, data, shift):
		result = []
		for byte in data:
			rotated = ((byte << shift) | (byte >> (8 - shift))) & 0xFF
			result.append(rotated)
		return bytes(result)
	
	{''.join(methods)}
	
	def get_next_layer(self):
		return "{next_pointer}"
	
	def looks_important(self):
		return True
			'''
			
			decoys.append(decoy_class)
		
		return decoys
	
	@staticmethod
	def inject_decoys_into_module(module_path, num_decoys=75):
		if not module_path.exists():
			return False
		
		content = module_path.read_text(encoding='utf-8')
		
		decoy_chain = DecoyInjector.generate_decoy_chain(num_decoys)
		decoy_code = '\n\n'.join(decoy_chain)
		
		injection_marker = '# DECOY_INJECTION_POINT'
		
		if injection_marker in content:
			parts = content.split(injection_marker)
			new_content = parts[0] + injection_marker + '\n' + decoy_code + '\n' + parts[1] if len(parts) > 1 else parts[0] + injection_marker + '\n' + decoy_code
		
		else:
			new_content = content + '\n\n' + injection_marker + '\n' + decoy_code
		
		module_path.write_text(new_content, encoding='utf-8')

		return True


class IntegrityManager:
	def __init__(self):
		self.py_hashes = {}
		self.pyd_hashes = {}
		self.target_files = []
		self.entanglement_key = None
	
	def calculate_hash(self, filepath):
		if not filepath.exists():
			return

		sha256 = hashlib.sha256()

		with open(filepath, 'rb') as f:
			for chunk in iter(lambda: f.read(8192), b''):
				sha256.update(chunk)

		return sha256.hexdigest()
	
	def register_py_file(self, filepath, module_name):
		file_hash = self.calculate_hash(filepath)

		if file_hash:
			self.py_hashes[module_name] = file_hash
			self.target_files.append(module_name)

			return True

		return False
	
	def register_pyd_file(self, filepath, module_name):
		file_hash = self.calculate_hash(filepath)

		if file_hash:
			self.pyd_hashes[module_name] = file_hash

			return True

		return False
	
	def generate_entanglement_key(self):
		combined_hash = hashlib.sha256()

		all_hashes = list(self.py_hashes.values()) + list(self.pyd_hashes.values())
		
		for file_hash in sorted(all_hashes):
			combined_hash.update(file_hash.encode())
		
		self.entanglement_key = combined_hash.hexdigest()

		return self.entanglement_key
	
	def inject_into_protection(self, protection_path):
		if not protection_path.exists():
			return False
		
		content = protection_path.read_text(encoding='utf-8')
		
		marker = '_integrity_checker = IntegrityChecker()'
		
		if marker not in content:
			return False
		
		clean_content = content.split(marker)[0] + marker + '\n'
		
		hash_injection = ''

		for module_name, file_hash in self.py_hashes.items():
			if 'auth_protection' in module_name:
				continue
			
			hash_injection += f"_integrity_checker.add_file('{module_name}', '{file_hash}')\n"

		for module_name, file_hash in self.pyd_hashes.items():
			if 'auth_protection' in module_name:
				continue
			
			hash_injection += f"_integrity_checker.add_pyd_file('{module_name}', '{file_hash}')\n"

		if self.entanglement_key:
			hash_injection += f"_integrity_checker.set_entanglement_key('{self.entanglement_key}')\n"
		
		protection_path.write_text(clean_content + hash_injection, encoding='utf-8')
		
		return True


class CythonCompiler:
	def __init__(self, project_root):
		self.project_root = project_root
		self.compiled_modules = []
	
	def create_setup_script(self, modules, output_path):
		module_list = ', '.join([f"'{m}'" for m in modules])
		
		setup_code = f'''
from setuptools import setup
from Cython.Build import cythonize
import sys

extensions = [{module_list}]

setup(
	ext_modules=cythonize(
		extensions,
		compiler_directives={{
			'language_level': '3',
			'always_allow_keywords': True,
			'emit_code_comments': False,
			'boundscheck': False,
			'wraparound': False,
			'initializedcheck': False,
			'nonecheck': False,
			'overflowcheck': False,
			'cdivision': True,
			'embedsignature': False,
			'optimize.use_switch': True,
			'optimize.unpack_method_calls': True
		}},
		force=True
	),
	script_args=['build_ext', '--inplace']
)
		'''
		output_path.write_text(setup_code)

		return output_path
	
	def compile_modules(self, modules):
		if not modules:
			return False
		
		setup_file = self.project_root / f'setup_compile_{random.randint(1000, 9999)}.py'
		
		try:
			self.create_setup_script(modules, setup_file)
			
			result = subprocess.run(
				[sys.executable, str(setup_file)],
				capture_output=True,
				text=True,
				cwd=str(self.project_root),
				timeout=300
			)
			
			if result.returncode == 0:
				for module in modules:
					base_name = module.replace('.py', '')
					pyd_candidates = list(self.project_root.glob(f'{base_name}*.pyd'))
					so_candidates = list(self.project_root.glob(f'{base_name}*.so'))
					
					if pyd_candidates or so_candidates:
						self.compiled_modules.append(base_name)
				
				c_files = list(self.project_root.glob('*.c'))

				for c_file in c_files:
					try:
						c_file.unlink()
					except:
						pass
				
				setup_file.unlink()

				return True

			else:
				print(result.stderr)
				return False
		
		except subprocess.TimeoutExpired:
			return False
		except Exception as e:
			return False
		finally:
			if setup_file.exists():
				try:
					setup_file.unlink()
				except:
					pass
	
	def get_compiled_extensions(self):
		extensions = []

		for module in self.compiled_modules:
			pyd_files = list(self.project_root.glob(f'{module}*.pyd'))
			so_files = list(self.project_root.glob(f'{module}*.so'))
			extensions.extend(pyd_files)
			extensions.extend(so_files)

		return extensions


class PyInstallerBuilder:
	def __init__(self, project_root, dist_dir, build_dir):
		self.project_root = project_root
		self.dist_dir = dist_dir
		self.build_dir = build_dir
		self.hidden_imports = [
			'auth_protection', 'auth_client', 'auth_decorator', 
			'updater', 'mentalist', 'mentalist_cli', 'mentalist_gui',

			'pyautogui', 'pywinauto', 'pygetwindow', 'psutil', 'ntplib', 
			'playsound', 'pyscreeze', 'pytweening', 'mouseinfo', 'pymsgbox', 'pyrect',

			'requests', 'urllib3', 'chardet', 'idna', 'certifi', 'tenacity',
			'eel', 'bottle', 'bottle_websocket', 'geventwebsocket', 'geventwebsocket.handler',
			'engineio.async_drivers.gevent', 

			'undetected_playwright', 
			'undetected_playwright.sync_api',
			'undetected_playwright._impl',
			'undetected_playwright._impl._connection',
			'undetected_playwright._impl._transport',
			'playwright',
			'playwright.sync_api',

			'asyncio', 'nest_asyncio', 'gevent', 'gevent.monkey',
			
			'colorama', 'dotenv', 'tzlocal', 'pytz', 'dateutil', 'dateutil.parser',
			'jaraco.text', 'PIL', 'PIL.Image', 'cv2',

			'base64', 'marshal', 'zlib', 'ctypes', 'uuid', 'hashlib', 'hmac', 'tkinter', '_tkinter'
		]
		self.excluded_modules = [
			'numpy', 'pandas', 'matplotlib', 'plotly', 'scipy',
			'pandas.plotting', 'pandas._libs.tslibs.timedeltas',
			'plotly.graph_objects', 'plotly.figure_factory', 'plotly.subplots', 'plotly.express'
		]
	
	def build(self, entry_script, exe_name, console_mode, icon_path, compiled_extensions, data_items):
		if not entry_script.exists():
			return False
		
		command = [
			'pyinstaller',
			'--name', exe_name,
			'--onefile',
			'--clean',
			f'--distpath={self.dist_dir}',
			f'--workpath={self.build_dir}',
			f'--specpath={self.build_dir}'
		]
		
		if console_mode:
			command.append('--console')

		else:
			command.append('--windowed')
		
		if icon_path and icon_path.exists():
			command.append(f'--icon={icon_path}')
		
		for hidden_import in self.hidden_imports:
			command.extend(['--hidden-import', hidden_import])
		
		for excluded_module in self.excluded_modules:
			command.extend(['--exclude-module', excluded_module])

		for ext_file in compiled_extensions:
			command.extend(['--add-binary', f'{ext_file}{os.pathsep}.'])
		
		for data_source, data_dest in data_items:
			if data_source.exists():
				command.extend(['--add-data', f'{data_source}{os.pathsep}{data_dest}'])
		
		command.extend([
			'--collect-all', 'eel',
			'--collect-all', 'bottle',
			'--collect-all', 'gevent',
			'--collect-all', 'undetected_playwright',
			'--collect-all', 'playwright',
			'--noupx',
			'--log-level', 'WARN'
		])
		
		try:
			result = subprocess.run(
				command + [str(entry_script)],
				capture_output=True,
				text=True,
				cwd=str(self.project_root)
			)
			
			return result.returncode == 0
		except subprocess.TimeoutExpired:
			return False
		except Exception as e:
			return False

		return extensions


class BuildOrchestrator:
	def __init__(self):
		self.project_root = Path.cwd()
		self.temp_build_env = self.project_root / 'build_env_temp'
		self.dist_dir = self.project_root / 'dist'
		self.build_dir = self.project_root / 'build'
		self.releases_dir = self.project_root / 'releases'
		
		self.version = self._extract_version()
		self.build_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		
		self.integrity_manager = IntegrityManager()
		self.cython_compiler = CythonCompiler(self.project_root)
		self.pyinstaller = PyInstallerBuilder(self.project_root, self.dist_dir, self.build_dir)
		self.decoy_injector = DecoyInjector()
		
		self.entry_points = {
			'cli': {
				'name': 'Mentalist CLI',
				'script': 'mentalist_cli.py',
				'console': True
			},
			'gui': {
				'name': 'Mentalist GUI',
				'script': 'mentalist_gui.py',
				'console': False
			}
		}

		self.protection_modules = ['auth_client.py', 'auth_decorator.py', 'auth_protection.py']
		self.core_modules = ['mentalist.py']
	
	def _extract_version(self):
		try:
			mentalist_path = self.project_root / 'mentalist.py'
			
			if mentalist_path.exists():
				content = mentalist_path.read_text(encoding='utf-8')
				match = re.search(r"VERSION\s*=\s*['\"]([^'\"]+)['\"]", content)
				
				if match:
					return match.group(1)
		except:
			pass

		return '1.0.0'

	def _find_compiled_modules(self):
		pyd_files = {}

		search_paths = [self.temp_build_env / 'build']

		target_modules = ['auth_client', 'auth_decorator', 'mentalist']
		
		for search_path in search_paths:
			if not search_path.exists():
				continue

			for pyd_file in search_path.rglob('*.pyd'):
				for module in target_modules:
					if module in pyd_file.stem:
						pyd_files[module] = pyd_file

			for so_file in search_path.rglob('*.so'):
				for module in target_modules:
					if module in so_file.stem:
						pyd_files[module] = so_file
		
		return pyd_files

	def print_header(self, title):
		print(f'\n{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}{title.center(80)}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}\n')
	
	def print_step(self, message):
		print(f'{Style.BRIGHT}{Fore.YELLOW}▶ {message}{Fore.RESET}')
	
	def print_success(self, message):
		print(f'{Fore.GREEN}✓ {message}{Fore.RESET}')
	
	def print_error(self, message):
		print(f'{Fore.RED}✗ {message}{Fore.RESET}')
	
	def print_warning(self, message):
		print(f'{Fore.YELLOW}⚠ {message}{Fore.RESET}')
	
	def print_info(self, message):
		print(f'{Fore.CYAN}  {message}{Fore.RESET}')
	
	def check_environment(self):
		self.print_step('Checking build environment...')
		
		if not HAS_CYTHON:
			self.print_error('Cython not installed')

			return False
		
		self.print_success('Cython available')
		
		pyinstaller_check = subprocess.run(
			['pyinstaller', '--version'],
			capture_output=True,
			timeout=5
		)
		
		if pyinstaller_check.returncode != 0:
			self.print_error('PyInstaller not available')

			return False
		
		self.print_success('PyInstaller available')

		return True
	
	def clean_workspace(self):
		self.print_step('Cleaning workspace...')
		
		dirs_to_clean = [self.dist_dir, self.build_dir, self.temp_build_env]

		for directory in dirs_to_clean:
			if directory.exists():
				shutil.rmtree(directory)

				self.print_info(f'Removed {directory.name}/')
		
		for pattern in ['*.pyd', '*.so', '*.spec']:
			for file in self.project_root.glob(pattern):
				try:
					file.unlink()

					self.print_info(f'Removed {file.name}')
				except:
					pass
		
		self.dist_dir.mkdir(exist_ok=True)
		self.releases_dir.mkdir(exist_ok=True)
		
		self.print_success('Workspace cleaned')
		
		return True
	
	def create_build_sandbox(self):
		self.print_step('Creating build sandbox...')
		
		if self.temp_build_env.exists():
			shutil.rmtree(self.temp_build_env)
		
		self.temp_build_env.mkdir(parents=True, exist_ok=True)
		
		py_files = [f for f in self.project_root.glob('*.py') if f.name not in ['build.py', 'admin_cli.py', 'upload_update.py']]
		icon_files = list(self.project_root.glob('*.ico'))

		for py_file in py_files:
			shutil.copy2(py_file, self.temp_build_env / py_file.name)

			self.print_info(f'Copied: {py_file.name}')
		
		for icon in icon_files:
			shutil.copy2(icon, self.temp_build_env / icon.name)

			self.print_info(f'Copied: {icon.name}')

		folders_to_copy = ['gui', 'assets', 'audio', 'images']

		for folder_name in folders_to_copy:
			src_folder = self.project_root / folder_name

			if src_folder.exists():
				dst_folder = self.temp_build_env / folder_name
				shutil.copytree(src_folder, dst_folder)

				self.print_info(f'Copied: {folder_name}/')
		
		self.print_success(f'Build sandbox created at: {self.temp_build_env}')

		return True

	def prepare_source_files(self):
		self.print_step('Verifying source files...')
		
		required_files = self.protection_modules + self.core_modules
		
		for module in required_files:
			module_path = self.project_root / module

			if not module_path.exists():
				self.print_error(f'Missing required file: {module}')

				return False

			self.print_info(f'Found: {module}')
		
		self.print_success('All source files verified')

		return True
	
	def inject_decoy_layers(self):
		self.print_step('Injecting decoy layers into sandbox...')
		
		target_modules = ['mentalist.py', 'auth_client.py']
		
		for module_name in target_modules:
			sandbox_module_path = self.temp_build_env / module_name
			
			if not sandbox_module_path.exists():
				self.print_warning(f'{module_name} not found in sandbox, skipping')
				
				continue
			
			if DecoyInjector.inject_decoys_into_module(sandbox_module_path, num_decoys=75):
				self.print_success(f'Injected 75 decoy layers into {module_name} (sandbox)')
			
			else:
				self.print_warning(f'Failed to inject decoys into {module_name}')
		
		self.print_success('Decoy injection complete (sandbox)')

		return True
	
	def compile_protection_layer(self):
		self.print_step('Compiling protection layer with Cython...')
		
		self.cython_compiler = CythonCompiler(self.temp_build_env)

		if self.cython_compiler.compile_modules(self.protection_modules):
			self.print_success('Protection layer compiled')

			return True

		else:
			self.print_warning('Protection compilation failed')
			
			return False
	
	def compile_core_layer(self):
		self.print_step('Compiling core application with Cython...')
		
		if self.cython_compiler.compile_modules(self.core_modules):
			self.print_success('Core modules compiled')
			
			return True
			
		else:
			self.print_warning('Core compilation failed')
			
			return False

	def finalize_integrity_system(self):
		self.print_step('Finalizing integrity system...')

		py_files = {
			'auth_client.py': self.temp_build_env / 'auth_client.py',
			'auth_decorator.py': self.temp_build_env / 'auth_decorator.py',
			'mentalist.py': self.temp_build_env / 'mentalist.py'
		}
		
		for module_name, filepath in py_files.items():
			if filepath.exists():
				if self.integrity_manager.register_py_file(filepath, module_name):
					self.print_info(f'Registered .py: {module_name}')

		pyd_files = self._find_compiled_modules()
		
		for module_name, pyd_path in pyd_files.items():
			if pyd_path.exists():
				if self.integrity_manager.register_pyd_file(pyd_path, module_name):
					self.print_info(f'Registered .pyd: {module_name}')

		entanglement_key = self.integrity_manager.generate_entanglement_key()
		
		self.print_success(f'Generated entanglement key: {entanglement_key[:16]}...')

		protection_path = self.temp_build_env / 'auth_protection.py'
		
		if self.integrity_manager.inject_into_protection(protection_path):
			self.print_success('Integrity hashes and entanglement key injected')
			self.print_info(f'  .py files: {len(self.integrity_manager.py_hashes)}')
			self.print_info(f'  .pyd files: {len(self.integrity_manager.pyd_hashes)}')
		
		else:
			self.print_error('Failed to inject integrity system')

			return False
		
		return True

	def build_executable(self, build_type):
		if build_type not in self.entry_points:
			return False
		
		config = self.entry_points[build_type]
		
		self.print_step(f'Building {config["name"]}...')
		
		entry_script = self.temp_build_env / config['script']

		if not entry_script.exists():
			self.print_warning(f'{config["script"]} not found, skipping')

			return True
		
		exe_name = f'{config["name"]}_v{self.version}.exe'
		
		icon_path = self.temp_build_env / 'favicon.ico'

		compiled_extensions = self.cython_compiler.get_compiled_extensions()

		data_items = [
			(self.temp_build_env / 'gui', 'gui'),
			(self.temp_build_env / 'audio', 'audio'),
			(self.temp_build_env / 'assets', 'assets')
		]

		if PLAYWRIGHT_DRIVER_PATH and PLAYWRIGHT_DRIVER_PATH.exists():
			chromium_dirs = list(PLAYWRIGHT_DRIVER_PATH.glob('chromium-*'))

			if chromium_dirs:
				chromium_path = chromium_dirs[0]
				data_items.append((chromium_path, os.path.join('ms-playwright', chromium_path.name)))
				
				self.print_success(f'Including Playwright Chromium: {chromium_path.name}')
			
			else:
				self.print_warning('Chromium not found in Playwright directory')

		else:
			self.print_warning('Playwright not found - executable will need system Chrome/Chromium')

		self.pyinstaller = PyInstallerBuilder(self.temp_build_env, self.dist_dir, self.build_dir)
		
		if self.pyinstaller.build(entry_script, exe_name, config['console'], icon_path, compiled_extensions, data_items):
			self.print_success(f'{config["name"]} built successfully')
			
			return True

		else:
			self.print_error(f'{config["name"]} build failed')

			return False
	
	def create_release_package(self):
		self.print_step('Creating release package...')
		
		release_name = f'Mentalist_v{self.version}_{self.build_timestamp}'
		release_path = self.releases_dir / release_name
		release_path.mkdir(parents=True, exist_ok=True)
		
		build_manifest = {
			'version': self.version,
			'build_date': datetime.now().isoformat(),
			'build_timestamp': self.build_timestamp,
			'protection_layers': [
				'Cryptographic Hall of Mirrors (75+ Decoy Layers)',
				'Silent Failure Protocol (Phantom Mode)',
				'Mathematical Entanglement (Coordinate Distortion)',
				'Temporal Distortion (Progressive Poisoning)',
				'Total Compilation (Cython)',
				'Enhanced AntiDebug (Windows API)',
				'Distributed Integrity Checks'
			],
			'compiler': 'Cython with advanced optimizations',
			'executables': []
		}
		
		exe_count = 0

		for build_type, config in self.entry_points.items():
			exe_name = f'{config["name"]}_v{self.version}.exe'
			src_exe = self.dist_dir / exe_name
			
			if src_exe.exists():
				dst_exe = release_path / exe_name
				shutil.copy2(src_exe, dst_exe)
				
				file_size = dst_exe.stat().st_size
				file_hash = self.integrity_manager.calculate_hash(dst_exe)
				
				self.print_success(f'Packaged: {exe_name} ({file_size / 1024 / 1024:.2f} MB)')
				
				build_manifest['executables'].append({
					'name': exe_name,
					'type': build_type,
					'size_bytes': file_size,
					'sha256': file_hash
				})
				
				exe_count += 1
		
		if exe_count == 0:
			self.print_error('No executables found to package')

			return None, None
		
		documentation_files = ['README.md', 'LICENSE', 'CHANGELOG.md', 'requirements.txt']
		
		for doc_file in documentation_files:
			src = self.project_root / doc_file
			
			if src.exists():
				shutil.copy2(src, release_path / doc_file)
				
				self.print_info(f'Added: {doc_file}')
		
		manifest_path = release_path / 'build_manifest.json'

		with open(manifest_path, 'w', encoding='utf-8') as f:
			json.dump(build_manifest, f, indent=2, ensure_ascii=False)
		
		self.print_success('Created build manifest')
		
		archive_name = f'{release_name}.zip'
		archive_path = self.releases_dir / archive_name
		
		shutil.make_archive(
			str(archive_path.with_suffix('')),
			'zip',
			release_path
		)
		
		self.print_success(f'Created archive: {archive_name}')
		
		return release_path, archive_path
	
	def cleanup_build_artifacts(self):
		self.print_step('Cleaning build artifacts...')
		
		if self.build_dir.exists():
			shutil.rmtree(self.build_dir)

			self.print_info('Removed build directory')
		
		if self.temp_build_env.exists():
			shutil.rmtree(self.temp_build_env)

			self.print_info('Removed temporary build sandbox')
		
		pyd_files = list(self.project_root.glob('*.pyd'))
		so_files = list(self.project_root.glob('*.so'))
		
		for ext_file in pyd_files + so_files:
			try:
				ext_file.unlink()
			except:
				pass
		
		self.print_success('Build artifacts cleaned')
		
		return True
	
	def print_build_summary(self, release_path, archive_path):
		self.print_header('BUILD SUMMARY')
		
		print(f'{Fore.CYAN}Version:{Fore.RESET} {Style.BRIGHT}{self.version}{Style.RESET_ALL}')
		print(f'{Fore.CYAN}Build Time:{Fore.RESET} {self.build_timestamp}')
		print(f'{Fore.CYAN}Protection Layers:{Fore.RESET}')
		print(f'  • Cryptographic Hall of Mirrors (75+ Decoy Layers)')
		print(f'  • Silent Failure Protocol (Phantom Mode)')
		print(f'  • Mathematical Entanglement (Coordinate Distortion)')
		print(f'  • Temporal Distortion (Progressive Poisoning)')
		print(f'  • Total Compilation (Cython)')
		print(f'  • Enhanced AntiDebug (Windows API)')
		print(f'  • Distributed Integrity Checks')
		
		print(f'\n{Style.BRIGHT}{Fore.GREEN}Release Contents:{Fore.RESET}')
		
		if release_path and release_path.exists():
			for item in sorted(release_path.iterdir()):
				if item.is_file():
					size_mb = item.stat().st_size / 1024 / 1024

					print(f'  • {item.name:<40} ({size_mb:>6.2f} MB)')
		
		print(f'\n{Fore.YELLOW}Release Location:{Fore.RESET}')

		if release_path:
			print(f'  {release_path}')
		
		print(f'\n{Fore.YELLOW}Archive Location:{Fore.RESET}')

		if archive_path:
			print(f'  {archive_path}')
	
	def execute_build_pipeline(self):
		self.print_header(f'MENTALIST BUILD SYSTEM v{self.version}')
		
		pipeline_steps = [
			('Environment Check', self.check_environment),
			('Workspace Cleanup', self.clean_workspace),
			('Source Verification', self.prepare_source_files),
			('Build Sandbox Creation', self.create_build_sandbox),
			('Decoy Injection', self.inject_decoy_layers),
			('Protection Compilation', self.compile_protection_layer),
			('Core Compilation', self.compile_core_layer),
			('Integrity Finalization', self.finalize_integrity_system),
			('CLI Build', lambda: self.build_executable('cli')),
			('GUI Build', lambda: self.build_executable('gui')),
			('Release Package', self.create_release_package),
			('Artifact Cleanup', self.cleanup_build_artifacts)
		]
		
		total_steps = len(pipeline_steps)
		completed_steps = 0
		
		release_path = None
		archive_path = None
		
		for step_num, (step_name, step_func) in enumerate(pipeline_steps, 1):
			print(f'\n{Style.BRIGHT}{Fore.MAGENTA}[Step {step_num}/{total_steps}] {step_name}{Fore.RESET}')
			
			try:
				if step_name == 'Release Package':
					result = step_func()

					if result and len(result) == 2:
						release_path, archive_path = result

						if release_path and archive_path:
							completed_steps += 1

						else:
							self.print_error(f'{step_name} failed')

							break

					else:
						self.print_error(f'{step_name} failed')

						break

				else:
					result = step_func()

					if result:
						completed_steps += 1
						
					else:
						if step_name in ['GUI Build', 'Protection Verification', 'Decoy Injection']:
							self.print_warning(f'{step_name} skipped or failed, continuing...')
							
							completed_steps += 1

						else:
							self.print_error(f'{step_name} failed')

							break
			except Exception as e:
				self.print_error(f'{step_name} crashed: {str(e)}')

				import traceback

				traceback.print_exc()

				break
		
		success = (completed_steps >= total_steps - 1)
		
		if success:
			self.print_build_summary(release_path, archive_path)
			
			print(f'\n{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}')
			print(f'{Style.BRIGHT}{Back.GREEN}{"BUILD COMPLETED SUCCESSFULLY".center(80)}{Back.RESET}')
			print(f'{Style.BRIGHT}{Back.GREEN}{"═" * 80}{Back.RESET}\n')

		else:
			print(f'\n{Style.BRIGHT}{Back.RED}{"═" * 80}{Back.RESET}')
			print(f'{Style.BRIGHT}{Back.RED}{"BUILD FAILED".center(80)}{Back.RESET}')
			print(f'{Style.BRIGHT}{Back.RED}{"═" * 80}{Back.RESET}\n')
		
		return success


def main():
	orchestrator = BuildOrchestrator()
	
	try:
		success = orchestrator.execute_build_pipeline()
		sys.exit(0 if success else 1)
	except KeyboardInterrupt:
		print(f'\n\n{Fore.YELLOW}Build interrupted by user{Fore.RESET}')

		sys.exit(1)
	except Exception as e:
		print(f'\n{Style.BRIGHT}{Fore.RED}Critical error: {str(e)}{Fore.RESET}')

		import traceback

		traceback.print_exc()
		sys.exit(1)


if __name__ == '__main__':
	main()
