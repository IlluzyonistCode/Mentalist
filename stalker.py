import requests
import threading
import ntplib
import pytz
import dateutil.parser
import json
import os
import re
import time
import random
import uuid
import webbrowser
from undetected_playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from copy import deepcopy
from collections import OrderedDict
from itertools import combinations
from datetime import datetime, timedelta
from tzlocal import get_localzone
from playsound3 import playsound
from colorama import Back, Fore, Style
from dotenv import dotenv_values
from pathlib import Path
from auth_decorator import require_module_auth
from auth_protection import _integrity_checker
from data_protection import save_encrypted, load_encrypted
from utils import (
	BASE_DIR,
	MENTALIST_DATA_DIR,
	USER_DATA_DIR,
	CONFIG_PATH,
	_launch_mode,
	_pause,
	get_resource_path,
	find_chrome_executable,
	generate_random_user_agent,
	banner
)

class Stalker:
	@require_module_auth('stalker')
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)
		self.is_valid = True

		try:
			self.API_KEYS = self.config['STALKER_API_KEYS'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Stalker Error: API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = find_chrome_executable()

		if not self.CHROME_EXECUTABLE:
			print(f'{Style.BRIGHT}{Back.RED}Stalker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_USER_DATA = USER_DATA_DIR / 'Mentalist'

		os.makedirs(self.CHROME_USER_DATA, exist_ok=True)

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Stalker Error: Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			print(f'{Style.BRIGHT}{Back.RED}Stalker Error: Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.TIMEZONE = self.get_system_timezone()

		self.ntp = ntplib.NTPClient()
		self.NTP_SERVER = 'time.google.com'

		self.API_KEY = self.switch_api_key()

		self.BEARER_TOKEN = None
		self.CF_JWT = None

		self.BOT_BASE_URL = 'https://api.wolvesville.com/'
		self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'

		self.BEARER_HEADERS = {}

		self.TARGETS = OrderedDict()
		self.CLAN_CHANGES = {}
		self.INFO_CHANGES = {}

		self.updating = False
		self.page = None
		self.monitor_page = 1

		self.load_targets()

		threading.Thread(target=self.auto_update, daemon=True).start()

	def _is_phantom(self):
		try:
			return _integrity_checker.get_corruption_handler().is_phantom_mode()
		except:
			return False

	@staticmethod
	def _generate_fake_player_data(player_id):
		fake_names = ['Ghost', 'Unknown', 'NullPtr', 'System', 'Admin', 'User_123']

		return {
			'id': player_id,
			'username': f"{random.choice(fake_names)}_{random.randint(100, 999)}",
			'level': random.randint(1, 500),
			'status': random.choice(['ONLINE', 'OFFLINE', 'PLAYING']),
			'lastOnline': (datetime.utcnow() - timedelta(hours=random.randint(0, 100))).isoformat(),
			'clanId': str(uuid.uuid4()) if random.random() > 0.5 else None,
			'receivedDio': random.choice([True, False]),
			'creationTime': (datetime.utcnow() - timedelta(days=random.randint(100, 1000))).isoformat()
		}

	@staticmethod
	def get_system_timezone():
		try:
			sys_tz = get_localzone()

			return pytz.timezone(str(sys_tz))
		except:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Could not detect local timezone. Defaulting to UTC.')

			return pytz.utc

	@staticmethod
	def convert_play_time(minutes):
		if minutes == -1:
			return -1

		hours = str(minutes // 60).zfill(2)
		minutes = str(minutes % 60).zfill(2)

		return f'{hours}:{minutes}'

	@staticmethod
	def help_message(error=False):
		color = Fore.RED if error else Fore.YELLOW

		print(f'{Style.BRIGHT}{color}Usage:')
		print(f'{Style.BRIGHT}{color}Add [IN-GAME NAME]')
		print(f'{Style.BRIGHT}{color}Delete [ID]')
		print(f'{Style.BRIGHT}{color}Move [NEW ID] to [NEW ID]')
		print(f'{Style.BRIGHT}{color}Update - update all players')
		print(f'{Style.BRIGHT}{color}Update [ID] - update chosen player')
		print(f'{Style.BRIGHT}{color}Plot [ID] [ID]... - plot graphs for players')
		print(f'{Style.BRIGHT}{color}P [PAGE]')
		print(f'{Style.BRIGHT}{color}L - previous page')
		print(f'{Style.BRIGHT}{color}R - next page')
		print(f'{Style.BRIGHT}{color}Enter to refresh')
		print(f'{Style.BRIGHT}{color}End - stop Stalker')

		_pause() if error else print()

	@property
	def total_pages(self):
		return max(len(self.TARGETS) // 5 + int(len(self.TARGETS) % 5 > 0), 1)

	@property
	def bot_headers(self):
		api_key = next(self.API_KEY)

		return {
			'Authorization': f'Bot {api_key}',
			'Accept': 'application/json',
			'Content-Type': 'application/json'
		}

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

	def normalize_time(self, dt):
		if not dt:
			return ''

		dt = dateutil.parser.parse(dt)
		dt = dt.astimezone(self.TIMEZONE)
		dt = dt.strftime('%d.%m.%Y %H:%M:%S')

		return dt

	def switch_api_key(self):
		while True:
			for key in self.API_KEYS:
				yield key

	def load_targets(self):
		targets = load_encrypted('targets')
			
		if targets is not None:
			self.TARGETS = OrderedDict(targets)

		else:
			self.TARGETS = OrderedDict()

	def write_target(self, target_id, info=None):
		if info is None:
			self.TARGETS.pop(target_id)

		else:
			if target_id not in self.TARGETS:
				self.TARGETS[target_id] = []

			self.TARGETS[target_id].append(info)

			if len(self.TARGETS[target_id]) == 3:
				self.TARGETS[target_id].pop(0)

	def save_targets(self):
		if not os.path.isdir(MENTALIST_DATA_DIR):
			os.mkdir(MENTALIST_DATA_DIR)

		save_encrypted('targets', self.TARGETS)

	def get_current_time(self):
		try:
			data = self.ntp.request(self.NTP_SERVER)
		
			return time.ctime(data.tx_time)
		except ntplib.NTPException:
			return

	def add_changes(self, prev_target, target, diff, current_time, clan=False):
			if not os.path.isdir(MENTALIST_DATA_DIR):
				os.mkdir(MENTALIST_DATA_DIR)

			if not os.path.isdir(MENTALIST_DATA_DIR / 'targets'):
				os.mkdir(MENTALIST_DATA_DIR / 'targets')

			target_id = target['id']

			if clan:
				target = target['clan']
				prev_target = prev_target['clan']

			if diff:
				with open(f'{MENTALIST_DATA_DIR}/targets/{target_id}.txt', 'a', encoding='utf-8') as f:
					f.write(f'{current_time}\n\n')

					if not target:
						f.write('Left the clan!\n\n')

						return

					for d in diff:
						new_val = target.get(d)
						prev_val = prev_target.get(d)

						if not new_val or new_val == -1:
							new_val = 'HIDDEN'

						if not prev_val or prev_val == -1:
							prev_val = 'HIDDEN'

						if new_val == prev_val:
							continue

						field = 'Clan ' if clan else ''
						field += d.replace('_', ' ').capitalize()

						prev_value = prev_val
						value = new_val

						change_info = f'{field}: {prev_value} -> {value}\n'

						f.write(change_info)

					f.write('\n')

	def auto_update(self):
		while True:
			time.sleep(random.randint(60, 300))

			self.update_targets()

	def get_changes(self, prev_target, target):
		if not all([prev_target, target]):
			return

		d1 = deepcopy(prev_target)
		d2 = deepcopy(target)

		clan1 = d1.pop('clan').items()
		clan2 = d2.pop('clan').items()

		info1 = d1.items()
		info2 = d2.items()

		info_diff = list(dict(info1 - info2))
		clan_diff = list(dict(clan1 - clan2))

		if not any([info_diff, clan_diff]):
			return

		current_time = self.get_current_time()

		if current_time:
			self.add_changes(prev_target, target, clan_diff, current_time, True)
			self.add_changes(prev_target, target, info_diff, current_time)

		return clan_diff, info_diff

	def get_clan(self, clan_id):
		ENDPOINT = f'clans/{clan_id}/info'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()

		name = data.get('name')
		description = data.get('description')
		created = self.normalize_time(data.get('creationTime'))
		total_xp = data.get('xp')
		language = data.get('language')
		tag = data.get('tag')
		member_count = data.get('memberCount')

		clan_data = {
			'name': name,
			'description': description,
			'created': created,
			'language': language,
			'tag': tag,
			'member_count': member_count,
			'members': {}
		}

		ENDPOINT = f'clans/{clan_id}/members'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()

		for player in data:
			player_id = player.get('playerId')
			player_xp = player.get('xp')
			co_leader = player.get('isCoLeader')
			flair = player.get('flair')
			joined = self.normalize_time(player.get('creationTime'))

			clan_data['members'][player_id] = {
				'player_xp': player_xp,
				'co_leader': co_leader,
				'flair': flair,
				'joined': joined
			}

		return 0, clan_data

	def get_player_id(self, username):
		ENDPOINT = f'players/search?username={username}'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return data.status_code, data.text

		data = data.json().get('id')

		return 0, data

	def predict_level_by_xp(self, player_id):
		if self._is_phantom():
			return random.randint(1, 1000)

		if self.page is None:
			return -1

		ENDPOINT = 'highScores/top100Friends'

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
			return

		data = response['body']['ranks']
		
		player = dict((d['playerId'], dict(xp=d['xp'])) for d in data).get(player_id)

		if not player:
			return

		k = 0.000500205
		b = 8.85

		level = int(k * player['xp'] + b)

		return level

	def get_player_friends_count(self, player_id):
		if self.page is None:
			return -1

		ENDPOINT = f'players/{player_id}'

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
			return -1

		data = response['body']

		friends_count = int(data.get('friendsCount', -1))

		return friends_count

	def get_player(self, player_id):
		if self._is_phantom():
			time.sleep(random.uniform(0.1, 0.5))
				
			return 0, self._generate_fake_player_data(player_id)

		ENDPOINT = f'players/{player_id}'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()
		game_stats = data.get('gameStats', {})

		name = data.get('username')
		level = data.get('level', -1)
		bio = data.get('personalMessage')
		status = data.get('status')

		friends_count = self.get_player_friends_count(player_id)

		if friends_count == -1:
			if self.TARGETS.get(player_id):
				friends_count = self.TARGETS[player_id][-1]['friends_count']

			else:
				friends_count = -1

		if level == -1:
			time.sleep(1)

			level = self.predict_level_by_xp(player_id)

			if not level:
				if self.TARGETS.get(player_id):		
					level = self.TARGETS[player_id][-1]['level']

				else:
					level = '?'

		if status == 'PLAY':
			status = '✅'

		elif status == 'DEFAULT':
			status = '⚪'

		elif status == 'DND':
			status = '🔴'

		elif status == 'OFFLINE':
			status = '📵'

		last_online = self.normalize_time(data.get('lastOnline'))
		created = self.normalize_time(data.get('creationTime'))

		received_roses = data.get('receivedRosesCount', -1)
		sent_roses = data.get('sentRosesCount', -1)

		win_count = game_stats.get('totalWinCount', -1)
		lose_count = game_stats.get('totalLoseCount', -1)
		tie_count = game_stats.get('totalTieCount', -1)

		play_time = self.convert_play_time(game_stats.get('totalPlayTimeInMinutes', -1))

		village_win_count = game_stats.get('villageWinCount', -1)
		village_lose_count = game_stats.get('villageLoseCount', -1)

		werewolf_win_count = game_stats.get('werewolfWinCount', -1)
		werewolf_lose_count = game_stats.get('werewolfLoseCount', -1)

		voting_win_count = game_stats.get('votingWinCount', -1)
		voting_lose_count = game_stats.get('votingLoseCount', -1)

		solo_win_count = game_stats.get('soloWinCount', -1)
		solo_lose_count = game_stats.get('soloLoseCount', -1)

		clan_id = data.get('clanId')
		clan = {}

		if clan_id:
			clan = self.get_clan(clan_id)

			if not clan[0]:
				clan = clan[1]
				clan.update(clan.pop('members').get(player_id, {}))

			else:
				clan = {}

		player_data = {
			'id': player_id,
			'name': name,
			'level': level,
			'bio': bio,
			'status': status,
			'last_online': last_online,
			'created': created,
			'friends_count': friends_count,
			'received_roses': received_roses,
			'sent_roses': sent_roses,
			'win_count': win_count,
			'lose_count': lose_count,
			'tie_count': tie_count,
			'play_time': play_time,
			'village_win_count': village_win_count,
			'village_lose_count': village_lose_count,
			'werewolf_win_count': werewolf_win_count,
			'werewolf_lose_count': werewolf_lose_count,
			'voting_win_count': voting_win_count,
			'voting_lose_count': voting_lose_count,
			'solo_win_count': solo_win_count,
			'solo_lose_count': solo_lose_count,
			'clan': clan
		}

		return 0, player_data

	def update_targets(self, target_id=None):
		if self.updating:
			return

		self.updating = True

		targets = [target_id] if target_id else list(self.TARGETS)

		for target_id in targets:
			try:
				data = self.get_player(target_id)
			except requests.exceptions.ConnectionError:
				continue

			if data[0]:
				input(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

				continue

			self.write_target(target_id, data[1])

			time.sleep(1)

		changes_detected = False

		for i, target in enumerate(self.TARGETS.values()):
			prev_target = deepcopy(target[0]) if len(target) == 2 else {}
			target = deepcopy(target[-1])
			target_id = target['id']

			self.CLAN_CHANGES[target_id] = set()
			self.INFO_CHANGES[target_id] = set()

			changes = self.get_changes(prev_target, target)

			if changes:
				changes_detected = True

				self.CLAN_CHANGES[target_id].update(changes[0])
				self.INFO_CHANGES[target_id].update(changes[1])

		if changes_detected:
			self.save_targets()

			sound_path = get_resource_path(os.path.join('audio', 'illusionist.mp3'))
			playsound(sound_path, block=True)

		self.updating = False

	def plot_targets(self, indices):
		import numpy as np
		import pandas as pd
		import plotly.graph_objects as go
		from plotly.subplots import make_subplots

		print(f'{Style.BRIGHT}{Fore.YELLOW}Analyzing data & Predicting future...{Fore.RESET}')

		np.seterr(divide='ignore', invalid='ignore')

		plotly_colors = ['#00FF00', '#FF0000', '#0000FF', '#FFA500', '#800080', '#00FFFF', '#FF00FF', '#FFFF00']
		console_colors = [Fore.GREEN, Fore.RED, Fore.BLUE, Fore.YELLOW, Fore.MAGENTA, Fore.CYAN, Fore.MAGENTA, Fore.YELLOW]
		
		fig = make_subplots(specs=[[{'secondary_y': True}]])
		
		log_header_fmt = '%a %b %d %H:%M:%S %Y'
		online_fmt = '%d.%m.%Y %H:%M:%S'
		
		re_header = re.compile(r'^[A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+\d{4}')
		re_online = re.compile(r'Last online:\s+(.+?)\s+->\s+(.+)')
		re_xp = re.compile(r'Clan Player xp:\s+(\d+|HIDDEN)\s+->\s+(\d+|HIDDEN)')

		player_data = {}
		all_timestamps = []
		targets_found = False

		for idx, list_index in enumerate(indices):
			try:
				target_id = list(self.TARGETS)[list_index]
				target_data = self.TARGETS[target_id][-1]
				player_name = target_data.get('name', target_id)
			except IndexError:
				continue

			filename = f'{MENTALIST_DATA_DIR}/targets/{target_id}.txt'

			if not os.path.exists(filename):
				print(f'{Style.BRIGHT}{Back.RED}Log file for {player_name} not found!{Back.RESET}')

				continue

			targets_found = True
			p_color = plotly_colors[idx % len(plotly_colors)]
			c_color = console_colors[idx % len(console_colors)]
			
			sessions = []
			xp_points = []
			current_log_context = None

			with open(filename, 'r', encoding='utf-8') as f:
				lines = f.readlines()

			for line in lines:
				line = line.strip()

				if not line:
					continue

				if re_header.match(line):
					try:
						clean_ts = re.sub(r'\s+', ' ', line)
						current_log_context = datetime.strptime(clean_ts, log_header_fmt)
					except ValueError:
						pass

					continue

				online_match = re_online.search(line)

				if online_match:
					start_str, end_str = online_match.groups()

					try:
						dt_start = datetime.strptime(start_str, online_fmt)
						dt_end = datetime.strptime(end_str, online_fmt)
						duration = (dt_end - dt_start).total_seconds() / 60
						
						if 0 < duration < 360:
							sessions.append({
								'Start': dt_start,
								'End': dt_end,
								'Duration': duration
							})

							all_timestamps.append(dt_start)
							all_timestamps.append(dt_end)
					except ValueError:
						pass

					continue

				if current_log_context:
					xp_match = re_xp.search(line)

					if xp_match:
						old_xp, new_xp = xp_match.groups()

						if new_xp != 'HIDDEN' and new_xp.isdigit():
							val = int(new_xp)

							if not xp_points or xp_points[-1]['XP'] != val:
								xp_points.append({
									'Time': current_log_context,
									'XP': val
								})

								all_timestamps.append(current_log_context)

			sessions.sort(key=lambda x: x['Start'])
			xp_points.sort(key=lambda x: x['Time'])

			player_data[player_name] = {
				'sessions': sessions,
				'xp': xp_points,
				'color': p_color,
				'console_color': c_color,
				'index': list_index
			}

		if not targets_found or not all_timestamps:
			print(f'{Style.BRIGHT}{Back.RED}No valid data found to analyze!{Back.RESET}')

			return

		print(f'{Style.BRIGHT}{Fore.CYAN}--- RELATIONSHIP REPORT ---{Fore.RESET}')
		
		max_hist_time = max(all_timestamps)
		min_hist_time = min(all_timestamps).replace(second=0)
		
		full_rng = pd.date_range(start=min_hist_time, end=max_hist_time + timedelta(minutes=1), freq='1min')
		df_matrix = pd.DataFrame(index=full_rng)
		
		for name, data in player_data.items():
			x_lines = []
			y_lines = []

			for s in data['sessions']:
				x_lines.extend([s['Start'], s['End'], None])
				y_lines.extend([data['index'], data['index'], None])

			if x_lines:
				fig.add_trace(
					go.Scatter(
						x=x_lines,
						y=y_lines,
						mode='lines',
						line=dict(color=data['color'], width=12),
						name=f'{name} Online',
						legendgroup=name,
						hoverinfo='name+x'
					),
					secondary_y=False
				)

			if data['xp']:
				df_xp = pd.DataFrame(data['xp'])

				fig.add_trace(
					go.Scatter(
						x=df_xp['Time'],
						y=df_xp['XP'],
						mode='lines+markers',
						line=dict(color=data['color'], width=2),
						marker=dict(size=5),
						name=f'{name} XP',
						legendgroup=name,
						hovertemplate=f'<b>{name}</b><br>XP: %{{y}}<br>%{{x}}<extra></extra>'
					),
					secondary_y=True
				)

			series = pd.Series(0, index=full_rng)

			for s in data['sessions']:
				s_r = s['Start'].replace(second=0)
				e_r = s['End'].replace(second=0) + timedelta(minutes=1)
				series.loc[s_r:e_r] = 1

			for x in data['xp']:
				t = x['Time'].replace(second=0)
				series.loc[t - timedelta(minutes=1) : t + timedelta(minutes=1)] = 1

			df_matrix[name] = series.rolling(window=5, center=True, min_periods=1).max().fillna(0)

		players = list(player_data.keys())

		if len(players) > 1:
			for p1, p2 in combinations(players, 2):
				vec1 = df_matrix[p1]
				vec2 = df_matrix[p2]
				
				intersection = (vec1 * vec2).sum()
				min_duration = min(vec1.sum(), vec2.sum())
				
				coop_score = intersection / min_duration if min_duration > 0 else 0
				
				sync_count = 0
				xp_sync_count = 0
				sessions1 = player_data[p1]['sessions']
				sessions2 = player_data[p2]['sessions']
				
				for s1 in sessions1:
					for s2 in sessions2:
						if abs((s1['Start'] - s2['Start']).total_seconds()) <= 180:
							sync_count += 1

						elif abs((s1['End'] - s2['End']).total_seconds()) <= 180:
							sync_count += 1
							
				xp1 = player_data[p1]['xp']
				xp2 = player_data[p2]['xp']

				for x1 in xp1:
					for x2 in xp2:
						if abs((x1['Time'] - x2['Time']).total_seconds()) <= 60:
							xp_sync_count += 1

				score = (coop_score * 0.6) + (min(xp_sync_count, 5) / 5 * 0.4)
				
				if score < 0.1 and sync_count == 0:
					continue

				verdict = 'Strangers'
				verdict_color = Fore.WHITE
				
				if xp_sync_count >= 3:
					verdict = 'High Sync / Party / Multiboxing'
					verdict_color = Fore.GREEN

				elif coop_score > 0.7:
					verdict = 'Duo / Soulmates'
					verdict_color = Fore.CYAN

				elif coop_score > 0.3:
					verdict = 'Friends'
					verdict_color = Fore.YELLOW

				print(f'{Style.BRIGHT}{p1} <-> {p2}:')
				print(f'  Co-op Score: {coop_score:.2f} (Played together {int(intersection)} mins)')
				print(f'  Login/Logout Sync: {sync_count} | XP Sync: {xp_sync_count}')
				print(f'  Verdict: {verdict_color}{verdict}{Style.RESET_ALL}\n')

		future_start = max_hist_time
		future_end = future_start + timedelta(hours=24)
		prediction_steps = pd.date_range(start=future_start, end=future_end, freq='15min')

		for name, data in player_data.items():
			activity_timestamps = []

			for s in data['sessions']:
				curr = s['Start']

				while curr < s['End']:
					activity_timestamps.append(curr)
					curr += timedelta(minutes=15)

			for x in data['xp']:
				activity_timestamps.append(x['Time'])

			if not activity_timestamps:
				continue

			activity_profile = np.zeros(96)

			for t in activity_timestamps:
				slot = (t.hour * 4) + (t.minute // 15)
				activity_profile[slot] += 1

			max_act = np.max(activity_profile)

			if max_act == 0:
				continue
			
			pred_x = []
			pred_y = []
			pred_text = []
			
			next_session_time = None

			for step_time in prediction_steps:
				slot = (step_time.hour * 4) + (step_time.minute // 15)
				prob = activity_profile[slot] / max_act

				if prob >= 0.5:
					if next_session_time is None:
						next_session_time = step_time
					
					pred_x.extend([step_time, step_time + timedelta(minutes=15), None])
					pred_y.extend([data['index'], data['index'], None])
					
					prob_str = f"{prob:.0%}"
					pred_text.extend([prob_str, prob_str, ''])
			
			if next_session_time:
				time_str = next_session_time.strftime('%a %H:%M')

				print(f'{data["console_color"]}Ghost Trace ({name}): Expect online at {time_str}{Fore.RESET}')

			if pred_x:
				fig.add_trace(
					go.Scatter(
						x=pred_x,
						y=pred_y,
						mode='lines',
						line=dict(color=data['color'], width=12, dash='dot'),
						opacity=0.5,
						name=f'{name} (Forecast)',
						legendgroup=name,
						showlegend=False,
						customdata=pred_text,
						hovertemplate=f'<b>{name} Forecast</b><br>Time: %{{x|%H:%M}}<br>Probability: %{{customdata}}<extra></extra>'
					),
					secondary_y=False
				)

		fig.update_layout(
			title='Stalker Analysis + AI Forecast (24h)',
			template='plotly_dark',
			hovermode='closest',
			height=800,
			legend=dict(orientation='h', y=1.02, xanchor='right', x=1),
			shapes=[dict(
				type='line',
				x0=future_start, x1=future_start,
				y0=-1, y1=len(self.TARGETS), xref='x', yref='y',
				line=dict(color='white', width=1, dash='dash')
			)]
		)

		tick_vals = []
		tick_text = []

		for name, data in player_data.items():
			tick_vals.append(data['index'])
			tick_text.append(name)

		fig.update_yaxes(
			title_text='Activity',
			tickvals=tick_vals,
			ticktext=tick_text,
			secondary_y=False,
			range=[-1, len(self.TARGETS)]
		)

		fig.update_yaxes(
			title_text='XP Growth',
			secondary_y=True,
			showgrid=False
		)
		
		fig.update_xaxes(title_text='Timeline (Past | Future)')
		
		output_path = '{MENTALIST_DATA_DIR}/targets/plot_analysis.html'

		if not os.path.exists('targets'):
			os.mkdir('targets')
		
		fig.write_html(output_path)

		print(f'\n{Style.BRIGHT}{Fore.GREEN}Analysis saved! Opening...{Fore.RESET}')

		try:
			import webbrowser

			webbrowser.open('file://' + os.path.abspath(output_path))
		except:
			pass
		
		input(f'\n{Style.BRIGHT}{Fore.YELLOW}Press Enter to continue...{Fore.RESET}')

	def monitor(self):
		banner(self.__class__.__name__)

		targets_range = range((self.monitor_page - 1) * 5, self.monitor_page * 5)
		pages_info = f'{Fore.YELLOW}PAGE {self.monitor_page}/{self.total_pages}{Fore.RESET}\n\n'
		targets_info = ''

		for i, target in enumerate(self.TARGETS.values()):
			if i not in targets_range:
				continue

			prev_target = deepcopy(target[0]) if len(target) == 2 else {}
			target = deepcopy(target[-1])
			player_id = target['id']

			for field in target:
				if field == 'status':
					continue

				if field in self.INFO_CHANGES.get(player_id, []):
					target[field] = f'{Fore.GREEN}{target[field]}{Fore.RESET}'

			for field in target['clan']:
				if 'xp' in field and target['clan'][field]:
					target['clan'][field] = str(target['clan'][field]) + 'xp'

				if field in self.CLAN_CHANGES.get(player_id, []):
					target['clan'][field] = f'{Fore.GREEN}{target["clan"][field]}{Fore.RESET}'

			name = target['name']
			level = target['level']
			bio = target['bio']
			status = target['status']

			last_online = target['last_online']
			created = target['created']

			friends_count = target['friends_count']

			received_roses = target['received_roses']
			sent_roses = target['sent_roses']

			win_count = target['win_count']
			lose_count = target['lose_count']
			tie_count = target['tie_count']

			play_time = target['play_time']

			village_win_count = target['village_win_count']
			village_lose_count = target['village_lose_count']

			werewolf_win_count = target['werewolf_win_count']
			werewolf_lose_count = target['werewolf_lose_count']

			voting_win_count = target['voting_win_count']
			voting_lose_count = target['voting_lose_count']

			solo_win_count = target['solo_win_count']
			solo_lose_count = target['solo_lose_count']

			clan = target['clan']

			clan_name = clan.get('name')
			tag = clan.get('tag') or ''
			language = clan.get('language')
			member_count = clan.get('member_count')
			player_xp = clan.get('player_xp', '?xp')
			flair = clan.get('flair')
			co_leader = clan.get('co_leader')
			joined = clan.get('joined')

			if tag:
				tag += ' |'

			info = f'{i + 1}\n{player_id}\n'
			info += f'{tag}{name} {level} {status} {last_online}\n'

			if clan:
				info += f'🏰 {clan_name} {member_count}/50 {language} {player_xp}'
				info += f' ({flair})' if flair else ''
				info += f' {joined}' if joined else ''
				info += ' CO-LEADER' if co_leader else ''
				info += '\n'

			info += f'{bio}\n'

			if friends_count != -1:
				info += f'👤 {friends_count}\n'

			if received_roses != -1:
				info += f'🌹 {received_roses} {sent_roses}\n'

			if win_count != -1:
				info += f'🥇 {win_count} ❌ {lose_count} ☠  {tie_count}\n'

			if play_time != -1:
				info += f'⌚ {play_time}\n'

			if village_win_count != -1:
				info += f'🏠 {village_win_count} {village_lose_count}\n'

			if werewolf_win_count != -1:
				info += f'🐺 {werewolf_win_count} {werewolf_lose_count}\n'

			if voting_win_count != -1:
				info += f'👆 {voting_win_count} {voting_lose_count}\n'

			if solo_win_count != -1:
				info += f'🔪 {solo_win_count} {solo_lose_count}\n'

			if created:
				info += f'⏳ {created}\n'

			targets_info += info + '\n'

		if targets_info:
			print(f'{Style.BRIGHT}{pages_info}{targets_info}')

		else:
			self.help_message()

	def process(self):
		cmd = input(f'{Style.BRIGHT}{Fore.RED}>{Fore.RESET} ')

		if not cmd:
			return

		elif cmd.lower() == 'end':
			return 1

		elif cmd.lower() == 'update':
			self.update_targets()

		elif cmd.lower().startswith('move'):
			try:
				old_id, new_id = map(int, cmd.split('move ')[1].split(' to '))

				if not 1 <= old_id <= len(self.TARGETS):
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid old ID!{Back.RESET}')

				elif not 1 <= new_id <= len(self.TARGETS):
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid new ID!{Back.RESET}')

				else:
					self.TARGETS.move_to_end(list(self.TARGETS)[old_id - 1])

					for target in list(self.TARGETS)[new_id - 1:-1]:
						self.TARGETS.move_to_end(target)

					self.save_targets()
			except (ValueError, IndexError):
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid IDs!{Back.RESET}')

				return

		elif 0 and cmd.lower().startswith('plot '):
			try:
				args = cmd.split(' ')[1:]
				indices = []
				
				for arg in args:
					idx = int(arg)

					if 1 <= idx <= len(self.TARGETS):
						indices.append(idx - 1)

					else:
						print(f'{Style.BRIGHT}{Back.RED}ID {idx} out of range!{Back.RESET}')
				
				if indices:
					self.plot_targets(indices)
			except ValueError:
				input(f'\n{Style.BRIGHT}{Back.RED}Invalid IDs!')

		elif cmd.lower() == 'l':
			if self.monitor_page != 1:
				self.monitor_page -= 1

		elif cmd.lower() == 'r':
			if self.monitor_page != self.total_pages:
				self.monitor_page += 1

		else:
			try:
				cmd, target = cmd.split(' ')
			except ValueError:
				self.help_message(True)

				return

			if cmd.lower() == 'add':
				if len(self.TARGETS) == 50:
					input(f'\n{Style.BRIGHT}{Back.RED}Too many targets!{Back.RESET}')

					return

				data = self.get_player_id(target)

				if data[0] == 404:
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid name!{Back.RESET}')

					return

				elif data[0]:
					input(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

					return

				target_id = data[1]

				if target_id in self.TARGETS:
					input(f'\n{Style.BRIGHT}{Back.RED}The player is already a target!{Back.RESET}')

					return

				data = self.get_player(target_id)

				if data[0]:
					input(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

					return

				self.write_target(target_id, data[1])
				self.save_targets()

				if self.monitor_page == self.total_pages - 1:
					self.monitor_page += 1

			elif cmd.lower() == 'delete':
				try:
					target = int(target) - 1

					if target < 0:
						input(f'\n{Style.BRIGHT}{Back.RED}Invalid ID!{Back.RESET}')

					else:
						target_id = list(self.TARGETS)[target]

						self.write_target(target_id)
						self.save_targets()

						if self.monitor_page == self.total_pages + 1:
							self.monitor_page -= 1
				except (ValueError, IndexError):
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid ID!{Back.RESET}')

			elif cmd.lower() == 'update':
				try:
					target = int(target) - 1

					if target < 0:
						input(f'\n{Style.BRIGHT}{Back.RED}Invalid ID!{Back.RESET}')

					else:
						target_id = list(self.TARGETS)[target]

						self.update_targets(target_id)
				except (ValueError, IndexError):
					input(f'\n{Style.BRIGHT}{Back.RED}Invalid ID!{Back.RESET}')

			elif cmd.lower() == 'p':
				try:
					target = int(target)

					if 1 <= target <= self.total_pages:
						self.monitor_page = target

					else:
						input(f'\n{Style.BRIGHT}{Back.RED}Incorrect page!{Back.RESET}')
				except ValueError:
					input(f'\n{Style.BRIGHT}{Back.RED}Incorrect page!{Back.RESET}')

			else:
				input(f'\n{Style.BRIGHT}{Back.RED}Incorrect command!{Back.RESET}')

	def run(self):
		banner(self.__class__.__name__)

		try:
			with sync_playwright() as playwright:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Navigating to Wolvesville in background...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
					user_agent=self.USER_AGENT,
					viewport={
						'width': int(self.CHROME_VIEWPORT[0]),
						'height': int(self.CHROME_VIEWPORT[1])
					},
					headless=True,
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
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=120000)

						break
					except PlaywrightTimeoutError:
						print(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')

						continue

				changes = self.patch_localstorage()

				if changes:
					self.log_message('warning', f'Applied {changes} setting patches, reloading page...')

					self.page.reload(wait_until='domcontentloaded', timeout=120000)
					self.page.wait_for_load_state('networkidle', timeout=30000)

					self.log_message('success', 'Page reloaded, continuing...')

				self.get_bearer()

				while True:
					self.monitor()

					if self.process():
						break
		except KeyboardInterrupt:
			return
		except Exception as e:
			input(f'\n{Style.BRIGHT}{Back.RED}{str(e)}{Back.RESET}')

			return

	def to_dict(self, page=1, per_page=5):
		start = (page - 1) * per_page
		end = start + per_page
		
		targets = []

		for i, (target_id, target_data) in enumerate(list(self.TARGETS.items())[start:end]):
			if not target_data:
				continue
			
			latest = target_data[-1]
			targets.append({
				'id': target_id,
				'index': start + i + 1,
				'name': latest.get('name'),
				'level': latest.get('level'),
				'bio': latest.get('bio'),
				'status': latest.get('status'),
				'last_online': latest.get('last_online'),
				'created': latest.get('created'),
				'friends_count': latest.get('friends_count'),
				'received_roses': latest.get('received_roses'),
				'sent_roses': latest.get('sent_roses'),
				'win_count': latest.get('win_count'),
				'lose_count': latest.get('lose_count'),
				'tie_count': latest.get('tie_count'),
				'play_time': latest.get('play_time'),
				'village_win_count': latest.get('village_win_count'),
				'village_lose_count': latest.get('village_lose_count'),
				'werewolf_win_count': latest.get('werewolf_win_count'),
				'werewolf_lose_count': latest.get('werewolf_lose_count'),
				'voting_win_count': latest.get('voting_win_count'),
				'voting_lose_count': latest.get('voting_lose_count'),
				'solo_win_count': latest.get('solo_win_count'),
				'solo_lose_count': latest.get('solo_lose_count'),
				'clan': latest.get('clan', {})
			})
		
		return {
			'targets': targets,
			'total': len(self.TARGETS),
			'page': page,
			'total_pages': self.total_pages
		}
