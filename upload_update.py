import requests
import hashlib
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime
from colorama import Fore, Style, Back, init

init(autoreset=True)


class UpdateManager:
	def __init__(self, server_url, admin_token):
		self.server_url = server_url.rstrip('/')
		self.admin_token = admin_token
		self.session = requests.Session()
		self.session.headers.update({
			'X-Admin-Token': admin_token
		})
		self.build_types = ['gui', 'cli', 'mobile']

	def calculate_checksum(self, filepath):
		sha256 = hashlib.sha256()

		with open(filepath, 'rb') as f:
			for chunk in iter(lambda: f.read(8192), b''):
				sha256.update(chunk)

		return sha256.hexdigest()

	def validate_version(self, version):
		return bool(re.match(r'^\d+\.\d+\.\d+$', version))

	def upload_version(self, file_path, version, build_type, changelog='', required=False):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} MENTALIST UPDATE MANAGER {Back.RESET}')
		print(f'{Fore.CYAN}{'═' * 70}')

		if not file_path.exists():
			print(f'{Style.BRIGHT}{Fore.RED}Error: File not found: {file_path}{Fore.RESET}')
			
			return False

		if not self.validate_version(version):
			print(f'{Style.BRIGHT}{Fore.RED}Error: Invalid version format (use x.x.x){Fore.RESET}')
			
			return False
		
		if build_type.lower() not in self.build_types:
			print(f'{Style.BRIGHT}{Fore.RED}Error: Invalid build_type. Must be one of: {", ".join(self.build_types)}{Fore.RESET}')
		   
			return False

		expected_ext = {
			'gui': '.exe',
			'cli': '.exe',
			'mobile': '.zip'
		}
		
		if file_path.suffix.lower() != expected_ext[build_type.lower()]:
			print(f'{Style.BRIGHT}{Fore.RED}Error: Invalid file extension for {build_type}. Expected {expected_ext[build_type.lower()]}{Fore.RESET}')
			
			return False

		print(f'\n{Fore.YELLOW}Preparing upload...')
		print(f'{Fore.CYAN}  File:       {file_path.name}')
		print(f'{Fore.CYAN}  Version:    {version}')
		print(f'{Fore.CYAN}  Build Type: {build_type.upper()}')
		print(f'{Fore.CYAN}  Size:       {self._format_size(file_path.stat().st_size)}')
		print(f'\n{Fore.YELLOW}Calculating checksum...')

		checksum = self.calculate_checksum(file_path)

		print(f'{Fore.GREEN}  Checksum: {checksum[:16]}...{checksum[-16:]}')
		print(f'\n{Fore.YELLOW}Uploading to server...')

		try:
			with open(file_path, 'rb') as f:
				files = {'file': (file_path.name, f, 'application/octet-stream')}
				data = {
					'version': version,
					'build_type': build_type.lower(),
					'changelog': changelog,
					'required': str(required).lower()
				}
				response = self.session.post(
					f'{self.server_url}/api/update/upload',
					files=files,
					data=data,
					timeout=300
				)

			if response.status_code == 200:
				result = response.json()

				if result.get('success'):
					print(f'\n{Style.BRIGHT}{Fore.GREEN}✓ Upload successful!{Fore.RESET}')
					
					version_data = result.get('version', {})

					print(f'\n{Fore.CYAN}Version Information:')
					print(f'  Version:      {version_data.get("version")}')
					print(f'  Build Type:   {version_data.get("build_type", "").upper()}')
					print(f'  Filename:     {version_data.get("filename")}')
					print(f'  Size:         {self._format_size(version_data.get("size", 0))}')
					print(f'  Checksum:     {version_data.get("checksum", "")[:32]}...')
					print(f'  Released:     {version_data.get("release_date", "")[:19]}')
					print(f'  Required:     {version_data.get("required", False)}')

					return True
				else:
					print(f'\n{Style.BRIGHT}{Fore.RED}✗ Upload failed: {result.get("error")}{Fore.RESET}')
					
					return False

			else:
				print(f'\n{Style.BRIGHT}{Fore.RED}✗ Server error (HTTP {response.status_code}){Fore.RESET}')
				
				try:
					error_data = response.json()
					
					print(f'{Fore.RED}  {error_data.get("error", "Unknown error")}{Fore.RESET}')
				except:
					print(f'{Fore.RED}  {response.text}{Fore.RESET}')
				
				return False
		except requests.exceptions.RequestException as e:
			print(f'\n{Style.BRIGHT}{Fore.RED}✗ Connection error: {str(e)}{Fore.RESET}')
			
			return False
		except Exception as e:
			print(f'\n{Style.BRIGHT}{Fore.RED}✗ Error: {str(e)}{Fore.RESET}')
			
			return False

	def list_versions(self, build_type=None):
		try:
			params = {}
			
			if build_type:
				if build_type.lower() not in self.build_types:
					print(f'{Fore.RED}Invalid build_type. Must be one of: {", ".join(self.build_types)}{Fore.RESET}')
					
					return False

				params['build_type'] = build_type.lower()

			response = self.session.get(
				f'{self.server_url}/api/update/versions',
				params=params,
				timeout=10
			)

			if response.status_code == 200:
				data = response.json()

				if 'build_type' in data:
					self._print_build_versions(data['build_type'], data)

				elif 'all_builds' in data:
					for build in self.build_types:
						build_data = data['all_builds'].get(build, {})

						self._print_build_versions(build, build_data)

						print()

				return True

			else:
				print(f'{Style.BRIGHT}{Fore.RED}Failed to get versions (HTTP {response.status_code}){Fore.RESET}')
				
				return False
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}Error: {str(e)}{Fore.RESET}')

			return False

	def _print_build_versions(self, build_type, data):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} {build_type.upper()} VERSIONS {Back.RESET}')
		print(f'{Fore.CYAN}{'═' * 70}')

		latest = data.get('latest')
		
		if latest:
			print(f'\n{Fore.GREEN}Latest version: {latest}{Fore.RESET}')
		
		else:
			print(f'\n{Fore.YELLOW}No versions available for {build_type.upper()}{Fore.RESET}')
			
			return

		versions = data.get('versions', [])

		if versions:
			print(f'\n{Fore.CYAN}All versions:{Fore.RESET}')
			
			for v in versions:
				is_latest = '★' if v['version'] == latest else ' '
				required = '[REQUIRED]' if v.get('required') else ''

				print(f'\n{is_latest} {Fore.YELLOW}{v["version"]}{Fore.RESET} {Fore.RED}{required}{Fore.RESET}')
				print(f'    Size:     {self._format_size(v["size"])}')
				print(f'    Released: {v["release_date"][:19]}')

				if v.get('changelog'):
					print(f'    Changes:')
					
					for line in v['changelog'].split('\n')[:3]:
						if line.strip():
							print(f'      • {line.strip()}')

	@staticmethod
	def _format_size(bytes_size):
		for unit in ['B', 'KB', 'MB', 'GB']:
			if bytes_size < 1024.0:
				return f'{bytes_size:.2f} {unit}'

			bytes_size /= 1024.0

		return f'{bytes_size:.2f} TB'

	def interactive_upload(self):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} UPLOAD NEW VERSION {Back.RESET}')
		print(f'{Fore.CYAN}{"═" * 70}')

		print(f'\n{Fore.YELLOW}Select build type:{Fore.RESET}')

		for i, build in enumerate(self.build_types, 1):
			print(f'{Fore.CYAN}{i}. {build.upper()}{Fore.RESET}')
		
		build_choice = input(f'{Fore.CYAN}> {Fore.RESET}').strip()
		
		try:
			build_idx = int(build_choice) - 1

			if build_idx < 0 or build_idx >= len(self.build_types):
				print(f'{Fore.RED}Invalid choice!{Fore.RESET}')

				return

			build_type = self.build_types[build_idx]
		except ValueError:
			print(f'{Fore.RED}Invalid input!{Fore.RESET}')

			return

		ext_hint = {
			'gui': '.exe',
			'cli': '.exe',
			'mobile': '.zip'
		}
		
		print(f'\n{Fore.YELLOW}Enter path to file ({ext_hint[build_type]}):{Fore.RESET}')
		
		file_path = input(f'{Fore.CYAN}> {Fore.RESET}').strip()
		file_path_obj = Path(file_path)

		if not file_path_obj.exists():
			print(f'{Fore.RED}File not found!{Fore.RESET}')

			return

		print(f'\n{Fore.YELLOW}Enter version number (x.x.x):{Fore.RESET}')

		version = input(f'{Fore.CYAN}> {Fore.RESET}').strip()

		if not self.validate_version(version):
			print(f'{Fore.RED}Invalid version format!{Fore.RESET}')

			return

		print(f'\n{Fore.YELLOW}Enter changelog (press Enter twice to finish):{Fore.RESET}')
		
		changelog_lines = []

		while True:
			line = input(f'{Fore.CYAN}> {Fore.RESET}')

			if not line and changelog_lines:
				break

			if line:
				changelog_lines.append(line)

		changelog = '\n'.join(changelog_lines)

		print(f'\n{Fore.YELLOW}Is this a required update? (y/N):{Fore.RESET}')

		required = input(f'{Fore.CYAN}> {Fore.RESET}').strip().lower() == 'y'

		print(f'\n{Fore.YELLOW}Upload summary:{Fore.RESET}')
		print(f'{Fore.CYAN}  File:       {file_path_obj.name}')
		print(f'{Fore.CYAN}  Version:    {version}')
		print(f'{Fore.CYAN}  Build Type: {build_type.upper()}')
		print(f'{Fore.CYAN}  Size:       {self._format_size(file_path_obj.stat().st_size)}')
		print(f'{Fore.CYAN}  Required:   {required}')
		print(f'\n{Fore.YELLOW}Proceed with upload? (Y/n):{Fore.RESET}')

		confirm = input(f'{Fore.CYAN}> {Fore.RESET}').strip().lower()

		if confirm in ('n', 'no'):
			print(f'{Fore.YELLOW}Upload cancelled{Fore.RESET}')

			return

		self.upload_version(file_path_obj, version, build_type, changelog, required)

	def main_menu(self):
		while True:
			print(f'\n{Style.BRIGHT}{Back.MAGENTA} UPDATE MANAGER MENU {Back.RESET}')
			print(f'{Fore.CYAN}{'═' * 70}')
			print(f'\n{Fore.YELLOW}1.{Fore.RESET} Upload new version')
			print(f'{Fore.YELLOW}2.{Fore.RESET} List all versions (all builds)')
			print(f'{Fore.YELLOW}3.{Fore.RESET} List GUI versions')
			print(f'{Fore.YELLOW}4.{Fore.RESET} List CLI versions')
			print(f'{Fore.YELLOW}5.{Fore.RESET} List Mobile versions')
			print(f'{Fore.RED}0.{Fore.RESET} Exit')

			choice = input(f'\n{Fore.CYAN}Select option: {Fore.RESET}').strip()

			if choice == '1':
				self.interactive_upload()

			elif choice == '2':
				self.list_versions()

			elif choice == '3':
				self.list_versions('gui')

			elif choice == '4':
				self.list_versions('cli')

			elif choice == '5':
				self.list_versions('mobile')

			elif choice == '0':
				print(f'\n{Fore.YELLOW}Goodbye!{Fore.RESET}')

				break

			else:
				print(f'{Fore.RED}Invalid option!{Fore.RESET}')

			if choice in ('1', '2', '3', '4', '5'):
				input(f'\n{Fore.CYAN}Press Enter to continue...{Fore.RESET}')


def main():
	print(f'{Style.BRIGHT}{Back.MAGENTA}{'═' * 70}{Back.RESET}')
	print(f'{Style.BRIGHT}{Back.MAGENTA}         MENTALIST UPDATE MANAGER - ADMIN TOOL                {Back.RESET}')
	print(f'{Style.BRIGHT}{Back.MAGENTA}{'═' * 70}{Back.RESET}')

	server_url = os.environ.get('MENTALIST_SERVER_URL')
	admin_token = os.environ.get('MENTALIST_ADMIN_TOKEN')

	if not server_url:
		print(f'\n{Fore.YELLOW}Enter server URL:{Fore.RESET}')

		server_url = input(f'{Fore.CYAN}> {Fore.RESET}').strip()

	if not admin_token:
		print(f'\n{Fore.YELLOW}Enter admin token:{Fore.RESET}')

		admin_token = input(f'{Fore.CYAN}> {Fore.RESET}').strip()

	if not server_url or not admin_token:
		print(f'\n{Fore.RED}Server URL and admin token are required!{Fore.RESET}')
		
		return

	manager = UpdateManager(server_url, admin_token)

	try:
		manager.main_menu()
	except KeyboardInterrupt:
		print(f'\n\n{Fore.YELLOW}Interrupted by user{Fore.RESET}')
	except Exception as e:
		print(f'\n{Fore.RED}Error: {str(e)}{Fore.RESET}')


if __name__ == '__main__':
	main()
