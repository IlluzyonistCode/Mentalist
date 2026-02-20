import requests
import hashlib
import subprocess
import shutil
import json
import os
import sys
import time
import tempfile
from datetime import datetime
from colorama import Fore, Style, Back, init
from pathlib import Path

init(autoreset=True)


class MentalistUpdater:
	def __init__(self, server_url, api_key, current_version, build_type='cli'):
		self.server_url = server_url.rstrip('/')
		self.current_version = current_version
		self.build_type = build_type.lower()
		self.api_key = api_key
		self.update_endpoint = f'{self.server_url}/api/update'
		self.session = requests.Session()
		self.session.headers.update({'X-API-Key': self.api_key})

	def _get_exe_path(self):
		if getattr(sys, 'frozen', False):
			return Path(sys.executable)

		return Path(__file__).parent / f'mentalist_{self.build_type}_v{self.current_version}.exe'

	def _calculate_checksum(self, filepath):
		sha256 = hashlib.sha256()

		with open(filepath, 'rb') as f:
			for chunk in iter(lambda: f.read(8192), b''):
				sha256.update(chunk)

		return sha256.hexdigest()

	def check_for_updates(self, build_type='cli', silent=False):
		try:
			if not silent:
				print(f'{Style.BRIGHT}{Fore.CYAN}[UPDATER]{Fore.RESET} Checking for updates...')

			response = self.session.get(
				f'{self.update_endpoint}/check',
				params={
					'current_version': self.current_version,
					'build_type': build_type
				},
				timeout=10
			)

			if response.status_code == 200:
				data = response.json()

				if data.get('update_available'):
					update_info = data.get('latest_version', {})

					if not silent:
						print(f'{Style.BRIGHT}{Fore.GREEN}[UPDATER]{Fore.RESET} New version available!')
						print(f'{Fore.YELLOW}  Current: {self.current_version}')
						print(f'{Fore.GREEN}  Latest:  {update_info.get("version")}')
						print(f'{Fore.CYAN}  Type:    {self.build_type.upper()}')
						print(f'{Fore.CYAN}  Size:    {self._format_size(update_info.get("size", 0))}')

						if update_info.get('changelog'):
							print(f'\n{Fore.MAGENTA}Changelog:')

							for line in update_info.get('changelog', '').split('\n'):
								if line.strip():
									print(f"  • {line.strip()}")

					return True, update_info

				else:
					if not silent:
						print(f'{Style.BRIGHT}{Fore.GREEN}[UPDATER]{Fore.RESET} You are running the latest {self.build_type.upper()} version!')

					return False, None

			else:
				if not silent:
					print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Failed to check for updates (HTTP {response.status_code})')

				return False, None
		except requests.exceptions.RequestException as e:
			if not silent:
				print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Connection error: {str(e)}')

			return False, None
		except Exception as e:
			if not silent:
				print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Error: {str(e)}')

			return False, None

	def download_update(self, update_info, progress_callback=None):
		try:
			version = update_info.get('version')

			print(f'\n{Style.BRIGHT}{Fore.CYAN}[UPDATER]{Fore.RESET} Downloading {self.build_type.upper()} version {version}...')

			response = self.session.get(
				f'{self.update_endpoint}/download',
				params={
					'version': version,
					'build_type': self.build_type
				},
				stream=True,
				timeout=300
			)

			if response.status_code != 200:
				print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Download failed (HTTP {response.status_code})')
				
				return

			total_size = int(response.headers.get('content-length', 0))

			suffix_map = {
				'gui': '.exe',
				'cli': '.exe',
				'mobile': '.zip'
			}
			suffix = suffix_map.get(self.build_type, '.exe')
			
			temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
			temp_path = Path(temp_file.name)
			downloaded = 0
			chunk_size = 8192

			with open(temp_path, 'wb') as f:
				for chunk in response.iter_content(chunk_size=chunk_size):
					if chunk:
						f.write(chunk)
						downloaded += len(chunk)

						if progress_callback:
							progress_callback(downloaded, total_size)

						else:
							if total_size > 0:
								percent = (downloaded / total_size) * 100
								bar_length = 40
								filled = int(bar_length * downloaded / total_size)
								bar = '█' * filled + '░' * (bar_length - filled)
								
								print(f"\r  {bar} {percent:.1f}% ({self._format_size(downloaded)}/{self._format_size(total_size)})", end='')

			print()

			expected_checksum = update_info.get('checksum')

			if expected_checksum:
				print(f'{Style.BRIGHT}{Fore.CYAN}[UPDATER]{Fore.RESET} Verifying download integrity...')
				
				actual_checksum = self._calculate_checksum(temp_path)

				if actual_checksum.lower() != expected_checksum.lower():
					print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Checksum mismatch! Download corrupted.')
					
					temp_path.unlink()
					
					return

				print(f'{Style.BRIGHT}{Fore.GREEN}[UPDATER]{Fore.RESET} Checksum verified!')

			return temp_path
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Download error: {str(e)}')
	   
	def apply_update(self, update_file, new_version):
		try:
			current_exe = self._get_exe_path()
			backup_path = current_exe.with_suffix(current_exe.suffix + '.backup')
			
			print(f'\n{Style.BRIGHT}{Fore.CYAN}[UPDATER]{Fore.RESET} Applying {self.build_type.upper()} update...')
			
			if current_exe.exists():
				print(f'{Fore.YELLOW}  Creating backup...')

				shutil.copy2(current_exe, backup_path)

			self.current_version = new_version
			new_exe = self._get_exe_path()
			
			print(f'{Fore.YELLOW}  Installing new version...')

			shutil.copy2(update_file, new_exe)
			update_file.unlink()

			if current_exe != new_exe and current_exe.exists():
				current_exe.unlink()
			
			print(f'{Style.BRIGHT}{Fore.GREEN}[UPDATER]{Fore.RESET} Update applied successfully!')
			print(f'{Fore.YELLOW}  Backup saved as: {backup_path.name}')
			
			return True
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Failed to apply update: {str(e)}')

			if backup_path.exists():
				print(f'{Fore.YELLOW}  Restoring from backup...')

				try:
					shutil.copy2(backup_path, current_exe)

					print(f'{Fore.GREEN}  Backup restored successfully')
				except:
					pass

			return False

	def restart_application(self):
		try:
			current_exe = self._get_exe_path()

			print(f'\n{Style.BRIGHT}{Fore.CYAN}[UPDATER]{Fore.RESET} Restarting application...')
			
			time.sleep(1)

			if getattr(sys, 'frozen', False):
				subprocess.Popen([str(current_exe)])

			else:
				subprocess.Popen([sys.executable, sys.argv[0]])

			sys.exit(0)
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}[UPDATER]{Fore.RESET} Failed to restart: {str(e)}')
			print(f'{Fore.YELLOW}Please restart the application manually.')

	def perform_update(self, auto_restart=False):
		update_available, update_info = self.check_for_updates()

		if not update_available:
			return False

		print()

		downloaded_file = self.download_update(update_info)

		if not downloaded_file:
			return False

		success = self.apply_update(downloaded_file, update_info.get('version'))

		if success and auto_restart:
			self.restart_application()

		return success

	def interactive_update(self):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} MENTALIST AUTO-UPDATER {Back.RESET}')

		print(f"{Fore.CYAN}{'─' * 60}")

		update_available, update_info = self.check_for_updates()

		if not update_available:
			input(f'\n{Fore.CYAN}Press Enter to continue...')

			return

		print(f'\n{Fore.YELLOW}Do you want to download and install this update?')

		choice = input(f'{Fore.CYAN}[Y/n]: {Fore.RESET}').strip().lower()

		if choice in ('n', 'no'):
			print(f'{Fore.YELLOW}Update cancelled.')

			return

		downloaded_file = self.download_update(update_info)

		if not downloaded_file:
			input(f'\n{Fore.RED}Press Enter to continue...')

			return

		success = self.apply_update(downloaded_file, update_info.get('version'))

		if not success:
			input(f'\n{Fore.RED}Press Enter to continue...')

			return

		print(f'\n{Fore.YELLOW}Do you want to restart the application now?')

		choice = input(f'{Fore.CYAN}[Y/n]: {Fore.RESET}').strip().lower()

		if choice not in ('n', 'no'):
			self.restart_application()

		else:
			print(f'\n{Fore.GREEN}Update complete! Please restart manually to use the new version.')
			input(f'\n{Fore.CYAN}Press Enter to continue...')

	@staticmethod
	def _format_size(bytes_size):
		for unit in ['B', 'KB', 'MB', 'GB']:
			if bytes_size < 1024.0:
				return f"{bytes_size:.2f} {unit}"

			bytes_size /= 1024.0

		return f'{bytes_size:.2f} TB'


class EelUpdater(MentalistUpdater):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.eel_available = False

		try:
			import eel

			self.eel = eel
			self.eel_available = True
		except ImportError:
			pass

		self.build_type = 'gui'

	def send_update(self, event_type, data):
		if self.eel_available:
			try:
				self.eel.update_progress(event_type, data)
			except:
				pass

	def check_for_updates_gui(self):
		try:
			update_available, update_info = self.check_for_updates(build_type='gui', silent=True)

			return {
				'success': True,
				'update_available': update_available,
				'update_info': update_info or {},
				'current_version': self.current_version,
				'build_type': self.build_type
			}
		except Exception as e:
			return {
				'success': False,
				'error': str(e)
			}

	def download_update_gui(self, update_info):
		try:
			self.send_update('download_started', {
				'version': update_info.get('version'),
				'build_type': 'gui'}
			)

			def progress_callback(downloaded, total):
				percent = (downloaded / total * 100) if total > 0 else 0

				self.send_update('download_progress', {
					'percent': percent,
					'downloaded': downloaded,
					'total': total
				})

			downloaded_file = self.download_update(update_info, progress_callback)

			if downloaded_file:
				self.send_update('download_complete', {'file': str(downloaded_file)})

				return {
					'success': True,
					'file': str(downloaded_file)
				}

			else:
				self.send_update('download_failed', {})

				return {
					'success': False,
					'error': 'Download failed'
				}
		except Exception as e:
			self.send_update('download_failed', {'error': str(e)})

			return {
				'success': False,
				'error': str(e)
			}

	def apply_update_gui(self, update_file_path, update_info):
		try:
			self.send_update('install_started', {})

			success = self.apply_update(Path(update_file_path), update_info.get('version'))

			if success:
				self.send_update('install_complete', {})

				return {'success': True}

			self.send_update('install_failed', {})

			return {'success': False, 'error': 'Installation failed'}
		except Exception as e:
			self.send_update('install_failed', {'error': str(e)})

			return {
				'success': False,
				'error': str(e)
			}
