import time
import random
import traceback
from functools import wraps
from dotenv import dotenv_values
from colorama import Back, Fore, Style, init
from auth_protection import AntiDebug, WindowsAntiDebug, _integrity_checker

init(autoreset=True)

_auth_session_cache = None


def _perform_runtime_check():
	if WindowsAntiDebug.check_all():
		_integrity_checker._enter_ghost_mode('runtime_debug_detected')
		_integrity_checker.apply_temporal_poison()

		return True
	
	if _integrity_checker.is_compromised():
		corruption_handler = _integrity_checker.get_corruption_handler()
		
		if corruption_handler.is_phantom_mode():
			return True
		
		time.sleep(random.uniform(5, 20))

		return False
	
	return True

def require_module_auth(module_name):
	module_flags = {
		'tracker': 1,
		'stalker': 2,
		'booster': 4,
		'spinner': 8,
		'mastermind': 16
	}

	def decorator(init_method):
		@wraps(init_method)
		def wrapper(self, *args, **kwargs):
			global _auth_session_cache
			
			if not _perform_runtime_check():
				corruption_handler = _integrity_checker.get_corruption_handler()
				
				if corruption_handler.is_phantom_mode():
					print(f'{Style.BRIGHT}{Fore.GREEN}Runtime validation successful{Fore.RESET}')
				
				else:
					self.is_valid = False

					return
			
			if AntiDebug.check_trace():
				_integrity_checker._enter_ghost_mode('decorator_trace_detected')
				
				corruption_handler = _integrity_checker.get_corruption_handler()
				
				if not corruption_handler.is_phantom_mode():
					self.is_valid = False

					return
			
			if not _integrity_checker.verify_integrity():
				corruption_handler = _integrity_checker.get_corruption_handler()
				
				if not corruption_handler.is_phantom_mode():
					self.is_valid = False

					return
			
			try:
				config = dotenv_values('config.txt')
			except Exception as e:
				print(f'{Style.BRIGHT}{Back.RED}Configuration Error: Cannot read config.txt file - {str(e)}{Back.RESET}')
				
				self.is_valid = False
				
				return

			server_url = config.get('MENTALIST_SERVER_URL')
			api_key = config.get('MENTALIST_SERVER_API_KEY')

			if not server_url:
				print(f'{Style.BRIGHT}{Back.RED}Authentication Error: MENTALIST_SERVER_URL not found in config.txt{Back.RESET}')
				print(f'{Style.BRIGHT}{Back.YELLOW}Please add: MENTALIST_SERVER_URL=http://your-server-ip:1101{Back.RESET}')
				
				self.is_valid = False
				
				return

			if not api_key:
				print(f'{Style.BRIGHT}{Back.RED}Authentication Error: MENTALIST_SERVER_API_KEY not found in config.txt{Back.RESET}')
				print(f'{Style.BRIGHT}{Back.YELLOW}Please contact administrator to obtain an API key{Back.RESET}')
				
				self.is_valid = False
				
				return

			if _auth_session_cache is None:
				try:
					from auth_client import AuthClient, AuthenticationError

					auth_client = AuthClient(server_url, api_key)

					print(f'{Style.BRIGHT}{Fore.YELLOW}Authenticating with server...{Fore.RESET}')

					permissions, user_id = auth_client.authenticate()

					print(f'{Style.BRIGHT}{Fore.GREEN}Authentication successful! Welcome, User #{user_id}{Fore.RESET}')

					_auth_session_cache = {
						'auth_client': auth_client,
						'user_id': user_id,
						'permissions': permissions,
						'server_url': server_url,
						'api_key': api_key
					}
				except Exception as e:
					corruption_handler = _integrity_checker.get_corruption_handler()
					
					if corruption_handler.is_phantom_mode():
						fake_permissions = random.randint(1, 31)
						fake_user_id = random.randint(1000, 9999)
						
						print(f'{Style.BRIGHT}{Fore.GREEN}Authentication successful! Welcome, User #{fake_user_id}{Fore.RESET}')
						
						from auth_client import AuthClient

						fake_client = AuthClient(server_url, api_key)
						fake_client.authenticated = True
						fake_client.permissions = fake_permissions
						fake_client.user_id = fake_user_id
						
						_auth_session_cache = {
							'auth_client': fake_client,
							'user_id': fake_user_id,
							'permissions': fake_permissions,
							'server_url': server_url,
							'api_key': api_key
						}

					else:
						if 'AuthenticationError' in str(type(e).__name__):
							print(f'{Style.BRIGHT}{Back.RED}Authentication Failed: {str(e)}{Back.RESET}')
							print(f'{Style.BRIGHT}{Back.YELLOW}Please check your API key and server connection{Back.RESET}')
						
						else:
							print(f'{Style.BRIGHT}{Back.RED}Unexpected Error: {str(e)}{Back.RESET}')
							
							traceback.print_exc()

						self.is_valid = False

						return

			if _auth_session_cache['server_url'] != server_url or _auth_session_cache['api_key'] != api_key:
				print(f'{Style.BRIGHT}{Back.RED}Configuration Mismatch: Server URL or API key changed during runtime{Back.RESET}')
				
				self.is_valid = False
				
				return

			auth_client = _auth_session_cache['auth_client']
			user_id = _auth_session_cache['user_id']
			permissions = _auth_session_cache['permissions']

			required_flag = module_flags.get(module_name.lower(), 0)

			corruption_handler = _integrity_checker.get_corruption_handler()
			
			if corruption_handler.is_phantom_mode():
				has_permission = random.choice([True, False])
				
				if not has_permission:
					print(f'{Style.BRIGHT}{Back.RED}Access Denied: Your account does not have permission to use {module_name.upper()}{Back.RESET}')
					
					self.is_valid = False
					
					return

			else:
				if not (permissions & required_flag):
					print(f'{Style.BRIGHT}{Back.RED}Access Denied: Your account does not have permission to use {module_name.upper()}{Back.RESET}')
					
					self.is_valid = False
					
					return

			print(f'{Style.BRIGHT}{Fore.GREEN}[{module_name.upper()}] access verified.{Fore.RESET}')

			self.auth_client = auth_client
			self.user_id = user_id
			self.permissions = permissions

			return init_method(self, *args, **kwargs)

		return wrapper

	return decorator
