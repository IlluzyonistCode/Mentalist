import eel
import requests
import threading
import hashlib
import json
import re
import os
import time
import random
from undetected_playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from copy import deepcopy
from colorama import Back, Fore, Style
from dotenv import dotenv_values
from pathlib import Path
from auth_decorator import require_module_auth
from auth_protection import _integrity_checker
from data_protection import save_encrypted, load_encrypted
from translations import (
    match_event,
    is_winner_event,
    is_game_phase,
    parse_player_token,
    extract_role_from_token
)
from utils import (
    MENTALIST_DATA_DIR,
    USER_DATA_DIR,
    CONFIG_PATH,
    VERSION,
    _launch_mode,
    _pause,
    get_resource_path,
    find_chrome_executable,
    generate_random_user_agent,
    MACOS_DISABLE_PLAYWRIGHT_THREADING,
    banner
)
from updater import MentalistUpdater
from analytics import BayesEngine, NLPAnalyzer
from mastermind import Mastermind

class Tracker:
	@require_module_auth('tracker')
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)
		self.is_valid = True

		try:
			self.API_KEYS = self.config['TRACKER_API_KEYS'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = find_chrome_executable()

		if not self.CHROME_EXECUTABLE:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			profile_number = int(self.config.get('CHROME_PROFILE', '1'))

			if profile_number < 1 or profile_number > 10:
				raise ValueError
		except (ValueError, TypeError):
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Chrome Profile must be a number between 1 and 10!{Back.RESET}')
			
			self.is_valid = False

			return

		self.CHROME_USER_DATA = USER_DATA_DIR / f'Mentalist_{profile_number}'

		os.makedirs(self.CHROME_USER_DATA, exist_ok=True)

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Browser Viewport not found!{Back.RESET}')
			
			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Browser Viewport is invalid!{Back.RESET}')
			
			self.is_valid = False

			return

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.API_KEY = self.switch_api_key()

		self.SERVER_ENABLED = self.config.get('SERVER_SYNC_ENABLED', 'false').lower() == 'true'
		self.SERVER_URL = self.config.get('MENTALIST_SERVER_URL', 'http://localhost:1101')
		self.SERVER_API_KEY = self.config.get('MENTALIST_SERVER_API_KEY', '')
		self.SERVER_TIMEOUT = 10

		self.data_hashes = {
			'cards': None,
			'icons': None,
			'role_profiles': None
		}

		self.ASSET_PATHS = {
			'see': {
				'html': 'main.html',
				'css': 'main.css'
			},
			'see2': {
				'html': 'main.html'
			},
			'messages': {
				'html': 'main.html',
				'css': 'main.css'
			}
		}
		self.ASSETS = {}

		self.load_assets()

		self.BEARER_TOKEN = None
		self.CF_JWT = None

		self.BOT_BASE_URL = 'https://api.wolvesville.com/'
		self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'

		self.ROTATION = []
		self.PLAYERS = []
		self.PREV_PLAYERS = []

		self.ROLES = []
		self.ADVANCED_ROLES = {}

		self.RANDOM_ROLE_TYPES = {
			'random-villager-normal': [
				'aura-seer',
				'beast-hunter',
				'bodyguard',
				'doctor',
				'flower-child',
				'loudmouth',
				'mayor',
				'priest',
				'red-lady',
				'sheriff',
				'witch'
			],
			'random-villager-strong': [
				'detective',
				'jailer',
				'medium',
				'seer',
				'vigilante'
			],
			'random-villager-support': [
				'doctor',
				'bodyguard',
				'ghost-lady',
				'sheriff',
				'beast-hunter',
				'bellringer'
			],
			'random-werewolf': 'WEREWOLF',
			'random-werewolf-weak': 'WEREWOLF',
			'random-werewolf-strong': 'WEREWOLF',
			'random-support-werewolf': [
				'nightmare-werewolf',
				'wolf-shaman',
				'toxic-wolf'
			],
			'random-obscuring-werewolf': [
				'nightmare-werewolf',
				'wolf-shaman'
			],
			'random-killer': [
				'arsonist',
				'bandit',
				'corruptor',
				'serial-killer'
			],
			'random-voting': ['fool'],
			'random-other': ['cupid', 'cursed']
		}

		self.ROTATION_ICONS = {}
		self.PLAYER_CARDS = {}
		self.ICONS = {}

		for _ in range(16):
			self.PLAYERS.append({
				'name': None,
				'level': -1,
				'min_level': -1,
				'role': None,
				'team': None,
				'teams_exclude': set(),
				'aura': None,
				'dead': False,
				'equal': set(),
				'not_equal': set(),
				'hero': False,
				'messages': [],
				'mentions': []
			})

		self.DISCOVERED = [False, False]
		self.PLAYER_LAYERS = []

		self.BEARER_HEADERS = {}

		self.page = None
		self.last_message_number = 0

		self.mastermind = None
		self.THREAT_LEVELS = {}
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}

	def _apply_entanglement_distortion(self, x, y):
		try:
			entanglement = _integrity_checker.get_corruption_handler().get_entanglement_engine()
			
			return entanglement.apply_coordinate_distortion(x, y)
		except:
			return x + random.randint(-1, 1), y + random.randint(-1, 1)
	
	def _entangle_statistical_data(self, data):
		try:
			corruption = _integrity_checker.get_corruption_handler()

			if corruption.is_phantom_mode():
				if isinstance(data, dict):
					return {k: self._entangle_statistical_data(v) for k, v in data.items()}
				
				elif isinstance(data, (int, float)):
					return data * random.uniform(0.5, 1.5)
				
				elif isinstance(data, list):
					return [self._entangle_statistical_data(i) for i in data]

			return data
		except:
			return data
	
	def _is_phantom(self):
		try:
			return _integrity_checker.get_corruption_handler().is_phantom_mode()
		except:
			return False

	@staticmethod
	def predict_player_level(received_roses, sent_roses, win_count, lose_count, clan_xp):
		min_levels = [
			(clan_xp // 2000) if clan_xp != -1 else 1,
			(received_roses + sent_roses) // 20 or 1
		]

		return max(min_levels)

	@property
	def bot_headers(self):
		api_key = next(self.API_KEY)

		return {
			'Authorization': f'Bot {api_key}',
			'Accept': 'application/json',
			'Content-Type': 'application/json'
		}

	def init_updater(self):
		if self.SERVER_ENABLED and self.SERVER_URL and self.SERVER_API_KEY:
			self.updater = MentalistUpdater(
				server_url=self.SERVER_URL,
				api_key=self.SERVER_API_KEY,
				current_version=VERSION
			)

			return True

		return False

	def check_updates_menu(self):
		if not hasattr(self, 'updater') or self.updater is None:
			if not self.init_updater():
				print('Update system unavailable')

				return

		self.updater.interactive_update()

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

	def patch_localstorage(self):
		changes = 0

		try:
			self.page.wait_for_function(
				'() => localStorage.getItem("settings") !== null',
				timeout=60000
			)
		except:
			return 0

		raw_settings = self.page.evaluate('() => localStorage.getItem("settings")')

		try:
			settings = json.loads(raw_settings)
		except:
			return 0

		patches = {
			'backgroundMusic': False,
			'darkMode': True,
			'showIntros': False,
			'showRoleHints': False,
			'showWerewolfRolesOnGameGrid': True,
			'soundEffects': False
		}

		for key, value in patches.items():
			if settings.get(key) != value:
				settings[key] = value

				changes += 1

		if changes:
			self.page.evaluate(f'() => localStorage.setItem("settings", JSON.stringify({json.dumps(settings)}))')

		raw_intros = self.page.evaluate('() => localStorage.getItem("intros")')

		if raw_intros:
			try:
				intros = json.loads(raw_intros)
			except:
				return changes

			patched = {
				k: (False if v is True else (0 if v == 1 else v))
				for k, v in intros.items()
			}

			if patched != intros:
				self.page.evaluate(f'() => localStorage.setItem("intros", JSON.stringify({json.dumps(patched)}))')

				changes += 1

		return changes

	def get_bearer(self):
		tokens = self.page.evaluate('''
			() => {
				const authtokens = JSON.parse(localStorage.getItem("authtokens"));

				if (!authtokens) return;

				const cfJwt = localStorage.getItem("cloudflare-turnstile-jwt");

				return {
					idToken: authtokens["idToken"] || null,
					refreshToken: authtokens["refreshToken"] || null,
					cfJwt
				};
			}
		''')

		if not tokens:
			return

		id_token = tokens.get('idToken')
		refresh_token = tokens.get('refreshToken')
		cf_jwt = tokens.get('cfJwt')
		
		if not id_token or not refresh_token:
			return

		self.BEARER_TOKEN = id_token
		self.REFRESH_TOKEN = refresh_token
		self.CF_JWT = cf_jwt

		self.BEARER_HEADERS = {
			'Authorization': f'Bearer {self.BEARER_TOKEN}',
			'Cf-Jwt': self.CF_JWT,
			'Ids': '1'
		}

		if hasattr(self, 'auth_client'):
			try:
				self.auth_client.update_tokens(
					bearer_token=self.BEARER_TOKEN,
					refresh_token=self.REFRESH_TOKEN
				)
			except:
				pass

	def switch_api_key(self):
		while True:
			for key in self.API_KEYS:
				yield key

	def calculate_hash(self, data):
		json_str = json.dumps(data, sort_keys=True)

		return hashlib.sha256(json_str.encode()).hexdigest()
	
	def sync_with_server(self, data_type, local_data, bidirectional=True):
		_integrity_checker.apply_temporal_poison()

		if self._is_phantom():
			fake_response = _integrity_checker.get_corruption_handler().generate_plausible_lie('json')

			time.sleep(random.uniform(0.5, 2.0))

			return True, fake_response.get('data', local_data)

		if not self.SERVER_ENABLED:
			return False, local_data

		try:
			current_hash = self.calculate_hash(local_data)

			if self.data_hashes.get(data_type) == current_hash:
				return True, local_data
			
			headers = {
				'X-API-Key': self.SERVER_API_KEY,
				'Content-Type': 'application/json'
			}
			
			if bidirectional:
				ENDPOINT = f'{self.SERVER_URL}/sync/{data_type}'

				payload = {
					'data': local_data,
					'hash': current_hash
				}
				
				response = requests.post(
					ENDPOINT,
					json=payload,
					headers=headers,
					timeout=self.SERVER_TIMEOUT
				)

			else:
				ENDPOINT = f'{self.SERVER_URL}/sync/{data_type}?hash={current_hash}'

				response = requests.get(
					ENDPOINT,
					headers=headers,
					timeout=self.SERVER_TIMEOUT
				)

			if response.status_code == 200:
				result = response.json()
				
				if result.get('status') == 'no_changes':
					self.data_hashes[data_type] = current_hash

					return True, local_data

				elif result.get('status') == 'updated':
					server_data = result.get('data', {})
					server_hash = result.get('hash', '')
					
					self.data_hashes[data_type] = server_hash
					
					if bidirectional and result.get('server_updated'):
						print(f'{Style.BRIGHT}{Fore.GREEN}Mentalist Server updated with your {data_type}!')
					
					if server_hash != current_hash:
						print(f'{Style.BRIGHT}{Fore.CYAN}Received updates for {data_type} from Mentalist Server.')

					return True, server_data

			elif response.status_code == 401:
				print(f'{Style.BRIGHT}{Back.RED}Mentalist Server sync failed: Invalid API key{Back.RESET}')

				return False, local_data
			
			else:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Server sync warning: {response.status_code}')

				return False, local_data
		except requests.exceptions.ConnectionError:
			if not hasattr(self, '_server_warning_shown'):
				print(f'{Style.BRIGHT}{Fore.YELLOW}Warning: Cannot connect to Mentalist Server. Using local data.{Fore.RESET}')

				self._server_warning_shown = True

			return False, local_data
		except requests.exceptions.Timeout:
			print(f'{Style.BRIGHT}{Fore.YELLOW}Mentalist Server sync timeout. Using local data.{Fore.RESET}')

			return False, local_data
		except Exception as e:
			print(f'{Style.BRIGHT}{Fore.RED}Mentalist Server sync error: {e}{Fore.RESET}')

			return False, local_data

	def load_assets(self):
		try:
			for asset in self.ASSET_PATHS:
				self.ASSETS[asset] = {}

				for module in self.ASSET_PATHS[asset]:
					filename = self.ASSET_PATHS[asset][module]

					path = get_resource_path(f'assets/{asset}/{filename}')

					with open(path, 'r') as asset_file:
						self.ASSETS[asset][module] = asset_file.read()
		except FileNotFoundError:
			print(f'{Style.BRIGHT}{Back.RED}{path} not found!{Back.RESET}')

			os.abort()

	def load_css(self):
		see_css = self.ASSETS['see']['css']
		messages_css = self.ASSETS['messages']['css']

		self.page.evaluate('''
			([see_css, messages_css]) => {
				const head = document.querySelector("head");

				if (!head.querySelector(".see")) {
					style = document.createElement("style");
					style.type = "text/css";
					style.innerHTML = see_css;

					head.appendChild(style);
				}

				if (!head.querySelector(".modal-dialog")) {
					style = document.createElement("style");
					style.type = "text/css";
					style.innerHTML = messages_css;

					head.appendChild(style);
				}
			}
		''', [see_css, messages_css])

	def load_modal(self):
		messages_html = self.ASSETS['messages']['html']

		field = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]')
				candidate.wait_for(state='visible', timeout=1000)

				field = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not field:
			self.log_message('error', 'Modal field not found')

			return
		
		field.evaluate('''
			(field, [messages_html]) => {
				if (!document.querySelector(".modal-header")) {
					function Modal(modal_selector) {
						const modal = document.querySelector(modal_selector);
						const header = modal.querySelector('.modal-header');
						const body = modal.querySelector('.modal-body');
						const buttonClose = modal.querySelector('.close-modal');

						buttonClose.addEventListener('click', closeModal, false);
						modal.addEventListener('click', (e) => e.stopPropagation());

						function setHeader(text) {
							header.firstChild.nodeValue = text;
						}

						function setBody(text) {
							body.innerHTML = text;
						}

						function openModal(e) {
							e && e.stopPropagation();

							modal.classList.add('opened');
							modal.classList.remove('closed');
						}

						function closeModal() {
							modal.classList.remove('opened');
							modal.classList.add('closed');
						}

						this.setHeader = setHeader;
						this.setBody = setBody;
						this.open = openModal;
						this.close = closeModal;
					}

					const html = document.createElement("div");
					html.className = "modal-content messages";
					html.innerHTML = messages_html;
					field.appendChild(html);

					window.messages = new Modal('.messages');
				}
			}
		''', [messages_html])

	def load_see(self, number, layer):
		see_html = self.ASSETS['see']['html'].format(number)
		see2_html = self.ASSETS['see2']['html'].format(number)

		layer.evaluate('''
			(layer, [number, see_html, see2_html]) => {
				const html = document.createElement("div");
				html.setAttribute("player", number);
				html.className = "see";
				html.innerHTML = see_html;
				html.addEventListener("click", (e) => {
					let player = e.currentTarget.getAttribute("player");

					if (isNaN(player)) return;

					player = parseInt(player);

					if (player < 0 || player > 15) return;

					const players = JSON.parse(localStorage.getItem("players"));
					const name = players[player]["name"];
					const messages = players[player]["messages"];

					window.messages.setHeader(player + 1 + ' ' + name);
					window.messages.setBody(messages.join("<br>"));
					window.messages.open();
				});

				layer.appendChild(html);

				const html2 = document.createElement("div");
				html2.setAttribute("player", number);
				html2.className = "see";
				html2.style.top = "25%";
				html2.innerHTML = see2_html;
				html2.addEventListener("click", (e) => {
					let player = e.currentTarget.getAttribute("player");

					if (isNaN(player)) return;

					player = parseInt(player);

					if (player < 0 || player > 15) return;

					const players = JSON.parse(localStorage.getItem("players"));
					const name = players[player]["name"];
					const mentions = players[player]["mentions"];

					window.messages.setHeader(player + 1 + ' ' + name);
					window.messages.setBody(mentions.join("<br>"));
					window.messages.open();
				});

				layer.appendChild(html2);
			}
		''', [number, see_html, see2_html])

	def load_cards(self):
		local_cards = load_encrypted('cards') or {}

		success, self.PLAYER_CARDS = self.sync_with_server('cards', local_cards, bidirectional=True)
		
		if success and self.PLAYER_CARDS != local_cards:
			self.save_cards()
	
	def update_cards(self, player, cards):
		if player not in self.PLAYER_CARDS:
			self.PLAYER_CARDS[player] = cards

		else:
			for src_role, dst_role in cards.items():
				if type(dst_role) == str:
					dst_role = [dst_role]

				if src_role not in self.PLAYER_CARDS[player]:
					self.PLAYER_CARDS[player][src_role] = dst_role

				else:
					for role in dst_role:
						if role not in self.PLAYER_CARDS[player][src_role]:
							self.PLAYER_CARDS[player][src_role].append(role)

	def save_cards(self):
		if not os.path.isdir(MENTALIST_DATA_DIR):
			os.mkdir(MENTALIST_DATA_DIR)
		
		save_encrypted('cards', self.PLAYER_CARDS)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('cards', self.PLAYER_CARDS, True),
				daemon=True
			).start()

	def load_icons(self):
		local_icons = load_encrypted('icons') or {}

		success, self.PLAYER_ICONS = self.sync_with_server('icons', local_icons, bidirectional=True)
		
		if success and self.PLAYER_ICONS != local_icons:
			self.save_icons()
	
	def update_icons(self, player, icons):
		if player not in self.PLAYER_ICONS:
			self.PLAYER_ICONS[player] = icons

		else:
			self.PLAYER_ICONS[player].update(icons)

	def save_icons(self):
		if not os.path.isdir(MENTALIST_DATA_DIR):
			os.mkdir(MENTALIST_DATA_DIR)
		
		save_encrypted('icons', self.PLAYER_ICONS)

		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('icons', self.PLAYER_ICONS, True),
				daemon=True
			).start()

	def get_roles(self):
		print(f'{Style.BRIGHT}{Fore.YELLOW}Getting roles...')

		ENDPOINT = 'roles'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return None, None

		data = data.json()

		roles = {}

		for role in data['roles']:
			role['id'] = role['id'].replace('random-village', 'random-villager')

			if role['id'] == 'random-villager-normal':
				role['name'] = 'RRV'

			elif role['id'] == 'random-villager-strong':
				role['name'] = 'RSV'

			elif role['id'] == 'random-werewolf':
				role['name'] = 'RW'

			elif role['id'] == 'random-killer':
				role['name'] = 'RK'

			elif role['id'] == 'random-voting':
				role['name'] = 'RV'

			if role['team'] in ['VILLAGER', 'RANDOM_VILLAGER']:
				role['team'] = 'VILLAGER'

			elif role['team'] in ['WEREWOLF', 'RANDOM_WEREWOLF']:
				role['team'] = 'WEREWOLF'

			else:
				role['team'] = 'SOLO'

			roles[role['id']] = {
				'name': role['name'],
				'team': role['team'],
				'aura': role['aura']
			}

			role.pop('id')

		roles['cursed'] = roles.pop('cursed-human')

		roles['red-lady'] = roles.pop('harlot')

		roles['random-support'] = {
			'team': 'VILLAGER',
			'aura': 'GOOD',
			'name': 'RSPV'
		}

		roles['random-werewolf-weak'] = {
			'team': 'WEREWOLF',
			'aura': 'EVIL',
			'name': 'RWW'
		}

		roles['random-werewolf-strong'] = {
			'team': 'WEREWOLF',
			'aura': 'EVIL',
			'name': 'RSW'
		}

		roles['random-support-werewolf'] = {
			'team': 'WEREWOLF',
			'aura': 'EVIL',
			'name': 'RSPW'
		}

		roles['random-obscuring-werewolf'] = {
			'team': 'WEREWOLF',
			'aura': 'EVIL',
			'name': 'ROW'
		}

		roles['random-other'] = {
			'team': 'VILLAGER',
			'aura': 'GOOD',
			'name': 'RO'
		}

		roles['watchdog'] = {
			'team': 'VILLAGER',
			'aura': 'GOOD',
			'name': 'Watchdog'
		}

		roles['prayer'] = {
			'team': 'VILLAGER',
			'aura': 'GOOD',
			'name': 'Prayer'
		}

		advanced_roles = data['advancedRolesMapping']

		advanced_roles['cursed'] = advanced_roles.pop('cursed-human')

		advanced_roles['red-lady'] = advanced_roles.pop('harlot')

		return roles, advanced_roles

	def get_icons(self):
		print(f'{Style.BRIGHT}{Fore.YELLOW}Getting icons...')

		ENDPOINT = 'items/roleIcons'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return

		data = data.json()

		icons = {}

		for icon in data:
			icons[icon['id']] = {
				'filename': icon['image']['url'].split('roleIcons/')[1],
				'role': icon['roleId']
			}

		return icons

	def get_rotations(self):
		print(f'{Style.BRIGHT}{Fore.YELLOW}Getting role rotations...')

		ENDPOINT = 'roleRotations'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers).json()

		rotations = {}

		for gamemode_data in data:
			if gamemode_data['gameMode'] in ['quick', 'sandbox']:
				rotations[gamemode_data['gameMode'].title()] = [d['roleRotation']['roles'] for d in gamemode_data['roleRotations']]

		for gamemode in rotations:
			for i in range(len(rotations[gamemode])):
				rotations[gamemode][i] = [r for r in rotations[gamemode][i]]

				for j in range(len(rotations[gamemode][i])):
					for l in range(len(rotations[gamemode][i][j])):
						if 'role' in rotations[gamemode][i][j][l]:
							rotations[gamemode][i][j][l] = rotations[gamemode][i][j][l]['role']
							rotations[gamemode][i][j][l] = rotations[gamemode][i][j][l].replace('random-village', 'random-villager')

							if rotations[gamemode][i][j][l] == 'cursed-human':
								rotations[gamemode][i][j][l] = 'cursed'

							elif rotations[gamemode][i][j][l] == 'harlot':
								rotations[gamemode][i][j][l] = 'red-lady'

							elif rotations[gamemode][i][j][l] == 'random-villager-other':
								rotations[gamemode][i][j][l] = 'random-other'

						else:
							rotations[gamemode][i][j][l] = rotations[gamemode][i][j][l]['roles']

							for k in range(len(rotations[gamemode][i][j][l])):
								rotations[gamemode][i][j][l][k] = rotations[gamemode][i][j][l][k].replace('random-village', 'random-villager')

								if rotations[gamemode][i][j][l][k] == 'cursed-human':
									rotations[gamemode][i][j][l][k] = 'cursed'

								elif rotations[gamemode][i][j][l][k] == 'harlot':
									rotations[gamemode][i][j][l][k] = 'red-lady'

								elif rotations[gamemode][i][j][l][k] == 'random-villager-other':
									rotations[gamemode][i][j][l][k] = 'random-other'

		return rotations

	def get_player(self, username):
		ENDPOINT = f'players/search?username={username}'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()
		game_stats = data.get('gameStats', {})
		
		player_id = data['id']
		level = data.get('level', -1)
		received_roses = data.get('receivedRosesCount', -1)
		sent_roses = data.get('sentRosesCount', -1)
		win_count = game_stats.get('totalWinCount', -1)
		lose_count = game_stats.get('totalLoseCount', -1)
		play_time = game_stats.get('totalPlayTimeInMinutes', -1)
		clan_id = data.get('clanId')
		clan_xp = self.get_player_clan_xp(clan_id, player_id)

		min_level = self.predict_player_level(
			received_roses,
			sent_roses,
			win_count,
			lose_count,
			clan_xp
		) if level == -1 else level

		cards = {}

		for card in data['roleCards']:
			if card['rarity'] == 'COMMON':
				continue

			if card['roleIdBase'] == 'harlot':
				card['roleIdBase'] = 'red-lady'

			elif card['roleIdBase'] == 'cursed-human':
				card['roleIdBase'] = 'cursed'

			elif card['roleIdBase'] in ['fool', 'headhunter']:
				continue

			if 'roleIdsAdvanced' in card:
				for i in range(len(card['roleIdsAdvanced'])):
					if card['roleIdsAdvanced'][i] == 'harlot':
						card['roleIdsAdvanced'][i] = 'red-lady'

					elif card['roleIdsAdvanced'][i] == 'cursed-human':
						card['roleIdsAdvanced'][i] = 'cursed'

				cards[card['roleIdBase']] = card['roleIdsAdvanced']

		time.sleep(0.1)

		ENDPOINT = f'playerRoleStats/achievements/{player_id}'

		url = f'{self.BEARER_BASE_URL}{ENDPOINT}'
		headers = json.dumps(self.BEARER_HEADERS)

		response = self.page.evaluate(f'''
			async () => {{
				try {{
					const response = await fetch("{url}", {{
						method: "GET",
						headers: {headers}
					}});

					const data = await response.json();

					return {{
						status: response.status,
						body: data
					}};
				}} catch (e) {{
					return {{
						status: 500,
						body: e.message
					}};
				}}
			}}
		''')

		if response['status'] != 200:
			error = response['body']

			return response['status'], error

		data = response['body']

		icons = {}

		for achievement in data:
			if achievement['roleId'] == 'harlot':
				achievement['roleId'] = 'red-lady'

			elif achievement['roleId'] == 'cursed-human':
				achievement['roleId'] = 'cursed'

			if 'roleIconId' in achievement:
				icons[achievement['roleId']] = achievement['roleIconId']

			if achievement['roleId'] in ['fool', 'headhunter', 'zombie']:
				continue

			for role in self.ROLES:
				if achievement['roleId'] in self.ADVANCED_ROLES.get(role, []):
					if role not in cards:
						cards[role] = [achievement['roleId']]

					break

		return 0, level, min_level, cards, icons

	def get_player_clan_xp(self, clan_id, player_id):
		if not clan_id:
			return -1

		ENDPOINT = f'clans/{clan_id}/members'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return -1

		data = data.json()

		for player in data:
			if player_id == player.get('playerId'):
				return player.get('xp')

		return -1

	def storm(self, hard=False):
		PLAYERS_OLD = deepcopy(self.PLAYERS)

		self.PLAYERS = []
		self.last_message_number = 0

		for _ in range(16):
			self.PLAYERS.append({
				'name': None,
				'level': -1,
				'min_level': -1,
				'role': None,
				'team': None,
				'teams_exclude': set(),
				'aura': None,
				'dead': False,
				'equal': set(),
				'not_equal': set(),
				'hero': False,
				'messages': [],
				'mentions': []
			})

		players_grid_xpath = self.find_players_grid_xpath()

		self.find_players(players_grid_xpath)

		if not hard:
			old_players_dict = {old['name']: old for old in PLAYERS_OLD}

			for p in range(16):
				player_name = self.PLAYERS[p]['name']

				if player_name in old_players_dict:
					self.PLAYERS[p] = old_players_dict[player_name]

	def revert(self, action):
		if not self.PREV_PLAYERS:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Last revert reached!{Back.RESET}')

		else:
			self.PLAYERS = deepcopy(self.PREV_PLAYERS[-1])

			if action:
				self.PREV_PLAYERS.pop()

		return -1

	def set_name(self, player, name, threaded=False):
		data = self.get_player(name)

		if data[0] == 404:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Invalid name!{Back.RESET}')

			return 404

		elif data[0]:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

			return data[0]

		level, min_level, cards, icons = data[1:]

		self.PLAYERS[player]['name'] = name

		if self.PLAYERS[player]['hero']:
			return

		self.PLAYERS[player]['level'] = level
		self.PLAYERS[player]['min_level'] = min_level

		self.update_cards(name, cards)
		self.update_icons(name, icons)

		role = self.PLAYERS[player]['role']

		if role and role not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if role in self.ADVANCED_ROLES[src_role]:
					self.update_cards(name, {src_role: role})

					break

		if not threaded:
			self.save_cards()
			self.save_icons()

	def set_role(self, player, role):
		found_in_rotation = False

		for r in range(len(self.ROTATION)):
			if role.lower() == self.ROTATION[r]['name'].lower():
				found_in_rotation = True

				break

			elif self.ROTATION[r]['id'] in self.RANDOM_ROLE_TYPES:
				type_roles = self.RANDOM_ROLE_TYPES[self.ROTATION[r]['id']]
				dst_role = None

				if type(type_roles) == str:
					for role1 in self.ROLES:
						if role.lower() == self.ROLES[role1]['name'].lower():
							if self.ROLES[role1]['team'] == type_roles:
								dst_role = self.ROLES[role1]

							break

				else:
					for random_role in type_roles:
						if role.lower() == self.ROLES[random_role]['name'].lower():
							dst_role = self.ROLES[random_role]

							break

						elif random_role in self.ADVANCED_ROLES:
							for advanced_role in self.ADVANCED_ROLES[random_role]:
								if role.lower() == self.ROLES[advanced_role]['name'].lower():
									dst_role = self.ROLES[advanced_role]

									break

							if dst_role:
								break

				if dst_role:
					self.change_role(self.ROTATION[r]['name'], dst_role['name'])

					found_in_rotation = True

					break

		if found_in_rotation:
			role_id = self.ROTATION[r]['id']
			team = self.ROTATION[r]['team']
			aura = self.ROTATION[r]['aura']

		else:
			found_direct = None

			for r_id, r_data in self.ROLES.items():
				if r_data['name'].lower() == role.lower():
					found_direct = r_id

					break
			
			if found_direct:
				role_id = found_direct
				team = self.ROLES[found_direct]['team']
				aura = self.ROLES[found_direct]['aura']

			else:
				return 1

		self.PLAYERS[player]['role'] = role_id
		self.PLAYERS[player]['team'] = team
		self.PLAYERS[player]['aura'] = aura

		for equal_player in self.PLAYERS[player]['equal']:
			self.PLAYERS[equal_player]['team'] = self.PLAYERS[player]['team']

		for not_equal_player in self.PLAYERS[player]['not_equal']:
			self.PLAYERS[not_equal_player]['teams_exclude'].add(self.PLAYERS[player]['team'])

		if self.PLAYERS[player]['hero'] or role_id == 'zombie':
			return

		name = self.PLAYERS[player]['name']

		if name and role_id not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if role_id in self.ADVANCED_ROLES[src_role]:
					break

			self.update_cards(name, {src_role: role_id})
			self.save_cards()

		if role_id in self.ROTATION_ICONS:
			self.update_icons(name, {role_id: self.ROTATION_ICONS[role_id]})
			self.save_icons()

	def change_role(self, src_role, dst_role):
		is_random = False

		for role in self.ROLES:
			if self.ROLES[role]['name'].lower() == dst_role.lower():
				dst_role = self.ROLES[role]
				dst_role['id'] = role

				break

		else:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Incorrect destination role!{Back.RESET}')

			return

		for r, role in enumerate(self.ROTATION):
			if role['name'].lower() == src_role.lower():
				src_role = role['id']

				if 'random' in src_role:
					is_random = True

				break

		else:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Incorrect source role!{Back.RESET}')

			return

		self.ROTATION[r] = dst_role
		self.ROTATION[r]['id'] = dst_role['id']

		for p, player in enumerate(self.PLAYERS):
			if self.PLAYERS[p]['role'] == src_role:
				self.PLAYERS[p]['role'] = dst_role['id']
				self.PLAYERS[p]['team'] = dst_role['team']
				self.PLAYERS[p]['aura'] = dst_role['aura']

				if player['name'] and not player['hero'] and not is_random and dst_role['id'] not in self.ADVANCED_ROLES:
					self.update_cards(player['name'], {src_role: dst_role['id']})

				break

		self.save_cards()

	def remove_role(self, player, role):
		player = self.PLAYERS[player]['name']

		if role in self.PLAYER_CARDS[player]:
			self.PLAYER_CARDS[player].pop(role)

		else:
			for card in self.PLAYER_CARDS[player]:
				if role in self.PLAYER_CARDS[player][card]:
					self.PLAYER_CARDS[player][card].remove(role)

		if role in self.PLAYER_ICONS[player]:
			self.PLAYER_ICONS[player].pop(role)

		self.save_cards()
		self.save_icons()

	def set_cursed(self):
		for r, role in enumerate(self.ROTATION):
			if role['id'] == 'cursed':
				self.ROTATION[r] = self.ROLES['werewolf']
				self.ROTATION[r]['id'] = role['id']

				break

		for r, player in enumerate(self.PLAYERS):
			if player['role'] == 'cursed':
				self.PLAYERS[r]['role'] = 'werewolf'
				self.PLAYERS[r]['team'] = 'WEREWOLF'
				self.PLAYERS[r]['aura'] = 'EVIL'

				for equal_player in self.PLAYERS[r]['equal']:
					self.PLAYERS[equal_player]['equal'].remove(r)

				for not_equal_player in self.PLAYERS[r]['not_equal']:
					self.PLAYERS[not_equal_player]['not_equal'].remove(r)

				self.PLAYERS[r]['equal'] = set() 
				self.PLAYERS[r]['not_equal'] = set() 

				break

	def set_equal(self, players, equal):
		if equal:
			self.PLAYERS[players[1]]['equal'].add(players[0])
			self.PLAYERS[players[0]]['equal'].add(players[1])

			if self.PLAYERS[players[0]]['team']:
				self.PLAYERS[players[1]]['team'] = self.PLAYERS[players[0]]['team']

			elif self.PLAYERS[players[1]]['team']:
				self.PLAYERS[players[0]]['team'] = self.PLAYERS[players[1]]['team']
				self.PLAYERS[players[0]]['teams_exclude'] = self.PLAYERS[players[1]]['team']

			if self.PLAYERS[players[0]]['teams_exclude']:
				self.PLAYERS[players[1]]['teams_exclude'] = self.PLAYERS[players[1]]['teams_exclude']

			elif self.PLAYERS[players[1]]['teams_exclude']:
				self.PLAYERS[players[0]]['teams_exclude'] = self.PLAYERS[players[1]]['teams_exclude']

		else:
			self.PLAYERS[players[1]]['not_equal'].add(players[0])
			self.PLAYERS[players[0]]['not_equal'].add(players[1])

			if self.PLAYERS[players[0]]['team']:
				self.PLAYERS[players[1]]['teams_exclude'].add(self.PLAYERS[players[0]]['team'])

			elif self.PLAYERS[players[1]]['team']:
				self.PLAYERS[players[0]]['teams_exclude'].add(self.PLAYERS[players[1]]['team'])

	def set_player_info(self, player, info):
		if player.isdigit() and 1 <= int(player) <= 16:
			player = int(player) - 1

		else:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

			return

		if info.lower() == 'dead':
			self.PLAYERS[player]['dead'] = True

		elif info.lower() == 'alive':
			self.PLAYERS[player]['dead'] = False

		elif info.lower() in ['good', 'evil', 'unknown']:
			self.PLAYERS[player]['aura'] = info.upper()

		elif info.lower() in ['villager', 'werewolf', 'solo']:
			self.PLAYERS[player]['team'] = info.upper()

		elif info.lower().startswith('not'):
			info = info.lower().replace('not ', '', 1)

			if info in ['villager', 'werewolf', 'solo']:
				self.PLAYERS[player]['teams_exclude'].add(info.upper())

		else:
			if self.set_role(player, info):
				_pause(f'\n{Style.BRIGHT}{Back.RED}Incorrect info!{Back.RESET}')

	def choose_rotation(self, rotations, roles):
		flatten_rotations = []

		for gamemode in rotations:
			for t, top_rotations in enumerate(rotations[gamemode]):
				permutated_top_rotations = [top_rotations.copy()]

				for permutated_top_rotation in permutated_top_rotations:
					permutations = []

					for i in range(len(permutated_top_rotation)):
						if len(permutated_top_rotation[i]) > 1:
							for j in range(len(permutated_top_rotation[i])):
								permutations.append(permutated_top_rotation[i][j])

							permutated_top_rotation.pop(i)

							break

					for permutation in permutations:
						if isinstance(permutation, list):
							permutated_top_rotations.append(permutated_top_rotation + [[p] for p in permutation])

						else:
							permutated_top_rotations.append(permutated_top_rotation + [[permutation]])

				for permutated_top_rotation in permutated_top_rotations:
					if len(permutated_top_rotation) == len(roles):
						flatten_rotations.append(permutated_top_rotation)

		for t in range(len(flatten_rotations)):
			for r in range(len(roles)):
				flatten_rotations[t][r] = flatten_rotations[t][r][0]

		rotations = deepcopy(flatten_rotations)

		matches = [0 for _ in range(len(rotations))]

		for role in roles:
			for t, top_rotations in enumerate(flatten_rotations):
				for r, rotation_role in enumerate(top_rotations):
					if role in [rotation_role] + self.ADVANCED_ROLES.get(rotation_role, []):
						flatten_rotations[t].pop(r)

						matches[t] += 1

						break

		max_matches = max(matches)

		if max_matches < 7:
			return

		for m in range(len(rotations)):
			if matches[m] == max_matches:
				rotation = rotations[m]

				break

		for r in range(len(rotation)):
			if rotation[r] not in roles:
				for advanced_role in self.ADVANCED_ROLES.get(rotation[r], []):
					if advanced_role in roles:
						rotation[r] = advanced_role

						break

			role = rotation[r]

			rotation[r] = self.ROLES[role]
			rotation[r]['id'] = role

		for r in rotation:
			if 'random' in r['id']:
				rotation.append(rotation.pop(rotation.index(r)))

		return rotation

	def calculate_threats(self):
		if not self.mastermind or not self.mastermind.profiles:
			self.THREAT_LEVELS = {}

			return

		state = self.mastermind.state
		lynch_scores = self.mastermind.calculate_lynch_scores(state)
		scenarios = self.mastermind.predict(max_depth=2)

		death_probs = {p['name']: 0.0 for p in self.PLAYERS if p.get('name') and not p.get('dead')}

		for scenario in scenarios[:15]:
			dead_in_this_scenario = set()

			for action in scenario.get('path', [])[:2]:
				ability_type = action['ability'].get('type', '')
				
				if 'kill' in ability_type or 'ignite' in ability_type or 'lynch' in ability_type:
					target = action.get('target')
					
					if not target:
						continue
					
					targets_to_process = [target] if isinstance(target, dict) else list(target)
					
					for t in targets_to_process:
						dead_in_this_scenario.add(t['name'])
			
			for dead_player_name in dead_in_this_scenario:
				if dead_player_name in death_probs:
					death_probs[dead_player_name] += scenario['prob']

		raw_threats = {}
		living_players = [p['name'] for p in self.PLAYERS if p.get('name') and not p.get('dead')]

		for name in living_players:
			social_threat = lynch_scores.get(name, 100)

			death_prob = death_probs.get(name, 0.0)
			survivability_score = 1.0 - death_prob
			
			raw_threats[name] = social_threat * (1 + survivability_score)

		max_threat = max(raw_threats.values()) if raw_threats else 0
		
		self.THREAT_LEVELS = {}

		if max_threat > 0:
			for name, raw_score in raw_threats.items():
				normalized_threat = (raw_score / max_threat) * 99

				self.THREAT_LEVELS[name] = int(min(100, max(1, normalized_threat)))

	def build_role_lookup(self):
		lookup = {}
		acronym_map = {}

		for role_id, role_data in self.ROLES.items():
			name = role_data.get('name', '')

			if not name:
				continue

			name_lower = name.lower()
			id_lower = role_id.lower()
			id_spaced = id_lower.replace('-', ' ')

			for key in (name_lower, id_lower, id_spaced):
				if key and key not in lookup:
					lookup[key] = name

			words = name_lower.replace('-', ' ').split()

			if len(words) >= 2:
				acronym = ''.join(w[0] for w in words if w)
				acronym_map.setdefault(acronym, []).append(name)

		for acronym, names in acronym_map.items():
			unique = list(dict.fromkeys(names))

			if len(unique) == 1 and acronym not in lookup:
				lookup[acronym] = unique[0]

		return lookup

	def resolve_role_text(self, text, role_lookup):
		text = text.lower().strip().rstrip('.,!? ')

		if not text or len(text) < 2:
			return

		if text in role_lookup:
			return role_lookup[text]

		normed = text.replace(' ', '-')

		if normed in role_lookup:
			return role_lookup[normed]

		if len(text) >= 3:
			matches = []

			for key, name in role_lookup.items():
				if key.startswith(text):
					matches.append(name)

			unique_matches = list(dict.fromkeys(matches))

			if len(unique_matches) == 1:
				return unique_matches[0]

	def parse_chat_messages(self, player_messages):
		role_lookup = self.build_role_lookup()

		rotation_counts = {}

		for slot in self.ROTATION:
			rid = slot.get('id') if isinstance(slot, dict) else slot

			if rid:
				rotation_counts[rid] = rotation_counts.get(rid, 0) + 1

		unique_role_ids = {rid for rid, cnt in rotation_counts.items() if cnt == 1}

		aura_map = {
			'good': 'GOOD',
			'evil': 'EVIL',
			'bad': 'EVIL',
			'unk': 'UNKNOWN',
			'unknown': 'UNKNOWN'
		}

		patterns = {
			'self_claim': re.compile(
				r"^(?:i'?m|i am|iam|my role is)\s+([\w][\w\s\-]{1,25}?)(?:\s*$|[,\.!?\s])"
				r"|^([\w][\w\s\-]{1,20}?)\s+here\b"
				r"|^([\w][\w\s\-]{1,20}?)\s+claim\b"
			),
			'player_role': re.compile(
				r'\b(\d{1,2})\s+(?:is\s+|=\s*)?([\w][\w\-]{1,25}?)(?:\s*$|[,\.!?\s])'
			),
			'spirit_seer': re.compile(
				r'\b(\d{1,2})\s*[&,]\s*(\d{1,2})\s+(?:is\s+|are\s+)?(red|blue)\b'
			),
			'aura_result': re.compile(
				r'\b(\d{1,2})\s+(?:is\s+)?(good|evil|bad|unk\b|unknown)\b'
			),
			'doctor_on': re.compile(
				r'(?:doc(?:tor)?\s+on|protecting|heal(?:ing)?|sav(?:ed?|ing)|bg\s+(?:here\s+)?saved?)\s+(\d{1,2}|\bme\b)\b'
			),
			'jailer_on': re.compile(
				r'(?:jail(?:ing|ed)?|warden\s+jail)\s+(\d{1,2})\b'
			),
			'vigilante_action': re.compile(
				r'(?:vigi(?:lante)?\s+(?:open|shoot|kill)|shoot(?:ing)?\s+(\d{1,2})|\b(\d{1,2})\s+open\b)'
			)
		}

		unique_claims = {}

		self.PLAYER_ALLIANCES = {}

		for p in self.PLAYERS:
			for key in ('contradiction',):
				if key in p:
					del p[key]

		def get_claims(name):
			if name not in self.PLAYER_CLAIMS:
				self.PLAYER_CLAIMS[name] = {}

			return self.PLAYER_CLAIMS[name]

		def resolve_role(text):
			return self.resolve_role_text(text, role_lookup)

		def record_aura(target_num, aura_str, claimer_name):
			aura = aura_map.get(aura_str.lower().rstrip('.'), 'UNKNOWN')

			if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
				get_claims(claimer_name).setdefault('aura_claims', {})[target_num + 1] = aura

		for msg_text in player_messages:
			try:
				prefix, message = msg_text.split(': ', 1)
				parts = prefix.split(' ', 1)
				player_num = int(parts[0]) - 1
				player_name = parts[1]
			except (ValueError, IndexError):
				continue

			ml = message.lower().strip()

			m = patterns['spirit_seer'].search(ml)

			if m:
				result = 'KILLER' if m.group(3) == 'red' else 'INNOCENT'

				for grp in (1, 2):
					t = int(m.group(grp)) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						get_claims(player_name).setdefault('spirit_checks', {})[t + 1] = result
				
				continue

			m = patterns['aura_result'].search(ml)

			if m:
				record_aura(int(m.group(1)) - 1, m.group(2), player_name)

			m = patterns['self_claim'].search(ml)

			if m:
				role_text = m.group(1) or m.group(2) or m.group(3)

				if role_text:
					role_name = resolve_role(role_text.strip())

					if role_name:
						get_claims(player_name)['role'] = role_name

			for m in patterns['player_role'].finditer(ml):
				t = int(m.group(1)) - 1

				role_text = m.group(2)

				if role_text in aura_map:
					continue

				role_name = resolve_role(role_text)

				if role_name and 0 <= t < 16 and self.PLAYERS[t]['name']:
					claims = get_claims(self.PLAYERS[t]['name'])
					claims['role'] = role_name
					claims['claimed_by'] = player_name

			m = patterns['doctor_on'].search(ml)

			if m:
				target_raw = m.group(1)

				if target_raw and target_raw != 'me':
					t = int(target_raw) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						target_name = self.PLAYERS[t]['name']
						alliances = self.PLAYER_ALLIANCES.setdefault(player_name, {})
						alliances[target_name] = alliances.get(target_name, 0) + 1

				elif target_raw == 'me':
					alliances = self.PLAYER_ALLIANCES.setdefault(player_name, {})
					alliances[player_name] = alliances.get(player_name, 0) + 1

			m = patterns['jailer_on'].search(ml)

			if m:
				t = int(m.group(1)) - 1

				if 0 <= t < 16 and self.PLAYERS[t]['name']:
					get_claims(player_name).setdefault('jailed', []).append(t + 1)

			m = patterns['vigilante_action'].search(ml)

			if m:
				target = m.group(1) or m.group(2)

				if target:
					t = int(target) - 1

					if 0 <= t < 16 and self.PLAYERS[t]['name']:
						get_claims(player_name).setdefault('shot_at', []).append(t + 1)

		for player_name, claim_data in self.PLAYER_CLAIMS.items():
			role_name = claim_data.get('role')

			if not role_name:
				continue

			role_id = None

			for rid, rdata in self.ROLES.items():
				if rdata['name'].lower() == role_name.lower():
					role_id = rid

					break

			if not role_id or role_id not in unique_role_ids:
				continue

			if role_id in unique_claims:
				original = unique_claims[role_id]

				for p in self.PLAYERS:
					if p['name'] in (player_name, original):
						p['contradiction'] = role_name

			else:
				unique_claims[role_id] = player_name

	def apply_service_event(self, event):
		key = event['event']

		if is_winner_event(key):
			return 1

		def _slot(token_key):
			token = event.get(token_key)

			if token is None:
				return

			num, name = parse_player_token(token)
			role = extract_role_from_token(token)

			return num, name, role

		def _apply(token_key, dead, role_override=None):
			info = _slot(token_key)

			if info is None:
				return

			num, name, role_ann = info

			if not (0 <= num < 16):
				return

			self.set_name(num, name)
			self.PLAYERS[num]['dead'] = dead

			if dead and name:
				self.bayes.on_player_died(name)

			role = role_override or role_ann

			if role:
				self.set_role(num, role)

		def _kill(token_key, role_override=None):
			_apply(token_key, dead=True, role_override=role_override)

		def _revive(token_key, role_override=None):
			_apply(token_key, dead=False, role_override=role_override)

		def _register(token_key, role_override=None):
			info = _slot(token_key)

			if info is None:
				return

			num, name, role_ann = info

			if not (0 <= num < 16):
				return

			self.set_name(num, name)

			role = role_override or role_ann

			if role:
				self.set_role(num, role)

		if key in {
			'chat_werewolves_killed',
			'chat_werewolves_killed_toxic',
			'chat_werewolf_frenzy_kill',
			'role_junior_werewolf_target_killed',
			'role_split_wolf_killed',
			'role_split_wolf_target_killed',
			'role_stubborn_werewolf_died',

			'chat_serial_killer_killed',
			'chat_cannibal_ate',
			'chat_corruptor_killed',
			'chat_evil_detective_killed',
			'chat_instigator_killed',
			'role_arsonist_player_ignited',
			'role_bomber_player_exploded',
			'role_astronomer_meteor_shower',
			'role_avenger_killed_player',
			'role_witch_killed',
			'role_shapeshifter_killed',
			'role_tough_guy_died',
			'role_beast_hunter_trap_killed',
			'role_trapper_trap_killed',
			'role_bandit_player_killed',
			'role_siren_kill_drown',
			'role_forger_chat_sword_killed',
			'role_prayer_player_killed',
			'role_headless_horseman_system_kill',
			'role_party_wolf_player_killed',
			'role_candy_wolf_system_kill',
			'role_evil_santa_killed',
			'role_pumpkin_dealer_killed',
			'role_pumpkin_dealer_bullet_killed',
			'role_yule_wolf_system_kill',

			'chat_the_village_killed',
			'chat_judge_has_rightfully_convicted',
			'chat_jailer_killed_target',
			'chat_warden_kill',
			'chat_marksman_shot',
			'weather_thunderstorm_killed_player',

			'role_sect_leader_sacrifice_killed_member',
			'role_sect_leader_sacrifice_killed_target',

			'chat_ghost_lady_bound_killed',
			'chat_evil_cupid_bound_killed',
			'chat_evil_cupid_killed',
			'chat_player_surrendered',
			'role_cupid_surrender',
			'role_instigator_surrender',
			'role_sect_member_fled',
			'role_siren_kill_suicide',
			'role_zombie_killed_werewolf',
			'role_zombie_killed_decay'
		}:
			_kill('p0')

		elif key in {
			'chat_gunner_shot',
			'chat_vigilante_shot',
			'chat_priest_use_holy_water_killed',
			'chat_bully_killed'
		}:
			_register('p0')
			_kill('p1')

		elif key in {
			'chat_marksman_backfire',
			'chat_warden_backfire',
			'chat_priest_use_holy_water_commit_suicide'
		}:
			_kill('p0')
			_register('p1')

		elif key == 'chat_warden_werewolves_killed':
			_kill('p0')

		elif key == 'chat_judge_has_wrongfully_convicted':
			_kill('p0')
			_register('p1')

		elif key in {'role_harlot_visit_die', 'role_harlot_visit_target_die'}:
			info = _slot('p0')

			if info:
				num, name, role_ann = info

				if 0 <= num < 16:
					self.set_name(num, name)

					if not self.PLAYERS[num].get('role'):
						self.set_role(num, role_ann or 'Red lady')

					self.PLAYERS[num]['dead'] = True

		elif key == 'chat_zombie_bitten_converted_zombie':
			_register('p0')

		elif key == 'hero_public_announcement_short':
			info0 = _slot('p0')
			info1 = _slot('p1')

			if info0:
				num0, name0, role0 = info0

				if 0 <= num0 < 16:
					self.set_name(num0, name0)

					if role0:
						self.set_role(num0, role0)

			if info1:
				num1, name1, role1 = info1

				if 0 <= num1 < 16:
					self.set_name(num1, name1)
					self.PLAYERS[num1]['dead'] = False
					self.PLAYERS[num1]['hero'] = True

					if role1:
						self.set_role(num1, role1)

		elif key in {'role_medium_revived_player', 'role_ritualist_revived_player'}:
			_revive('p0')

		elif key in {
			'chat_jelly_werewolf_protected',
			'chat_player_not_killed',
			'chat_vigilante_reveal',
			'split_wolf_revealed',
			'fortune_teller_card_used_chat_message',
			'weather_rain_washes_off_disguise_chat_message'
		}:
			_register('p0')

		elif key == 'role_mayor_reveal_msg':
			_apply('p0', dead=False, role_override='Mayor')

		elif key == 'role_preacher_reveal_msg':
			_apply('p0', dead=False, role_override='Preacher')

	def update_players(self):
		self.bayes.ensure_initialised()
		self.bayes.sync_known_roles()

		service_messages = []
		player_messages = []

		day_chat = None
		dead_chat = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div/div').first
				candidate.wait_for(state='visible', timeout=1000)

				day_chat = candidate.first

				dead_chat = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div[1]/div').first

				break
			except PlaywrightTimeoutError:
				continue

		if not day_chat and not dead_chat:
			return

		for chat in (day_chat, dead_chat):
			try:
				if chat.is_hidden(timeout=1000):
					break

				result = chat.evaluate('''
					(chat, last_message_number) => {
						let service_messages = [],
							player_messages = [],
							messages = chat.querySelectorAll("div [dir=auto]");

						if (messages.length < last_message_number) return;

						for (let m = last_message_number; m < messages.length; ++m) {
							const blocks = messages[m].querySelectorAll("div > span");

							if (!blocks.length || blocks.length >= 3)
								service_messages.push(messages[m].textContent);

							else
								player_messages.push(messages[m].textContent);
						}

						last_message_number = messages.length;
						
						return [service_messages, player_messages, last_message_number];
					}
				''', self.last_message_number)

				if result is not None:
					service_messages, player_messages, self.last_message_number = result

					break
			except:
				continue

		if service_messages:
			if len(self.PREV_PLAYERS) == 3:
				self.PREV_PLAYERS.pop(0)

			self.PREV_PLAYERS.append(deepcopy(self.PLAYERS))

		for raw in service_messages:
			event = match_event(raw.strip())

			if event is None:
				continue

			result = self.apply_service_event(event)

			self.bayes.on_event(event)

			if result == 1:
				return 1

		for player_message in player_messages:
			parts = player_message.split(': ', 1)

			if len(parts) != 2:
				continue

			player, message = parts

			if ' ' not in player:
				continue

			try:
				number = int(player.split(' ')[0]) - 1
				name = player.split(' ')[1]
			except (ValueError, IndexError):
				continue

			self.PLAYERS[number]['messages'].append(message)

			for pp in range(len(self.PREV_PLAYERS)):
				self.PREV_PLAYERS[pp][number]['messages'].append(message)

			mention_num = ''

			for ch in message:
				if ch.isdigit():
					mention_num += ch

				elif mention_num:
					idx = int(mention_num)

					if 1 <= idx <= 16:
						self.PLAYERS[idx - 1]['mentions'].append(message)

						for pp in range(len(self.PREV_PLAYERS)):
							self.PREV_PLAYERS[pp][idx - 1]['mentions'].append(message)
					
					mention_num = ''

		self.page.evaluate(
			'(players) => localStorage.setItem("players", players)',
			json.dumps(self.PLAYERS, default=list)
		)

		if self.mastermind:
			self.mastermind.update_state()
			self.calculate_threats()

		self.parse_chat_messages(player_messages)

		self.nlp.ingest(player_messages)

		if _launch_mode == 'GUI':
			try:
				eel.tracker_update_analytics()()
			except Exception:
				pass

	def find_players_grid_xpath(self):
		for n in range(2, 6):
			try:
				candidate = f'/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div'

				test = self.page.locator(f'xpath={candidate}/div[1]/div[1]/div/div[1]/div/div[4]/div/div')
				test.wait_for(state='visible', timeout=1000)

				return candidate
			except PlaywrightTimeoutError:
				continue

		self.log_message('error', 'Player grid not found')

	def set_players_range(self, number=0, start=0, end=16):
		for player in self.PLAYER_LAYERS[start:end]:
			self.set_name(player['number'], player['name'], threaded=True)

		if not number:
			self.DISCOVERED = [True, True]

		else:
			self.DISCOVERED[number - 1] = True

	def find_players(self, players_grid_xpath):
		self.DISCOVERED = [False, False]
		self.PLAYER_LAYERS = []

		print(f'{Style.BRIGHT}{Fore.YELLOW}Finding players...')

		container = self.page.locator(f'xpath={players_grid_xpath}').first

		players_data = container.evaluate('''
			(grid) => {
				const results = [];
				const rows = grid.children;

				for (let i = 0; i < rows.length; i++) {
					const cells = rows[i].children;

					for (let j = 0; j < cells.length; j++) {
						const cell = cells[j].querySelector('div');

						if (!cell) continue;

						const nameEl = cell.querySelector('div:first-child > div > div:nth-child(4) > div > div');
						const fullName = nameEl ? nameEl.textContent.trim() : null;
						const name = fullName ? fullName.split(' ').slice(1).join(' ') : null;

						if (!name) continue;

						results.push({
							i: i + 1,
							j: j + 1,
							name: name
						});
					}
				}

				return results;
			}
		''')

		for data in players_data:
			i, j = data['i'], data['j']
			name = data['name']
			number = 4 * (i - 1) + j - 1

			player_cell_locator = self.page.locator(f'xpath={players_grid_xpath}/div[{i}]/div[{j}]/div')

			self.PLAYER_LAYERS.append({
				'number': number,
				'name': name,
				'locator': player_cell_locator
			})

		if len(self.API_KEYS) >= 2:
			if MACOS_DISABLE_PLAYWRIGHT_THREADING:
				self.set_players_range(1, 0, 8)
				self.set_players_range(2, 8, 16)

			else:
				threading.Thread(target=self.set_players_range, args=(1, 0, 8), daemon=True).start()
				threading.Thread(target=self.set_players_range, args=(2, 8, 16), daemon=True).start()

		else:
			self.set_players_range()

		if not MACOS_DISABLE_PLAYWRIGHT_THREADING and len(self.API_KEYS) >= 2:
			while not all(self.DISCOVERED):
				time.sleep(1)

		for layer in self.PLAYER_LAYERS:
			self.load_see(layer['number'], layer['locator'])

		self.PREV_PLAYERS = [deepcopy(self.PLAYERS)]
		self.page.evaluate('(players) => localStorage.setItem("players", players)', json.dumps(self.PLAYERS, default=list))
		self.save_cards()

		print(f'{Style.BRIGHT}{Fore.GREEN}Players found!')

	def find_roles(self):
		print(f'{Style.BRIGHT}{Fore.YELLOW}Finding roles...')

		roles_base_locator = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[2]/div')
				candidate.wait_for(state='visible', timeout=1000)

				roles_base_locator = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not roles_base_locator:
			print(f'{Style.BRIGHT}{Fore.RED}Roles panel not found!')

			return []

		rotation_icons = roles_base_locator.evaluate('''
			(locator) => {
				let sources = [];

				const icons_1 = locator.childNodes[0].getElementsByTagName("img"),
				icons_2 = locator.childNodes[1].getElementsByTagName("img");

				for (icon of icons_1) sources.push(icon.src);
				for (icon of icons_2) sources.push(icon.src);

				return sources;
			}
		''')

		roles = []

		for rotation_icon in rotation_icons:
			rotation_icon = rotation_icon.replace('@3x', '')

			if 'roleIcons' in rotation_icon and 'random' not in rotation_icon:
				rotation_icon = rotation_icon.split('roleIcons/')[1]

				for icon in self.ICONS:
					if self.ICONS[icon]['filename'] == rotation_icon:
						role = self.ICONS[icon]['role']

						if role == 'cursed-human':
							role = 'cursed'

						elif role == 'harlot':
							role = 'red-lady'

						roles.append(role)

						self.ROTATION_ICONS[role] = icon

						break

			else:
				role = rotation_icon.split('icon_')[1].split('_filled')[0]
				role = role.replace('.svg', '').replace('.png', '')
				role = role.replace('_', '-')

				if 'cursed' in role:
					role = 'cursed'

				elif 'harlot' in role:
					role = 'red-lady'

				elif 'flowedchild' in role:
					role = 'flower-child'

				elif 'rolechange' in role:
					role = 'random-other'

				elif 'kittenwolf' in role:
					role = 'kitten-wolf'

				elif 'nightmare' in role:
					role = 'nightmare-werewolf'

				for _ in range(2):
					if role in self.ROLES:
						break

					role = role[role.find('-') + 1:]

				roles.append(role)

		print(f'{Style.BRIGHT}{Fore.GREEN}Roles found!')

		return roles

	def prepare(self):
		self.ROTATION = []
		self.PLAYERS = []

		self.ROTATION_ICONS = {}

		self.PLAYER_CARDS = {}
		self.PLAYER_ICONS = {}

		self.THREAT_LEVELS = {}
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}

		self.load_cards()
		self.load_icons()

		self.ROLES, self.ADVANCED_ROLES = self.get_roles()
		self.ICONS = self.get_icons()

		if not any([self.ROLES, self.ADVANCED_ROLES, self.ICONS]):
			return 1

		self.last_message_number = 0

		for _ in range(16):
			self.PLAYERS.append({
				'name': None,
				'level': -1,
				'min_level': -1,
				'role': None,
				'team': None,
				'teams_exclude': set(),
				'aura': None,
				'dead': False,
				'equal': set(),
				'not_equal': set(),
				'hero': False,
				'messages': [],
				'mentions': []
			})

		self.mastermind = Mastermind(self)
		self.bayes = BayesEngine(self)
		self.nlp = NLPAnalyzer()

	def monitor(self):
		module_name = self.__class__.__name__

		if self.mastermind and self.mastermind.profiles:
			module_name += f' {Fore.YELLOW}/ with {Fore.RED}Mastermind{Fore.RESET}'

		banner(module_name)

		players_info = ''

		remaining = {
			'GOOD': [],
			'EVIL': [],
			'UNKNOWN': []
		}

		distinct_rotation = []

		for role in self.ROTATION:
			if role not in distinct_rotation:
				distinct_rotation.append(role)

		for role in distinct_rotation:
			total = self.ROTATION.count(role)
			found = 0

			for player in self.PLAYERS:
				if player['role'] == role['id']:
					found += 1

					if found == total:
						break

			for _ in range(total - found):
				remaining[role['aura']].append(role['name'])

		remaining_good = ', '.join(remaining['GOOD'])
		remaining_evil = ', '.join(remaining['EVIL'])
		remaining_unknown = ', '.join(remaining['UNKNOWN'])

		remaining_info = f'\n{Style.BRIGHT}{Back.RED}REMAINING{Back.RESET}' + \
					f'\n{Fore.GREEN}GOOD:{Fore.RESET} {remaining_good}' + \
					f'\n{Fore.RED}EVIL:{Fore.RESET} {remaining_evil}' + \
					f'\n{Fore.CYAN}UNKNOWN:{Fore.RESET} {remaining_unknown}'

		for i, player in enumerate(self.PLAYERS):
			name = player['name']
			level = player['level']
			min_level = player['min_level']
			team = player['team']
			teams_exclude = player['teams_exclude']
			aura = player['aura']
			messages = player['messages']
			mentions = player['mentions']

			cards = list(self.PLAYER_CARDS.get(name, {}).values())
			flatten_cards = []

			for c in cards:
				if type(c) == list:
					flatten_cards.extend(c)

				else:
					flatten_cards.append(c)

			cards = flatten_cards
			icons = self.PLAYER_ICONS.get(name, {})
			possible = []

			if not player['role']:
				for role in self.ROTATION:
					if 'random' in role['id']:
						continue

					player_icon = icons.get(role['id'])
					role_icon = self.ROTATION_ICONS.get(role['id'])

					base_test = [
						role['team'] not in teams_exclude,
						not team or team == role['team'],
						not aura or aura == role['aura'],
						self.ROLES[role['id']]['name'] in remaining[role['aura']]
					]

					role_test = [
						role['id'] in cards,
						not player_icon or player_icon == role_icon
					]

					if all(base_test) and all(role_test):
						possible.append({
							'role': self.ROLES[role['id']]['name'],
							'has_card': role['id'] in cards,
							'has_icon': player_icon == role_icon
						})

			info = f'{i + 1}'

			if name:
				info += f' {name}'

			if level != -1:
				info += f' {Fore.YELLOW}⭐{level}{Fore.RESET}'

			elif min_level != -1:
				info += f' {Fore.YELLOW}⭐{min_level}+{Fore.RESET}'

			info += f' ({len(messages)}) ({len(mentions)})'

			player_claim = self.PLAYER_CLAIMS.get(name, {})

			if not player['role']:
				if player_claim.get('role'):
					info += f' {Fore.CYAN}C: {player_claim["role"]}{Style.RESET_ALL}'
				
				if player.get('contradiction'):
					role = player['contradiction']
					info += f' {Back.RED}{Style.BRIGHT}CC: {role}{Style.RESET_ALL}'
				
			for protector, targets in self.PLAYER_ALLIANCES.items():
				for target, count in targets.items():
					if target == name:
						info += f' {Fore.BLUE}🛡️ by {protector} (x{count}){Style.RESET_ALL}'

			if player['role']:
				role = self.ROLES[player['role']]['name']
				info += f' - {role}'

			elif team:
				info += f' [{team}]'

			elif teams_exclude:
				teams_exclude = ', '.join(teams_exclude)

				info += f' [NOT {teams_exclude}]'

			if possible:
				info += ' + POSSIBLE '

				for p in range(len(possible)):
					role = possible[p]['role']
					has_card = possible[p]['has_card']
					has_icon = possible[p]['has_icon']

					info += role

					if not has_card and not has_icon:
						info += ' ❌⭕'

					elif not has_card:
						info += ' ❌'

					elif not has_icon:
						info += ' ⭕'

					if p != len(possible) - 1:
						info += ' / '

			threat = self.THREAT_LEVELS.get(name)

			if threat is not None:
				threat_color = Fore.GREEN

				if 30 <= threat < 70:
					threat_color = Fore.YELLOW
				
				elif threat >= 70:
					threat_color = Fore.RED
				
				info += f' {threat_color}[{threat}% ❕]{Fore.RESET}'

			if player['aura'] == 'GOOD':
				info = f'{Back.GREEN}{info}{Back.RESET}'

			elif player['aura'] == 'EVIL':
				info = f'{Back.RED}{info}{Back.RESET}'

			elif player['aura'] == 'UNKNOWN':
				info = f'{Back.CYAN}{info}{Back.RESET}'

			if player['dead']:
				info = f'\t{Style.DIM}{info}{Style.NORMAL}'

			else:
				info = f'{Style.BRIGHT}{info}'

			info += '\n'

			players_info += info

		print(f'{Style.BRIGHT}{players_info}{remaining_info}')
		print(self.bayes.render_cli())
		print(self.nlp.render_cli())

	def debug_mastermind(self):
		print(f'\n{Fore.CYAN}{Style.BRIGHT}--- STARTING MASTERMIND DEBUG ---{Fore.RESET}')
		
		mind = self.mastermind

		if not mind or not mind.profiles:
			print(f'{Back.RED}{Style.BRIGHT}Mastermind is not initialized.{Back.RESET}')
			
			return

		mind.update_state()
		state = mind.state

		print(f'{Style.BRIGHT}Step 1: Initializing simulation state')

		alive_players = [p for p in state.players if not p['dead'] and p['role']]
		
		if not alive_players:
			print(f'{Back.YELLOW}{Fore.BLACK}No living players with known roles found for analysis.{Back.RESET}')
			
			return

		print(f'\n{Style.BRIGHT}Step 2: Searching for potentially active players')
		print(f'  - Found living players with roles: {len(alive_players)}')

		total_actions_found = 0

		for player in alive_players:
			print(f'\n{Fore.GREEN}--- Analyzing Player: {player["name"]} (Role: {player["role"]}) ---{Fore.RESET}')
			
			abilities = mind.profiles.get(player['role'])

			if not abilities:
				print(f'  - {Back.RED}ERROR:{Back.RESET} Abilities for role "{player["role"]}" not found in role profiles!')
				
				continue

			print(f'  - Abilities found in profile: {len(abilities)}')

			for i, ability in enumerate(abilities):
				ability_type = ability.get('type', 'N/A')

				print(f'	{i + 1}) Ability "{ability_type}":')
				
				is_valid = mind.is_ability_valid(player, ability, state)

				if not is_valid:
					reason = 'max uses exceeded'
					
					print(f'	  - {Fore.YELLOW}Validity Check: FAILED (Reason: {reason}){Fore.RESET}')
					
					continue
				
				print(f'	  - {Fore.GREEN}Validity Check: PASSED{Fore.RESET}')

				targets = mind.get_potential_targets(player, ability.get('targets', {}), state)
				
				if not targets:
					print(f'	  - {Fore.YELLOW}Target Search: No valid targets found.{Fore.RESET}')
					
					continue
				
				target_names = [t['name'] for t in targets]

				print(f'	  - {Fore.GREEN}Target Search: Found {len(targets)} targets ({", ".join(target_names)}){Fore.RESET}')
				
				total_actions_found += len(targets)

		print(f'\n{Style.BRIGHT}--- DEBUG SUMMARY ---{Style.BRIGHT}')

		if total_actions_found > 0:
			print(f'{Fore.GREEN}Mastermind found {total_actions_found} possible actions.{Fore.RESET}')
		
		else:
			print(f'{Back.YELLOW}{Fore.BLACK}Mastermind found 0 possible actions.{Back.RESET}')

		input()

	def predict(self, player_name):
		if not self.mastermind or not self.mastermind.profiles:
			print(f'\n{Back.RED}{Style.BRIGHT}Mastermind is not ready!{Back.RESET}')
			
			return

		if not player_name:
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios...{Fore.RESET}')

		else:
			print(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios with focus on {player_name}...{Fore.RESET}')

		self.mastermind.update_state()

		scenarios = self.mastermind.predict(max_depth=3, prob_threshold=0.01, player_name=player_name)

		if not scenarios:
			print(f'{Style.BRIGHT}{Fore.YELLOW}No viable scenarios found.{Fore.RESET}')

			return
		
		print()

		for i, scenario in enumerate(scenarios[:5]):
			path_parts = []

			if scenario['path']:
				for action in scenario['path']:
					actor_name = action['actor']['name']
					ability = action['ability']
					ability_desc = ability['description']
					ability_type = ability.get('type', '')
					target = action.get('target')
					
					desc_color = Fore.WHITE
					
					if 'kill' in ability_type or 'lynch' in ability_type or 'ignite' in ability_type:
						desc_color = Fore.RED

					elif 'protect' in ability_type:
						desc_color = Fore.BLUE

					elif 'investigate' in ability_type or 'check' in ability_type:
						desc_color = Fore.CYAN

					target_text = ''

					if target:
						if isinstance(target, tuple):
							target_names = f'{Fore.YELLOW}, '.join([t['name'] for t in target])
							target_text = f' -> ({Fore.YELLOW}{target_names}{Style.RESET_ALL})'
						
						else:
							target_text = f' -> {Fore.YELLOW}{target["name"]}{Style.RESET_ALL}'
					
					path_parts.append(f'{Fore.GREEN}{actor_name}{Style.RESET_ALL}({desc_color}{ability_desc}{Style.RESET_ALL}{target_text})')
			
			path_text = f' {Fore.WHITE}->{Style.RESET_ALL} '.join(path_parts) if path_parts else f'{Fore.YELLOW}Initial State{Style.RESET_ALL}'

			print(f'{Style.BRIGHT}{Fore.GREEN}Scenario #{i + 1} ({Fore.YELLOW}{scenario["prob"]:.2%}{Fore.GREEN}):{Style.RESET_ALL}{path_text}')

		best_textategy = self.mastermind.optimize_strategy(scenarios)

		if best_textategy['action']:
			action = best_textategy['action']
			actor, ability, target = action['actor'], action['ability'], action.get('target')

			desc_color = Fore.WHITE
			ability_type = ability.get('type', '')

			if 'kill' in ability_type or 'lynch' in ability_type or 'ignite' in ability_type:
				desc_color = Fore.RED

			elif 'protect' in ability_type:
				desc_color = Fore.BLUE

			elif 'investigate' in ability_type or 'check' in ability_type:
				desc_color = Fore.CYAN
			
			target_text = ''

			if target:
				if isinstance(target, tuple):
					target_names = f'{Fore.YELLOW}, '.join([t['name'] for t in target])
					target_text = f' -> ({Fore.YELLOW}{target_names}{Style.RESET_ALL})'

				else:
					target_text = f' -> {Fore.YELLOW}{target["name"]}{Style.RESET_ALL}'

			print(f'\n{Style.BRIGHT}{Fore.GREEN}Recommended Action: {Fore.GREEN}{actor["name"]}{Style.RESET_ALL}({desc_color}{ability["description"]}{Style.RESET_ALL}{target_text})')
			print(f'{Style.BRIGHT}{Fore.GREEN}Success Probability: {Fore.YELLOW}{best_textategy["expected_success"]*100:.2f}%{Style.RESET_ALL}')

		return

	def process(self):
		cmd = input(f'\n{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ')

		if not cmd:
			return

		elif cmd.lower() == 'end':
			return 1

		elif '=' in cmd:
			if not(cmd.count('!=') == 1 or cmd.count('=') == 1):
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

				return

			equal = '!=' if '!=' in cmd else '='

			players = cmd.split(f' {equal} ')

			if len(players) == 2 and players[0].isdigit() and players[1].isdigit():
				players = list(map(int, players))

				if not (1 <= players[0] <= 16 and 1 <= players[1] <= 16):
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid number(s)!{Back.RESET}')

					return

				players[0] -= 1
				players[1] -= 1

				self.set_equal(players, equal == '=')

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

		elif cmd.lower().startswith('name of '):
			cmd = cmd.split(' ')

			if len(cmd) == 5 and cmd[3].lower() == 'is' and cmd[2].isdigit() and 1 <= int(cmd[2]) <= 16:
				player = int(cmd[2]) - 1
				name = cmd[4]

				self.set_name(player, name)

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

		elif cmd.lower().startswith('change '):
			query = cmd.lower().split('change ')[1].split(' to ')

			if len(query) == 2:
				src_role, dst_role = query

				self.change_role(src_role, dst_role)

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

		elif cmd.lower().startswith('remove '):
			query = cmd.lower().split('remove ')[1].split(' from ')

			if len(query) == 2:
				role, player = query

				if player.isdigit() and 1 <= int(player) <= 16:
					player = int(player) - 1

					self.remove_role(player, role)

				else:
					input(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

		elif cmd.lower() == 'cursed turned':
			self.set_cursed()

		elif cmd.lower().startswith('clear '):
			player = cmd.lower().split('clear ')[1]

			if player.isdigit() and 1 <= int(player) <= 16:
				player = int(player) - 1

				self.PLAYERS[player]['role'] = None
				self.PLAYERS[player]['team'] = None
				self.PLAYERS[player]['teams_exclude'] = set()
				self.PLAYERS[player]['equal'] = set()
				self.PLAYERS[player]['not_equal'] = set()

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid info!{Back.RESET}')

		elif cmd.lower() == 'storm':
			self.storm()

		elif cmd.lower() in ['undo', 'redo']:
			self.revert(cmd.lower() == 'undo')

			return -1

		elif cmd.lower().startswith('predict'):
			parts = cmd.lower().split()

			player_name = None

			if len(parts) == 2 and parts[1].isdigit():
				player = int(parts[1]) - 1

				if 0 <= player < 16 and self.PLAYERS[player]['name']:
					player_name = self.PLAYERS[player]['name']
			
			self.predict(player_name)
			
			input()

		elif cmd.lower() == 'debug':
			self.debug_mastermind()

		else:
			try:
				player, info = cmd.lower().split(' is ')
			except ValueError:
				print(f'\n{Style.BRIGHT}{Fore.RED}Usage:')
				print(f'{Style.BRIGHT}{Fore.RED}[number] is [role / aura / (not) team / dead / alive]')
				print(f'{Style.BRIGHT}{Fore.RED}[number] [= / !=] [number]')
				print(f'{Style.BRIGHT}{Fore.RED}Name of [number] is [name]')
				print(f'{Style.BRIGHT}{Fore.RED}Change [role] to [role]')
				print(f'{Style.BRIGHT}{Fore.RED}Remove [role] from [number]')
				print(f'{Style.BRIGHT}{Fore.RED}Clear [number]')
				print(f'{Style.BRIGHT}{Fore.RED}Cursed turned')
				print(f'{Style.BRIGHT}{Fore.RED}Storm to rediscover')
				print(f'{Style.BRIGHT}{Fore.RED}Enter to update')
				print(f'{Style.BRIGHT}{Fore.RED}Undo - cancel changes')
				print(f'{Style.BRIGHT}{Fore.RED}Redo - return changes')
				print(f'{Style.BRIGHT}{Fore.RED}Predict - get game scenarios from Mastermind')
				print(f'{Style.BRIGHT}{Fore.RED}Debug - trace Mastermind analysis')
				print(f'{Style.BRIGHT}{Fore.RED}End - stop Tracker')
				input()

				return

			self.set_player_info(player, info)

	def run(self):
		_integrity_checker.verify_silent()

		if _integrity_checker.get_corruption_handler().is_phantom_mode():
			def silent_fail(*args, **kwargs):
				class FakeResponse:
					status_code = 500

					def json(self):
						return {}

					def raise_for_status(self):
						pass
				
				time.sleep(random.uniform(0.1, 1.0))

				return FakeResponse()

			requests.get = silent_fail
			requests.post = silent_fail

		banner(self.__class__.__name__)

		try:
			with sync_playwright() as playwright:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Navigating to Wolvesville...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
					user_agent=self.USER_AGENT,
					viewport={
						'width': int(self.CHROME_VIEWPORT[0]),
						'height': int(self.CHROME_VIEWPORT[1])
					},
					headless=False,
					args=[
						'--window-position=-7,40',
						'--disable-blink-features=AutomationControlled'
					],
					ignore_default_args=['--enable-automation'],
					chromium_sandbox=True
				)

				self.page = context.pages[0]

				while True:
					try:
						self.page.goto('https://wolvesville.com', wait_until='domcontentloaded', timeout=120000)

						try:
							self.page.wait_for_load_state('networkidle', timeout=30000)
						except PlaywrightTimeoutError:
							pass

						break
					except PlaywrightTimeoutError:
						self.log_message('error', 'Timeout error, retrying...')

						continue

				self.log_message('success', 'Website opened!')

				changes = self.patch_localstorage()

				if changes:
					self.log_message('warning', f'Applied {changes} setting patches, reloading page...')

					self.page.reload(wait_until='domcontentloaded', timeout=120000)

					try:
						self.page.wait_for_load_state('networkidle', timeout=30000)
					except PlaywrightTimeoutError:
						pass

					self.log_message('success', 'Page reloaded, continuing...')

				while True:
					banner(self.__class__.__name__)

					if self.prepare():
						_pause(f'\n{Style.BRIGHT}{Back.RED}Invalid API key!{Back.RESET}')

						return

					self.log_message('info', 'Waiting for game start...')

					while True:
						try:
							phase_locator = None

							for n in range(2, 6):
								try:
									candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
									candidate.wait_for(state='visible', timeout=500)

									phase_locator = candidate.first

									break
								except PlaywrightTimeoutError:
									continue

							if not phase_locator:
								time.sleep(1)

								continue

							phase_text = phase_locator.text_content(timeout=1000)

							if is_game_phase(phase_text):
								break
						except PlaywrightTimeoutError:
							pass
						except KeyboardInterrupt:
							return

						time.sleep(1)

					print(f'{Style.BRIGHT}{Fore.GREEN}Game found!')

					self.get_bearer()
					self.load_css()
					self.load_modal()

					players_grid_xpath = self.find_players_grid_xpath()

					self.find_players(players_grid_xpath)

					roles = self.find_roles()
					rotations = self.get_rotations()

					print(f'{Style.BRIGHT}{Fore.YELLOW}Finding rotation...')

					self.ROTATION = self.choose_rotation(rotations, roles)

					if self.ROTATION is None:
						_pause(f'\n{Style.BRIGHT}{Back.RED}Rotation not found!{Back.RESET}')

						return

					print(f'{Style.BRIGHT}{Fore.GREEN}Rotation found!')

					while True:
						self.monitor()

						result = self.process()

						if result == 1:
							break

						if not result:
							self.update_players()
		except KeyboardInterrupt:
			return
		except AttributeError:
			pass
		except Exception as e:
			_pause(f'\n{Style.BRIGHT}{Back.RED}{str(e)}{Back.RESET}')

			return

	def to_dict(self):
		return {
			'players': [{
				'index': i + 1,
				'name': p.get('name'),
				'level': p.get('level', -1),
				'min_level': p.get('min_level', -1),
				'role': p.get('role'),
				'team': p.get('team'),
				'teams_exclude': list(p.get('teams_exclude', set())),
				'aura': p.get('aura'),
				'dead': p.get('dead', False),
				'equal': list(p.get('equal', set())),
				'not_equal': list(p.get('not_equal', set())),
				'hero': p.get('hero', False),
				'messages': p.get('messages', []),
				'mentions': p.get('mentions', [])
			} for i, p in enumerate(self.PLAYERS)],
			
			'rotation': [{
				'id': r.get('id'),
				'name': r.get('name'),
				'team': r.get('team'),
				'aura': r.get('aura')
			} for r in self.ROTATION],
			
			'threat_levels': dict(self.THREAT_LEVELS) if hasattr(self, 'THREAT_LEVELS') else {},
			'player_claims': dict(self.PLAYER_CLAIMS) if hasattr(self, 'PLAYER_CLAIMS') else {},
			'player_alliances': dict(self.PLAYER_ALLIANCES) if hasattr(self, 'PLAYER_ALLIANCES') else {}
		}
