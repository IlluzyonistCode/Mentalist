import requests
import hashlib
import json
import sys
import re
from pathlib import Path
from dotenv import dotenv_values
from colorama import Back, Fore, Style, init

init(autoreset=True)

requests.packages.urllib3.disable_warnings()

config = dotenv_values('config.txt')
SERVER_URL = config.get('MENTALIST_SERVER_URL')
ADMIN_SECRET = config.get('MENTALIST_ADMIN_SECRET')


class MentalistAdmin:
	def __init__(self):
		self.server_url = SERVER_URL.rstrip('/')
		self.admin_secret = ADMIN_SECRET
		self.session = requests.Session()
		self.build_types = ['cli', 'gui', 'mobile']
	
	def get_server_health(self):
		try:
			response = requests.get(f'{self.server_url}/health', timeout=5)
			
			if response.status_code == 200:
				data = response.json()
				uptime_hours = data.get('uptime_seconds', 0) / 3600
				
				print(f'\n{Style.BRIGHT}{Fore.GREEN}🟢 Server Status: Online{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Server URL: {self.server_url}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Uptime: {uptime_hours:.2f} hours{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Total Syncs: {data.get("total_syncs", 0)}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Active Clients: {data.get("active_clients", 0)}{Fore.RESET}')
				
				return True
		except Exception as e:
			print(f'\n{Style.BRIGHT}{Fore.RED}🔴 Server Status: Offline{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.YELLOW}Error: {str(e)}{Fore.RESET}')
			
			return False
	
	def get_user_by_id(self, user_id):
		response = requests.get(
			f'{self.server_url}/admin/users',
			headers={'X-Admin-Token': self.admin_secret}
		)
		
		if response.status_code != 200:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
			
			return
		
		users = response.json()['users']
		user = next((u for u in users if u['id'] == user_id), None)
		
		if not user:
			print(f'{Style.BRIGHT}{Fore.RED}❌ User with ID {user_id} not found{Fore.RESET}')
			
			return

		return user

	def create_user(self, permissions=31):
		response = requests.post(
			f'{self.server_url}/admin/create_user',
			headers={
				'X-Admin-Token': self.admin_secret,
				'Content-Type': 'application/json'
			},
			json={'permissions': permissions}
		)
		
		if response.status_code == 200:
			data = response.json()

			print(f'\n{Style.BRIGHT}{Fore.GREEN}✅ User created successfully!{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.CYAN}API Key: {Fore.YELLOW}{data["api_key"]}{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.CYAN}Permissions: {Fore.YELLOW}{data["permissions"]}{Fore.RESET}')
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}User should add this to their config.txt file:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Back.BLUE}MENTALIST_SERVER_API_KEY={data["api_key"]}{Back.RESET}')

		else:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
	
	def list_users(self):
		response = requests.get(
			f'{self.server_url}/admin/users',
			headers={'X-Admin-Token': self.admin_secret}
		)
		
		if response.status_code == 200:
			data = response.json()
			users = data['users']
			
			print(f'\n{Style.BRIGHT}{Fore.CYAN}📋 Total Users: {len(users)}{Fore.RESET}\n')
			print(f'{Style.BRIGHT}{"="*140}{Style.RESET_ALL}')
			
			for user in users:
				status_icon = f'{Fore.GREEN}✅' if user['status'] == 1 else f'{Fore.RED}❌'
				status_text = 'Active' if user['status'] == 1 else 'Disabled'
				perms = user['permissions']
				
				modules = []

				if perms & 1: modules.append(f'{Fore.GREEN}Tracker{Fore.RESET}')
				if perms & 2: modules.append(f'{Fore.BLUE}Stalker{Fore.RESET}')
				if perms & 4: modules.append(f'{Fore.MAGENTA}Booster{Fore.RESET}')
				if perms & 8: modules.append(f'{Fore.YELLOW}Spinner{Fore.RESET}')
				if perms & 16: modules.append(f'{Fore.RED}Mastermind{Fore.RESET}')
				
				print(f'{Style.BRIGHT}{Fore.CYAN}ID: {user["id"]}{Fore.RESET} | {status_icon} {status_text}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.YELLOW}API Key: {Fore.WHITE}{user["api_key"]}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Modules: {", ".join(modules) if modules else f"{Fore.RED}None{Fore.RESET}"}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Created: {Fore.WHITE}{user["created_at"]}{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.CYAN}Last Seen: {Fore.WHITE}{user["last_connection"] or "Never"}{Fore.RESET}')
				
				usage_str = (f'{Fore.GREEN}T:{user["usage"]["tracker"]}{Fore.RESET} '
							f'{Fore.BLUE}S:{user["usage"]["stalker"]}{Fore.RESET} '
							f'{Fore.MAGENTA}B:{user["usage"]["booster"]}{Fore.RESET} '
							f'{Fore.YELLOW}Sp:{user["usage"]["spinner"]}{Fore.RESET} '
							f'{Fore.RED}M:{user["usage"]["mastermind"]}{Fore.RESET}')
				
				print(f'{Style.BRIGHT}{Fore.CYAN}Usage: {usage_str}')
				
				if user.get('bearer_token'):
					print(f'{Style.BRIGHT}{Fore.CYAN}Bearer Token: {Fore.WHITE}{user["bearer_token"][:32]}...{Fore.RESET}')
				
				if user.get('refresh_token'):
					print(f'{Style.BRIGHT}{Fore.CYAN}Refresh Token: {Fore.WHITE}{user["refresh_token"][:32]}...{Fore.RESET}')

				if user.get('tracker_api_keys'):
					print(f'{Style.BRIGHT}{Fore.CYAN}Tracker Keys: {Fore.WHITE}{user["tracker_api_keys"]}{Fore.RESET}')
				
				if user.get('stalker_api_keys'):
					print(f'{Style.BRIGHT}{Fore.CYAN}Stalker Keys: {Fore.WHITE}{user["stalker_api_keys"]}{Fore.RESET}')
				
				print(f'{Style.BRIGHT}{"-"*140}{Style.RESET_ALL}')

		else:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
	
	def show_user_details(self, user_id):
		user = self.get_user_by_id(user_id)
		
		if not user:
			return
		
		print(f'\n{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.GREEN}USER DETAILS{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}\n')
		
		status_icon = f'{Fore.GREEN}✅' if user['status'] == 1 else f'{Fore.RED}❌'
		status_text = 'Active' if user['status'] == 1 else 'Disabled'
		
		print(f'{Style.BRIGHT}{Fore.CYAN}Status: {status_icon} {status_text}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}User ID: {Fore.WHITE}{user["id"]}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}API Key: {Fore.YELLOW}{user["api_key"]}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}Permissions: {Fore.WHITE}{user["permissions"]}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}Created: {Fore.WHITE}{user["created_at"]}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.CYAN}Last Connection: {Fore.WHITE}{user["last_connection"] or "Never"}{Fore.RESET}\n')
		
		perms = user['permissions']

		print(f'{Style.BRIGHT}{Fore.YELLOW}Module Access:{Fore.RESET}')
		print(f'  {Fore.GREEN}✅ Tracker{Fore.RESET}' if perms & 1 else f'  {Fore.RED}❌ Tracker{Fore.RESET}')
		print(f'  {Fore.GREEN}✅ Stalker{Fore.RESET}' if perms & 2 else f'  {Fore.RED}❌ Stalker{Fore.RESET}')
		print(f'  {Fore.GREEN}✅ Booster{Fore.RESET}' if perms & 4 else f'  {Fore.RED}❌ Booster{Fore.RESET}')
		print(f'  {Fore.GREEN}✅ Spinner{Fore.RESET}' if perms & 8 else f'  {Fore.RED}❌ Spinner{Fore.RESET}')
		print(f'  {Fore.GREEN}✅ Mastermind{Fore.RESET}' if perms & 16 else f'  {Fore.RED}❌ Mastermind{Fore.RESET}')
		
		print(f'\n{Style.BRIGHT}{Fore.YELLOW}Usage Statistics:{Fore.RESET}')
		print(f'  {Fore.GREEN}Tracker: {user["usage"]["tracker"]} requests{Fore.RESET}')
		print(f'  {Fore.BLUE}Stalker: {user["usage"]["stalker"]} requests{Fore.RESET}')
		print(f'  {Fore.MAGENTA}Booster: {user["usage"]["booster"]} requests{Fore.RESET}')
		print(f'  {Fore.YELLOW}Spinner: {user["usage"]["spinner"]} requests{Fore.RESET}')
		print(f'  {Fore.RED}Mastermind: {user["usage"]["mastermind"]} requests{Fore.RESET}')
		
		total_requests = sum(user['usage'].values())

		print(f'\n{Style.BRIGHT}{Fore.CYAN}Total Requests: {Fore.WHITE}{total_requests}{Fore.RESET}')
		
		if user.get('bearer_token'):
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Bearer Token:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.WHITE}{user["bearer_token"]}{Fore.RESET}')
		
		if user.get('refresh_token'):
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Refresh Token:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.WHITE}{user["refresh_token"]}{Fore.RESET}')

		if user.get('tracker_api_keys'):
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Tracker API Keys:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.WHITE}{user["tracker_api_keys"]}{Fore.RESET}')
		
		if user.get('stalker_api_keys'):
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Stalker API Keys:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.WHITE}{user["stalker_api_keys"]}{Fore.RESET}')
		
		print(f'\n{Style.BRIGHT}{Fore.CYAN}{"="*80}{Fore.RESET}')
	
	def disable_user(self, user_id):
		user = self.get_user_by_id(user_id)
		
		if not user:
			return
		
		api_key = user['api_key']
		
		response = requests.post(
			f'{self.server_url}/admin/disable_user',
			headers={
				'X-Admin-Token': self.admin_secret,
				'Content-Type': 'application/json'
			},
			json={'api_key': api_key}
		)
		
		if response.status_code == 200:
			print(f'{Style.BRIGHT}{Fore.GREEN}✅ User #{user_id} disabled ({api_key[:32]}...){Fore.RESET}')
		
		else:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
	
	def delete_user(self, user_id):
		user = self.get_user_by_id(user_id)
		
		if not user:
			return
		
		api_key = user['api_key']
		
		confirm = input(f'{Style.BRIGHT}{Fore.RED}⚠️  Are you sure you want to DELETE user #{user_id} ({api_key[:32]}...)? (yes/no): {Fore.RESET}')
		
		if confirm.lower() != 'yes':
			print(f'{Style.BRIGHT}{Fore.YELLOW}Cancelled.{Fore.RESET}')

			return
		
		response = requests.post(
			f'{self.server_url}/admin/delete_user',
			headers={
				'X-Admin-Token': self.admin_secret,
				'Content-Type': 'application/json'
			},
			json={'api_key': api_key}
		)
		
		if response.status_code == 200:
			print(f'{Style.BRIGHT}{Fore.GREEN}✅ User #{user_id} deleted ({api_key[:32]}...){Fore.RESET}')
		
		else:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
	
	def set_permissions(self, user_id, permissions):
		user = self.get_user_by_id(user_id)
		
		if not user:
			return
		
		api_key = user['api_key']
		
		response = requests.post(
			f'{self.server_url}/admin/set_permissions',
			headers={
				'X-Admin-Token': self.admin_secret,
				'Content-Type': 'application/json'
			},
			json={'api_key': api_key, 'permissions': permissions}
		)
		
		if response.status_code == 200:
			print(f'{Style.BRIGHT}{Fore.GREEN}✅ Permissions updated for user #{user_id} to {permissions}{Fore.RESET}')
		
		else:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {response.text}{Fore.RESET}')
	
	def calculate_checksum(self, filepath):
		sha256 = hashlib.sha256()

		with open(filepath, 'rb') as f:
			for chunk in iter(lambda: f.read(8192), b''):
				sha256.update(chunk)

		return sha256.hexdigest()
	
	def validate_version(self, version):
		return bool(re.match(r'^\d+\.\d+\.\d+$', version))
	
	def format_size(self, bytes_size):
		for unit in ['B', 'KB', 'MB', 'GB']:
			if bytes_size < 1024.0:
				return f'{bytes_size:.2f} {unit}'

			bytes_size /= 1024.0

		return f'{bytes_size:.2f} TB'
	
	def upload_version(self, file_path, version, build_type, changelog='', required=False):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} UPLOAD VERSION {Back.RESET}')
		print(f'{Fore.CYAN}{"═" * 70}')

		if not file_path.exists():
			print(f'{Style.BRIGHT}{Fore.RED}❌ File not found: {file_path}{Fore.RESET}')
			
			return False

		if not self.validate_version(version):
			print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid version format (use x.x.x){Fore.RESET}')
			
			return False
		
		if build_type.lower() not in self.build_types:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid build_type. Must be one of: {", ".join(self.build_types)}{Fore.RESET}')
		   
			return False

		expected_ext = {
			'cli': '.exe',
			'gui': '.exe',
			'mobile': '.zip'
		}
		
		if file_path.suffix.lower() != expected_ext[build_type.lower()]:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid file extension for {build_type}. Expected {expected_ext[build_type.lower()]}{Fore.RESET}')
			
			return False

		print(f'\n{Fore.YELLOW}Preparing upload...')
		print(f'{Fore.CYAN}  File:       {file_path.name}')
		print(f'{Fore.CYAN}  Version:    {version}')
		print(f'{Fore.CYAN}  Build Type: {build_type.upper()}')
		print(f'{Fore.CYAN}  Size:       {self.format_size(file_path.stat().st_size)}')
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
				
				self.session.headers.update({'X-Admin-Token': self.admin_secret})
				
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
					print(f'  Size:         {self.format_size(version_data.get("size", 0))}')
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
					print(f'{Fore.RED}❌ Invalid build_type. Must be one of: {", ".join(self.build_types)}{Fore.RESET}')
					
					return False

				params['build_type'] = build_type.lower()

			self.session.headers.update({'X-Admin-Token': self.admin_secret})
			
			response = self.session.get(
				f'{self.server_url}/api/update/versions',
				params=params,
				timeout=10
			)

			if response.status_code == 200:
				data = response.json()

				if 'build_type' in data:
					self.print_build_versions(data['build_type'], data)

				elif 'all_builds' in data:
					for build in self.build_types:
						build_data = data['all_builds'].get(build, {})

						self.print_build_versions(build, build_data)

						print()

				return True

			else:
				print(f'{Style.BRIGHT}{Fore.RED}❌ Failed to get versions (HTTP {response.status_code}){Fore.RESET}')
				
				return False
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}❌ Error: {str(e)}{Fore.RESET}')

			return False
	
	def print_build_versions(self, build_type, data):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} {build_type.upper()} VERSIONS {Back.RESET}')
		print(f'{Fore.CYAN}{"═" * 70}')

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
				print(f'    Size:     {self.format_size(v["size"])}')
				print(f'    Released: {v["release_date"][:19]}')

				if v.get('changelog'):
					print(f'    Changes:')
					
					for line in v['changelog'].split('\n')[:3]:
						if line.strip():
							print(f'      • {line.strip()}')
	
	def interactive_upload(self):
		print(f'\n{Style.BRIGHT}{Back.MAGENTA} UPLOAD NEW VERSION {Back.RESET}')
		print(f'{Fore.CYAN}{"═" * 70}')

		print(f'\n{Fore.YELLOW}Select build type:{Fore.RESET}')

		for i, build in enumerate(self.build_types, 1):
			print(f'{Fore.CYAN}{i}. {build.upper()}{Fore.RESET}')
		
		build_choice = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()
		
		try:
			build_idx = int(build_choice) - 1

			if build_idx < 0 or build_idx >= len(self.build_types):
				print(f'{Fore.RED}❌ Invalid choice!{Fore.RESET}')

				return

			build_type = self.build_types[build_idx]
		except ValueError:
			print(f'{Fore.RED}❌ Invalid input!{Fore.RESET}')

			return

		ext_hint = {
			'cli': '.exe',
			'gui': '.exe',
			'mobile': '.zip'
		}
		
		print(f'\n{Fore.YELLOW}Enter path to file ({ext_hint[build_type]}):{Fore.RESET}')
		
		file_path = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()
		file_path_obj = Path(file_path)

		if not file_path_obj.exists():
			print(f'{Fore.RED}❌ File not found!{Fore.RESET}')

			return

		print(f'\n{Fore.YELLOW}Enter version number (x.x.x):{Fore.RESET}')

		version = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()

		if not self.validate_version(version):
			print(f'{Fore.RED}❌ Invalid version format!{Fore.RESET}')

			return

		print(f'\n{Fore.YELLOW}Enter changelog (press Enter twice to finish):{Fore.RESET}')
		
		changelog_lines = []

		while True:
			line = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ')

			if not line and changelog_lines:
				break

			if line:
				changelog_lines.append(line)

		changelog = '\n'.join(changelog_lines)

		print(f'\n{Fore.YELLOW}Is this a required update? (y/N):{Fore.RESET}')

		required = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip().lower() == 'y'

		print(f'\n{Fore.YELLOW}Upload summary:{Fore.RESET}')
		print(f'{Fore.CYAN}  File:       {file_path_obj.name}')
		print(f'{Fore.CYAN}  Version:    {version}')
		print(f'{Fore.CYAN}  Build Type: {build_type.upper()}')
		print(f'{Fore.CYAN}  Size:       {self.format_size(file_path_obj.stat().st_size)}')
		print(f'{Fore.CYAN}  Required:   {required}')
		print(f'\n{Fore.YELLOW}Proceed with upload? (Y/n):{Fore.RESET}')

		confirm = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip().lower()

		if confirm in ('n', 'no'):
			print(f'{Fore.YELLOW}Upload cancelled{Fore.RESET}')

			return

		self.upload_version(file_path_obj, version, build_type, changelog, required)
	
	def user_management_menu(self):
		print(f'\n{Style.BRIGHT}{Fore.YELLOW}User Management Commands:{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.GREEN}  1.{Fore.RESET} Create user')
		print(f'{Style.BRIGHT}{Fore.GREEN}  2.{Fore.RESET} List users')
		print(f'{Style.BRIGHT}{Fore.GREEN}  3.{Fore.RESET} Show user details')
		print(f'{Style.BRIGHT}{Fore.GREEN}  4.{Fore.RESET} Disable user')
		print(f'{Style.BRIGHT}{Fore.GREEN}  5.{Fore.RESET} Delete user')
		print(f'{Style.BRIGHT}{Fore.GREEN}  6.{Fore.RESET} Set permissions')
		print(f'{Style.BRIGHT}{Fore.GREEN}  0.{Fore.RESET} Back to main menu')
		
		while True:
			choice = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()
			
			if choice == '1':
				print(f'\n{Style.BRIGHT}{Fore.YELLOW}Permissions:{Fore.RESET}')
				print(f'{Style.BRIGHT}{Fore.GREEN}  1  ={Fore.RESET} Tracker only')
				print(f'{Style.BRIGHT}{Fore.BLUE}  2  ={Fore.RESET} Stalker only')
				print(f'{Style.BRIGHT}{Fore.MAGENTA}  4  ={Fore.RESET} Booster only')
				print(f'{Style.BRIGHT}{Fore.YELLOW}  8  ={Fore.RESET} Spinner only')
				print(f'{Style.BRIGHT}{Fore.RED}  16 ={Fore.RESET} Mastermind only')
				print(f'{Style.BRIGHT}{Fore.CYAN}  31 ={Fore.RESET} All modules (default)')

				perms = input(f'\n{Style.BRIGHT}{Fore.YELLOW}Enter permissions (default 31): {Fore.RESET}').strip()
				
				self.create_user(int(perms) if perms else 31)
			
			elif choice == '2':
				self.list_users()
			
			elif choice == '3':
				user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID: {Fore.RESET}').strip()
				
				if user_id.isdigit():
					self.show_user_details(int(user_id))
				
				else:
					print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
			
			elif choice == '4':
				user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID to disable: {Fore.RESET}').strip()
				
				if user_id.isdigit():
					self.disable_user(int(user_id))
				
				else:
					print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
			
			elif choice == '5':
				user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID to delete: {Fore.RESET}').strip()
				
				if user_id.isdigit():
					self.delete_user(int(user_id))
				
				else:
					print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid ID{Fore.RESET}')
			
			elif choice == '6':
				user_id = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter user ID: {Fore.RESET}').strip()
				perms = input(f'{Style.BRIGHT}{Fore.YELLOW}Enter new permissions: {Fore.RESET}').strip()
				
				if user_id.isdigit() and perms.isdigit():
					self.set_permissions(int(user_id), int(perms))
				
				else:
					print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid input{Fore.RESET}')
			
			elif choice == '0':
				break
			
			else:
				print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid option{Fore.RESET}')
	
	def update_management_menu(self):
		print(f'\n{Style.BRIGHT}{Fore.YELLOW}Update Management Commands:{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.GREEN}  1.{Fore.RESET} Upload new version')
		print(f'{Style.BRIGHT}{Fore.GREEN}  2.{Fore.RESET} List all versions (all builds)')
		print(f'{Style.BRIGHT}{Fore.GREEN}  4.{Fore.RESET} List CLI versions')
		print(f'{Style.BRIGHT}{Fore.GREEN}  3.{Fore.RESET} List GUI versions')
		print(f'{Style.BRIGHT}{Fore.GREEN}  5.{Fore.RESET} List Mobile versions')
		print(f'{Style.BRIGHT}{Fore.GREEN}  0.{Fore.RESET} Back to main menu')
		
		while True:
			choice = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()

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
				break

			else:
				print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid option{Fore.RESET}')

	def main_menu(self):
		print(f'\n{Style.BRIGHT}{Fore.RED}{"="*60}{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist {Fore.RED}ADMIN PANEL{Fore.RESET}')
		print(f'{Style.BRIGHT}{Fore.RED}{"="*60}{Fore.RESET}')
		
		self.get_server_health()
		
		while True:
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Main Menu:{Fore.RESET}')
			print(f'{Style.BRIGHT}{Fore.GREEN}  1.{Fore.RESET} User Management')
			print(f'{Style.BRIGHT}{Fore.GREEN}  2.{Fore.RESET} Update Management')
			print(f'{Style.BRIGHT}{Fore.GREEN}  3.{Fore.RESET} Server Health')
			print(f'{Style.BRIGHT}{Fore.GREEN}  0.{Fore.RESET} Exit')
			
			choice = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ').strip()
			
			if choice == '1':
				self.user_management_menu()
			
			elif choice == '2':
				self.update_management_menu()
			
			elif choice == '3':
				self.get_server_health()
			
			elif choice == '0':
				print(f'\n{Style.BRIGHT}{Fore.GREEN}Goodbye!{Fore.RESET}')
				
				break
			
			else:
				print(f'{Style.BRIGHT}{Fore.RED}❌ Invalid option{Fore.RESET}')


def main():
	if not ADMIN_SECRET:
		print(f'{Style.BRIGHT}{Back.RED}❌ MENTALIST_ADMIN_SECRET not found in config.txt{Back.RESET}')
		
		sys.exit(1)
	
	admin = MentalistAdmin()
	
	try:
		admin.main_menu()
	except KeyboardInterrupt:
		print(f'\n\n{Style.BRIGHT}{Fore.YELLOW}Interrupted by user{Fore.RESET}')
	except Exception as e:
		print(f'\n{Style.BRIGHT}{Fore.RED}❌ Error: {str(e)}{Fore.RESET}')


if __name__ == '__main__':
	main()
