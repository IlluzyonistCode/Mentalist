import gevent
import uiautomator2 as u2
import xml.etree.ElementTree as ET
import threading
import subprocess
import os
import sys
import time
import random
from playsound3 import playsound
from colorama import Back, Fore, Style, init
from dotenv import dotenv_values
from auth_decorator import require_module_auth
from auth_protection import _integrity_checker
from utils import CONFIG_PATH, get_resource_path, banner

if sys.platform == 'win32':
	import psutil
	import pyautogui
	import pywinauto
	import pygetwindow

init(autoreset=True)

PACKAGE = 'com.werewolfapps.online'
ADB_DEFAULT_PORT = 5555


def _adb(*args, serial=None, timeout=20):
	cmd = ['adb']

	if serial:
		cmd += ['-s', serial]

	cmd += list(args)

	return subprocess.run(cmd, capture_output=True, timeout=timeout)

def _adb_out(*args, serial=None, timeout=20):
	return _adb(*args, serial=serial, timeout=timeout).stdout.decode(errors='replace').strip()

def _adb_shell(*args, serial=None, timeout=20):
	return _adb_out('shell', *args, serial=serial, timeout=timeout)

def list_adb_devices():
	out = _adb_out('devices', '-l')
	devices = []

	for line in out.splitlines()[1:]:
		line = line.strip()

		if not line or 'offline' in line:
			continue

		parts = line.split()

		if len(parts) < 2:
			continue

		serial = parts[0]
		state = parts[1]
		tags = {kv.split(':')[0]: kv.split(':')[1] for kv in parts[2:] if ':' in kv}

		devices.append({
			'serial': serial,
			'state': state,
			'transport': 'wifi' if ':' in serial else 'usb',
			'model': tags.get('model', ''),
			'product': tags.get('product', '')
		})

	return devices

def connect_wifi(host, port=ADB_DEFAULT_PORT):
	out = _adb_out('connect', f'{host}:{port}')
	ok = 'connected' in out.lower() and 'unable' not in out.lower() and 'failed' not in out.lower()

	return ok, out

def get_screen_resolution(serial):
	out = _adb_shell('wm', 'size', serial=serial)

	for token in out.split():
		if 'x' in token:
			try:
				w, h = token.split('x')

				return int(w), int(h)
			except ValueError:
				pass

	return 1080, 1920

def _get_device_ip(serial):
	for iface in ('wlan0', 'wlan1', 'eth0'):
		out = _adb_shell('ip', '-f', 'inet', 'addr', 'show', iface, serial=serial)

		for line in out.split('\n'):
			if 'inet ' in line:
				try:
					ip = line.split()[1].split('/')[0]

					if ip and not ip.startswith('127.'):
						return ip
				except (IndexError, ValueError):
					pass

	out = _adb_shell('ip', 'route', serial=serial)

	for line in out.split('\n'):
		if 'src' in line:
			parts = line.split()

			try:
				idx = parts.index('src')

				if idx + 1 < len(parts):
					return parts[idx + 1]
			except (ValueError, IndexError):
				pass

	return None

def _hr(char='─', width=56):
	print(f'{Fore.CYAN}{char * width}{Fore.RESET}')

def _title(text):
	_hr()
	print(f'{Style.BRIGHT}{Fore.CYAN}  {text}{Fore.RESET}')
	_hr()

def _step(n, text):
	print(f'  {Style.BRIGHT}{Fore.YELLOW}[{n}]{Fore.RESET} {text}')

def _ok(text):
	print(f'  {Style.BRIGHT}{Fore.GREEN}✔  {text}{Fore.RESET}')

def _err(text):
	print(f'  {Style.BRIGHT}{Fore.RED}✘  {text}{Fore.RESET}')

def _info(text):
	print(f'  {Fore.CYAN}→  {text}{Fore.RESET}')

def _prompt(text):
	return input(f'  {Style.BRIGHT}{Fore.WHITE}{text}{Fore.RESET} ').strip()

def _auto_setup_device(config_device_id):
	_title('Automatic ADB Setup')

	_info('Starting ADB server...')
	_adb_out('start-server')

	time.sleep(1)

	devices = list_adb_devices()
	wifi_devices = [d for d in devices if d['state'] == 'device' and d['transport'] == 'wifi']
	usb_devices  = [d for d in devices if d['state'] == 'device' and d['transport'] == 'usb']

	if config_device_id:
		for d in wifi_devices:
			if d['serial'] == config_device_id:
				_ok(f'Config device found via WiFi: {config_device_id}')

				return config_device_id

	if wifi_devices:
		serial = wifi_devices[0]['serial']

		_ok(f'Found WiFi device: {serial}')

		return serial

	if usb_devices:
		usb_serial = usb_devices[0]['serial']
		model = usb_devices[0].get('model') or usb_serial

		_info(f'Found USB device: {model} ({usb_serial})')
		_info('Enabling TCP/IP mode on port 5555...')

		_adb_shell('tcpip', '5555', serial=usb_serial)

		time.sleep(2)

		_info('Getting device IP...')

		ip_address = _get_device_ip(usb_serial)

		if not ip_address:
			_err('Could not detect device IP automatically.')
			_info('Trying to use USB connection directly...')

			return usb_serial

		_info(f'Device IP: {ip_address}')
		_info('Connecting via WiFi...')

		ok, msg = connect_wifi(ip_address, 5555)

		if ok:
			_ok(f'Connected to {ip_address}:5555')

			time.sleep(1)

			_adb('disconnect', usb_serial)

			time.sleep(1)

			return f'{ip_address}:5555'

		else:
			_err(f'WiFi connection failed: {msg}')
			_info('Falling back to USB connection...')

			return usb_serial

	return None

def _wizard_show_instructions():
	_title('ADB over WiFi — Manual Setup')
	print()
	print(f'  {Style.BRIGHT}Make sure your phone and PC are on the same WiFi network.{Style.RESET_ALL}')
	print()

	_step(1, 'Enable Developer Options on your phone:')
	_info('Settings → About phone → tap "Build number" 7 times')
	print()

	_step(2, 'Enable USB Debugging:')
	_info('Settings → Developer Options → USB Debugging → ON')
	print()

	_step(3, f'{Style.BRIGHT}Android 11+{Style.RESET_ALL} — Wireless Debugging (recommended):')
	_info('Settings → Developer Options → Wireless Debugging → ON')
	_info('Tap "Pair device with pairing code" — note the IP:port + code')
	_info('Run in a separate terminal:')
	print(f'      {Style.BRIGHT}{Fore.GREEN}adb pair <IP>:<pairing-port>{Fore.RESET}')
	_info('Then connect with the IP:port shown on the main Wireless Debugging screen')
	print()

	_step(3, f'{Style.BRIGHT}Android 10 and below{Style.RESET_ALL} — USB method:')
	_info('Connect phone via USB cable')
	_info('In a terminal run:')
	print(f'      {Style.BRIGHT}{Fore.GREEN}adb tcpip 5555{Fore.RESET}')
	_info('Disconnect USB — phone IP is in Settings → About → Status')
	print()

	_step(4, 'Connect here:')
	_info('Choose option [1] in the menu below and enter your phone\'s IP')
	print()

def _wizard_menu(config_device_id):
	serial = _auto_setup_device(config_device_id)

	if serial:
		return serial

	_wizard_show_instructions()

	while True:
		_hr('·')

		print(f'\n  {Style.BRIGHT}What would you like to do?{Style.RESET_ALL}\n')
		print(f'  {Style.BRIGHT}[1]{Style.RESET_ALL}  Connect to device by IP (WiFi ADB)')
		print(f'  {Style.BRIGHT}[2]{Style.RESET_ALL}  Use already connected devices (adb devices)')
		print(f'  {Style.BRIGHT}[3]{Style.RESET_ALL}  Refresh device list')
		print(f'  {Style.BRIGHT}[0]{Style.RESET_ALL}  Exit')
		print()

		choice = _prompt('Your choice →')

		if choice == '0':
			return

		elif choice == '1':
			ip = _prompt('Phone IP address →')

			if not ip:
				_err('Empty IP, try again.')

				continue

			port_raw = _prompt(f'Port (Enter = {ADB_DEFAULT_PORT}) →')
			port = int(port_raw) if port_raw.isdigit() else ADB_DEFAULT_PORT

			_info(f'Connecting to {ip}:{port} ...')

			ok, msg = connect_wifi(ip, port)

			if ok:
				_ok(f'Connected: {msg}')

			else:
				_err(f'Connection failed: {msg}')
				_info('Check IP, port, and that Wireless Debugging is active.')

				continue

		elif choice in ('2', '3'):
			pass

		else:
			_err('Unknown option.')

			continue

		devices = list_adb_devices()
		ready = [d for d in devices if d['state'] == 'device']

		if not ready:
			_err('No ready ADB devices found.')
			_info('Make sure USB Debugging is enabled and you accepted the RSA prompt on the phone.')

			continue

		if config_device_id:
			for d in ready:
				if d['serial'] == config_device_id:
					_ok(f'Auto-selected device from config: {d["serial"]}')

					return d['serial']

		if len(ready) == 1:
			d = ready[0]

			_ok(f'Found 1 device: {d["serial"]}  {d["model"]}  [{d["transport"]}]')

			return d['serial']

		print()

		_title('Select device')

		for i, d in enumerate(ready):
			tag = f'{d["model"] or d["product"] or "?"}  [{d["transport"]}]'

			print(f'  {Style.BRIGHT}[{i}]{Style.RESET_ALL}  {d["serial"]}  {tag}')

		print()

		while True:
			raw = _prompt('Device number →')

			if raw.isdigit() and 0 <= int(raw) < len(ready):
				return ready[int(raw)]['serial']

			_err('Invalid number, try again.')


class SpinnerDesktop:
	display_name = f'Spinner {Fore.YELLOW}Desktop{Fore.RESET}'
	menu_name = 'Spinner Desktop'

	@require_module_auth('spinner')
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)
		self.is_valid = True
		self.app = None

		if sys.platform != 'win32':
			print(f'{Style.BRIGHT}{Back.RED}Spinner Desktop Error: available only on Windows!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.BLUESTACKS5_EXECUTABLE = self.config['BLUESTACKS5_EXECUTABLE']
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Spinner Desktop Error: Path to BlueStacks 5 not found!{Back.RESET}')

			self.is_valid = False

			return

		if not os.path.isfile(self.BLUESTACKS5_EXECUTABLE):
			print(f'{Style.BRIGHT}{Back.RED}Spinner Desktop Error: Path to BlueStacks 5 is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.BLUESTACKS5_NAME = self.config['BLUESTACKS5_NAME']
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Spinner Desktop Error: Name of BlueStacks 5 not found!{Back.RESET}')

			self.is_valid = False

			return

	def check_stop_flag(self):
		if hasattr(self, '_stop_event'):
			return self._stop_event.is_set()

		try:
			from mentalist_gui import stop_flags

			return stop_flags.get('spinner', threading.Event()).is_set()
		except:
			return False

	def log_message(self, msg_type, message):
		colors = {
			'info': Fore.YELLOW,
			'success': Fore.GREEN,
			'error': Fore.RED,
			'warning': Fore.YELLOW,
			'cyan': Fore.CYAN
		}

		color = colors.get(msg_type, Fore.WHITE)

		print(f'{Style.BRIGHT}{color}{message}{Fore.RESET}')

	@staticmethod
	def wait(filename, confidence=0.9, check_fail=False, check_count=6, click=True, stop_check_callback=None):
		fails = 0

		while True:
			if stop_check_callback and stop_check_callback():
				return -1

			image_path = get_resource_path(os.path.join('images', filename))

			is_phantom = False

			try:
				is_phantom = _integrity_checker.get_corruption_handler().is_phantom_mode()
			except:
				pass

			if is_phantom:
				time.sleep(random.uniform(3.0, 8.0))

			coords = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)

			if coords:
				if click:
					try:
						x, y = coords

						try:
							engine = _integrity_checker.get_entanglement_engine()
							x, y = engine.apply_coordinate_distortion(x, y)
						except:
							pass

						if is_phantom:
							x += random.uniform(-40, 40)
							y += random.uniform(-40, 40)
							time.sleep(random.uniform(2.0, 6.0))

							if random.random() < 0.4:
								time.sleep(random.uniform(4.0, 12.0))

								continue

						pyautogui.click(x, y)
					except pyautogui.FailSafeException:
						continue

				return 0

			if check_fail:
				fails += 1

			if fails == check_count:
				return 1

			time.sleep(5)

	def close_all(self):
		if self.app and self.app.Dialog:
			self.app.Dialog['HD-Player'].type_keys('^+5')

			time.sleep(1)

			self.app.Dialog['HD-Player'].type_keys('{DEL}{ESC}')

	def kill(self):
		self.app = None

		for p in psutil.process_iter():
			if p.name() == 'HD-Player.exe':
				p.kill()

				return

	def spin(self):
		try:
			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Spinner stop requested')

					return -1

				self.log_message('info', 'Checking ad button...')
				self.app.Dialog.click_input(coords=(0, 0))

				result = self.wait('done.png', confidence=0.8, check_fail=True, check_count=3, stop_check_callback=self.check_stop_flag)

				if result == -1:
					return -1

				elif result == 0:
					self.log_message('success', 'DONE!')

					sound_path = get_resource_path(os.path.join('audio', 'confusion.mp3'))
					playsound(sound_path, block=False)

					return 1

				result = self.wait('ad.png', confidence=0.8, check_fail=True, stop_check_callback=self.check_stop_flag)

				if result == -1:
					return -1

				elif result == 1:
					self.log_message('error', 'Loading takes too long.')

					return

				self.log_message('info', 'Watching ad...')

				for _ in range(12):
					if self.check_stop_flag():
						self.log_message('info', 'Spinner stop requested')

						return -1

					time.sleep(5)

				self.app[self.BLUESTACKS5_NAME].Button0.click()

				self.log_message('info', 'Checking spin button...')

				result = self.wait('spin.png', confidence=0.8, check_fail=True, stop_check_callback=self.check_stop_flag)

				if result == -1:
					return -1

				elif result == 1:
					self.log_message('error', 'Spin button not found.')

					return

				else:
					self.log_message('success', 'Spinned!')
		except (pywinauto.findwindows.ElementNotFoundError, OSError):
			return 2

	def prepare(self):
		while True:
			if self.check_stop_flag():
				self.log_message('info', 'Spinner stop requested')

				return False

			try:
				self.log_message('info', 'Waiting for BlueStacks 5...')

				subprocess.Popen(
					[self.BLUESTACKS5_EXECUTABLE, '--cmd', 'launchApp', '--package', PACKAGE],
					stdout=subprocess.PIPE
				)

				try:
					self.app = pywinauto.Application(backend='uia').connect(title=self.BLUESTACKS5_NAME, timeout=30)

					window = pygetwindow.getWindowsWithTitle(self.BLUESTACKS5_NAME)[0]
					window.size = (540, 934)
				except IndexError:
					print(f'{Style.BRIGHT}{Back.RED}Name of BlueStacks 5 window is invalid!{Back.RESET}')

					os.abort()

				self.log_message('info', 'Waiting for game load...')

				result = self.wait('profile.png', click=False, check_fail=True, check_count=12, stop_check_callback=self.check_stop_flag)

				if result == -1:
					return False

				elif result == 1:
					continue

				self.wait('cancel.png', check_fail=True, check_count=3, stop_check_callback=self.check_stop_flag)

				if self.check_stop_flag():
					return False

				self.app.Dialog.click_input(coords=(80, 40))

				self.log_message('success', 'Game loaded!')

				return True

			except:
				if self.check_stop_flag():
					return False

				self.log_message('error', 'The game failed to load.')
				self.log_message('warning', 'Restarting...')

				self.close_all()

				continue

	def run(self):
		try:
			while True:
				banner(self.display_name)

				if self.check_stop_flag():
					self.log_message('info', 'Spinner stop requested')

					self.kill()

					return

				if not self.prepare():
					self.kill()

					return

				result = self.spin()

				if result == -1:
					self.log_message('info', 'Spinner stopped by user')

					self.kill()

					return

				elif result == 1:
					self.kill()

					self.log_message('info', 'Press Enter to exit.')

					input()

					return

				elif result == 2:
					continue

				self.log_message('warning', 'Restarting...')
				self.close_all()
		except KeyboardInterrupt:
			self.kill()

			return


class SpinnerMobile:
	UI_PATTERNS = {
		'play':          r'(ИГРАТЬ|PLAY|OYNA)',
		'rejoin_normal': r'(Твоя игра всё ещё идëт, хочешь вернуться\?|Your game is still running, would you like to rejoin\?|Oynadığın oyun hala devam ediyor, tekrar katılmak ister misin\?)',
		'rejoin_dead':   r'(Твоя последняя игра ещё идёт. Ты уже мёртв, но можешь вернуться, чтобы помочь своей команде или посмотреть конец игры. Переподключиться\?|Your last game is still running. You are already dead but it might still be worth rejoining to help your team or to see how the game ends. Rejoin\?|Son oynadığın oyun hala devam ediyor. Öldün ama oyunun nasıl sona erdiğini görmek ve takımına yardım etmek için geri katılabilirsin. Oyuna tekrar katılmak istiyor musun\?)',
		'cancel':        r'(Отмена|Cancel|Vazgeç)',
		'free_gold':     r'(Бесплатное золото!|Free gold!|Ücretsiz altın!)',
		'ad_watch':      r'(РЕКЛАМА|WATCH VIDEO|REKLAM İZLE)',
		'spin':          r'(КРУТИТЬ|SPIN|ÇEVİR)',
		'done':          r'(Новые награды будут доступны через|New rewards will be available in|Yeni ödüller).*?(\d{1,2}:\d{2}:\d{2})'
	}

	DEBUG_UI = False
	display_name = f'Spinner {Fore.YELLOW}Mobile{Fore.RESET}'
	menu_name = 'Spinner Mobile'

	@require_module_auth('spinner')
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)
		self.is_valid = True
		self._stop_event = threading.Event()

		self.config_device_id = self.config.get('ADB_DEVICE_ID')
		self.serial = ''
		self.width = 1080
		self.height = 1920
		self.d = None

	def _is_phantom(self):
		try:
			return _integrity_checker.get_corruption_handler().is_phantom_mode()
		except:
			return False

	def phantom_delay(self, base_min=0.3, base_max=0.8):
		if self._is_phantom():
			gevent.sleep(random.uniform(8.0, 20.0))

			if random.random() < 0.3:
				gevent.sleep(random.uniform(15.0, 40.0))

		else:
			gevent.sleep(random.uniform(base_min, base_max))

	def phantom_click(self, cx, cy, jitter_base=10):
		if self._is_phantom():
			jitter_x = random.uniform(-60, 60)
			jitter_y = random.uniform(-60, 60)

		else:
			jitter_x = random.uniform(-jitter_base, jitter_base)
			jitter_y = random.uniform(-jitter_base, jitter_base)

		self.phantom_delay()

		if self._is_phantom() and random.random() < 0.35:
			return

		self.d.click(int(cx + jitter_x), int(cy + jitter_y))

	def debug_ui(self):
		if not self.DEBUG_UI or not self.d:
			return

		try:
			xml_data = self.d.dump_hierarchy(compressed=True)
			root = ET.fromstring(xml_data)

			print(f'\n{Fore.CYAN}{"─" * 60}{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.YELLOW}📱 CURRENT UI ELEMENTS (uiautomator2){Fore.RESET}')
			print(f'{Fore.CYAN}{"─" * 60}{Fore.RESET}')

			visible_count = 0

			for node in root.iter('node'):
				text = node.get('text', '').strip()
				desc = node.get('content-desc', '').strip()
				cl = node.get('class', '').split('.')[-1]
				clickable = node.get('clickable') == 'true'
				bounds = node.get('bounds', '')

				if not text and not desc:
					continue

				visible_count += 1
				icon = '🖱️' if clickable else '👁️'
				label = text or desc

				print(f'  {icon} {Style.BRIGHT}{Fore.GREEN}{label:<35}{Fore.RESET} {Fore.RED}class={cl}{Fore.RESET}')

				if bounds:
					print(f'    {Fore.YELLOW}bounds={bounds}{Fore.RESET}')

			if visible_count == 0:
				print(f'  {Fore.RED}⚠️  No visible elements with text/description found.{Fore.RESET}')

			print(f'{Fore.CYAN}{"─" * 60}{Fore.RESET}\n')
		except Exception as e:
			print(f'{Fore.RED}⚠️  UI dump failed: {e}{Fore.RESET}\n')

	def check_stop_flag(self):
		if self._stop_event.is_set():
			return True

		try:
			from mentalist_gui import stop_flags

			return stop_flags.get('spinner', threading.Event()).is_set()
		except:
			return False

	def stop(self):
		self._stop_event.set()

	def log_message(self, msg_type, message):
		colors = {
			'info':    Fore.YELLOW,
			'success': Fore.GREEN,
			'error':   Fore.RED,
			'warning': Fore.YELLOW,
			'cyan':    Fore.CYAN
		}

		color = colors.get(msg_type, Fore.WHITE)

		print(f'{Style.BRIGHT}{color}{message}{Fore.RESET}')

	def wait_text(self, pattern_key, timeout=15.0, interval=1.0, click=True, fail_threshold=None):
		pattern = self.UI_PATTERNS[pattern_key]
		start = time.monotonic()
		fails = 0

		while time.monotonic() - start < timeout:
			if self.check_stop_flag():
				return -1

			try:
				el = self.d(textMatches=pattern)

				if el.exists:
					if click:
						el.click()

					return 0
			except:
				pass

			fails += 1

			if fail_threshold and fails >= fail_threshold:
				self.debug_ui()

				return 1

			gevent.sleep(interval)

		self.debug_ui()

		return 1

	def handle_rejoin_popup(self):
		res = self.wait_text('rejoin_normal', timeout=2.0, interval=0.5, click=False)

		if res == 0:
			self.log_message('info', 'Rejoin popup, cancelling...')

			self.wait_text('cancel', timeout=5.0, interval=0.8, click=True)

			return True

		res = self.wait_text('rejoin_dead', timeout=2.0, interval=0.5, click=False)

		if res == 0:
			self.log_message('info', 'Rejoin popup, cancelling...')

			self.wait_text('cancel', timeout=5.0, interval=0.8, click=True)

			return True

		self.debug_ui()

		return False

	def is_on_main_screen(self):
		try:
			for key in ('spin', 'play', 'free_gold'):
				el = self.d(textMatches=self.UI_PATTERNS[key])

				if el.exists:
					return True
		except:
			pass

		return False

	def close_ad(self):
		for attempt in range(8):
			if self.check_stop_flag():
				return -1

			if self.is_on_main_screen():
				return 0

			self.d.press('back')

			gevent.sleep(2.0)

			res = self.wait_text('spin', timeout=3.0, interval=0.8, click=False, fail_threshold=3)

			if res == 0:
				return 0

		return 1

	def reset_ad_id(self):
		self.log_message('info', 'Resetting advertising ID via UI automation...')

		try:
			_adb_shell('am', 'start', '-a', 'com.google.android.gms.settings.ADS_PRIVACY', serial=self.serial)

			gevent.sleep(1)

			btn = self.d(textMatches=r'(Сбросить рекламный идентификатор|Reset advertising ID|Reklam kimliğini sıfırla)')
			btn.click()

			gevent.sleep(1)

			conf = self.d(textMatches=r'(ОК|OK|ONAYLA)')
			conf.click()

			self.log_message('success', 'Advertising ID reset successfully.')
		except Exception as e:
			self.log_message('warning', f'UI reset failed: {e}')

	def prepare(self):
		while True:
			if self.check_stop_flag():
				return False

			try:
				self.reset_ad_id()

				self.log_message('info', 'Launching game...')

				self.d.app_start(PACKAGE, stop=True)

				gevent.sleep(3)

				self.log_message('info', 'Waiting for main menu...')

				result = self.wait_text('play', timeout=30.0, interval=1.5, click=False, fail_threshold=20)

				if result == -1:
					return False

				if result == 1:
					self.log_message('warning', 'Load timeout, retrying...')

					continue

				self.handle_rejoin_popup()

				self.log_message('info', 'Opening gold wheel...')

				self.wait_text('free_gold', timeout=5.0, interval=0.8, click=True, fail_threshold=6)

				return True

			except Exception as e:
				if self.check_stop_flag():
					return False

				self.log_message('error', f'Game failed to load: {e}')
				self.log_message('warning', 'Force-stopping and retrying...')

				try:
					self.d.app_stop(PACKAGE)
				except:
					pass

				gevent.sleep(3)

	def spin(self):
		try:
			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Stop requested')

					return -1

				self.log_message('info', 'Checking ad button...')

				result = self.wait_text('done', timeout=5.0, interval=1.0, click=False, fail_threshold=5)

				if result == -1:
					return -1

				if result == 0:
					self.log_message('success', 'DONE!')

					sound_path = get_resource_path(os.path.join('audio', 'confusion.mp3'))
					playsound(sound_path, block=True)

					return 1

				result = self.wait_text('ad_watch', timeout=15.0, interval=1.0, click=False, fail_threshold=12)

				if result == -1:
					return -1

				if result == 1:
					self.log_message('error', 'Loading takes too long.')

					return 2

				self.log_message('info', 'Clicking ad button...')

				start_time = time.monotonic()
				ad_launched = False

				while time.monotonic() - start_time < 30:
					if self.check_stop_flag():
						return -1

					try:
						ad_btn = self.d(textMatches=self.UI_PATTERNS['ad_watch'])

						if ad_btn.exists:
							cx, cy = ad_btn.center()

							self.phantom_click(cx, cy)

							gevent.sleep(random.uniform(1.8, 2.6))

						else:
							ad_launched = True

							break
					except Exception as e:
						self.log_message('warning', f'Ad click error: {type(e).__name__}: {e}')

						gevent.sleep(1)

						continue

				if not ad_launched:
					self.log_message('error', 'Ad button stuck, aborting...')

					return 2

				self.log_message('info', 'Watching ad...')

				for _ in range(6):
					if self.check_stop_flag():
						return -1

					gevent.sleep(5)

				self.log_message('info', 'Closing ad...')

				result = self.close_ad()

				if result == -1:
					return -1

				if result == 1:
					self.log_message('error', 'Could not close ad.')

					return 2

				self.log_message('info', 'Checking spin button...')

				result = self.wait_text('spin', timeout=15.0, interval=1.0, fail_threshold=12)

				if result == -1:
					return -1

				if result == 1:
					self.log_message('error', 'Spin button not found.')

					return 2

				self.log_message('success', 'Spinned!')

				gevent.sleep(10)
		except Exception as e:
			self.log_message('error', f'Spin loop exception: {e}')

			return 2

	def run(self):
		serial = _wizard_menu(self.config_device_id)

		if not serial:
			self.log_message('info', 'Exiting.')

			return

		self.serial = serial
		self.width, self.height = get_screen_resolution(self.serial)

		self.log_message('info', 'Connecting to uiautomator2 server...')

		try:
			self.d = u2.connect(self.serial)

			self.log_message('success', f'Device ready: {self.serial}  ({self.width}×{self.height})')
		except Exception as e:
			self.log_message('error', f'Failed to connect via uiautomator2: {e}')
			self.log_message('info', 'Make sure uiautomator2 is installed: pip install uiautomator2')

			return

		try:
			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Spinner stopped.')

					return

				if not self.prepare():
					self.log_message('info', 'Preparation aborted.')

					return

				result = self.spin()

				if result == -1:
					self.log_message('info', 'Stopped by user.')

					return

				if result == 1:
					self.log_message('info', 'Press Enter to exit.')

					try:
						input()
					except KeyboardInterrupt:
						pass

					return

				self.log_message('warning', 'Recoverable error — restarting game...')

				try:
					self.d.app_stop(PACKAGE)
				except:
					pass

				gevent.sleep(3)
		except KeyboardInterrupt:
			self.log_message('info', 'Interrupted by user.')
