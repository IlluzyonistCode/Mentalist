import asyncio
import nest_asyncio
import threading
import ntplib
import pytz
import json
import os
import sys
import time
import random
import gc
from undetected_playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from collections import Counter
from itertools import combinations
from datetime import datetime
from tzlocal import get_localzone
from playsound3 import playsound
from colorama import Back, Fore, Style
from dotenv import dotenv_values
from pathlib import Path
from auth_decorator import require_module_auth
from auth_protection import _integrity_checker
from data_protection import save_encrypted, load_encrypted
from translations import is_discussion_phase, is_voting_phase, is_ui, ui_re
from utils import (
	USER_DATA_DIR,
	CONFIG_PATH,
	_pause,
	get_resource_path,
	find_chrome_executable,
	generate_random_user_agent,
	banner
)

class Booster:
	@require_module_auth('booster')
	def __init__(self):
		self.config = dotenv_values(CONFIG_PATH)
		self.is_valid = True

		self.CHROME_EXECUTABLE = find_chrome_executable()

		if not self.CHROME_EXECUTABLE:
			print(f'{Style.BRIGHT}{Back.RED}Booster Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			profile_number = int(self.config.get('CHROME_PROFILE', '1'))

			if profile_number < 1 or profile_number > 10:
				raise ValueError
		except (ValueError, TypeError):
			print(f'{Style.BRIGHT}{Back.RED}Booster Error: Chrome Profile must be a number between 1 and 10!{Back.RESET}')
			
			self.is_valid = False

			return

		self.CHROME_USER_DATA = USER_DATA_DIR / f'Mentalist_{profile_number}'
		
		os.makedirs(self.CHROME_USER_DATA, exist_ok=True)

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Booster Error: Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			print(f'{Style.BRIGHT}{Back.RED}Booster Error: Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.TIMEZONE = self.get_system_timezone()

		self.ntp = ntplib.NTPClient()
		self.NTP_SERVER = 'time.google.com'

		self.BEARER_TOKEN = None
		self.CF_JWT = None

		self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'
		self.BEARER_HEADERS = {}

		self.current_host = None

		self.VILLAGE_ROLES = {
			'villager', 'doctor', 'butcher', 'night-watchman', 'bodyguard', 'tough-guy',
			'seer-apprentice', 'seer', 'analyst', 'aura-seer', 'pumpkin-oracle',
			'spirit-seer', 'gambler', 'violinist', 'sheriff', 'detective', 'mortician',
			'ghost-lady', 'jailer', 'warden', 'vigilante', 'gunner', 'bully', 'witch',
			'pumpkin-dealer', 'forger', 'astronomer', 'beast-hunter', 'trapper',
			'flagger', 'priest', 'judge', 'marksman', 'nutcracker', 'snow-angel',
			'flower-child', 'pacifist', 'mayor', 'resolutionist', 'baker',
			'grumpy-grandma', 'preacher', 'loudmouth', 'bellringer', 'avenger',
			'admirer', 'cupid', 'instigator', 'medium', 'ritualist', 'conjuror',
			'soulbinder', 'ferryman', 'fortune-teller'
		}

		self.WW_ROLES = {
			'werewolf', 'junior-werewolf', 'yule-wolf', 'candy-wolf', 'wolffluencer',
			'nightmare-werewolf', 'swamp-wolf', 'voodoo-werewolf', 'wolf-trickster',
			'storm-wolf', 'wolf-shaman', 'wolf-scribe', 'confusion-wolf', 'wolf-pacifist',
			'guardian-wolf', 'jelly-wolf', 'shadow-wolf', 'werewolf-berserk', 'toxic-wolf',
			'alpha-werewolf', 'ghost-wolf', 'stubborn-werewolf', 'wolf-summoner',
			'wolf-seer', 'blind-werewolf', 'random-werewolf'
		}

		self.SOLO_ROLES = {
			'serial-killer', 'headless-horseman', 'evil-detective', 'cannibal',
			'arsonist', 'alchemist', 'bomber', 'corruptor', 'illusionist',
			'sect-leader', 'siren', 'blight', 'shapeshifter',
			'evil-santa', 'evil-cupid', 'random-killer'
		}

		self.RV_ROLES = {
			'headhunter', 'fool', 'anarchist'
		}

		self.NOT_ALLOWED_ROLES = {
			'accomplice', 'bandit', 'cursed-human', 'cursed', 'easter-bunny', 'fortune-teller',
			'grave-robber', 'harlot', 'kitten-wolf', 'lurker', 'party-wolf', 'prayer',
			'president', 'pumpkin-king', 'red-lady', 'random-all', 'random-voting',
			'santa', 'sorcerer', 'watchdog', 'werewolf-fan', 'zombie',
			'assassin'
		}

		self.KILLING_ROLES = {
			'astronomer', 'avenger', 'beast-hunter', 'bully', 'flagger', 'forger',
			'gunner', 'jailer', 'judge', 'marksman', 'nutcracker', 'priest',
			'pumpkin-dealer', 'trapper', 'vigilante', 'warden', 'witch'
		}

		self.PROTECTING_ROLES = {
			'bodyguard', 'butcher', 'doctor', 'ghost-lady', 'night-watchman',
			'seer-apprentice', 'snow-angel', 'tough-guy',
			'witch', 'pumpkin-dealer', 'forger', 'astronomer'
		}

		self.INVESTIGATIVE_ROLES = {
			'analyst', 'aura-seer', 'detective', 'gambler', 'mortician',
			'pumpkin-oracle', 'seer', 'sheriff', 'spirit-seer', 'violinist'
		}

		self.KILLING_MAX = 2
		self.PROTECTING_MAX = 2
		self.INVESTIGATIVE_MAX = 2
		self.WW_MIN = 4

		self.ROLE_MAX_COUNT = {
			'villager': 3,
			'aura-seer': 2,
			'blind-werewolf': 2,
			'detective': 2,
			'flower-child': 2,
			'gambler': 2,
			'guardian-wolf': 2,
			'jelly-wolf': 2,
			'mortician': 2,
			'nightmare-werewolf': 2,
			'pacifist': 2,
			'pumpkin-oracle': 2,
			'shadow-wolf': 2,
			'sheriff': 2,
			'spirit-seer': 2,
			'storm-wolf': 2,
			'swamp-wolf': 2,
			'toxic-wolf': 2,
			'violinist': 2,
			'voodoo-werewolf': 2,
			'wolf-pacifist': 2,
			'wolf-seer': 2
		}

		self.context = None
		self.page = None
		self.player_name = None

		self.is_host = False
		self.day_signal_sent = False
		self.reload_count = 0
		self.session_start = time.monotonic()

		self.guest_mode = False
		self._guest_mode_changed = False

		self.headless_mode = False
		self._headless_mode_changed = False

		self._cached_configs = None

		self.last_role_name = None

		self.stats = {
			'gamesPlayed': 0,
			'villagerGames': 0,
			'werewolfGames': 0,
			'soloGames': 0
		}

		self.load_hosts()

	@staticmethod
	def get_system_timezone():
		try:
			sys_tz = get_localzone()

			return pytz.timezone(str(sys_tz))
		except:
			_pause(f'\n{Style.BRIGHT}{Back.RED}Could not detect local timezone. Defaulting to UTC.')

			return pytz.utc

	def get_ntp_timestamp(self):
		try:
			data = self.ntp.request(self.NTP_SERVER, version=3)

			return data.tx_time
		except:
			return

	def push_stats(self, stats_dict):
		pass

	def set_guest_mode(self, enabled):
		if self.guest_mode == enabled:
			return

		self.guest_mode = enabled
		self._guest_mode_changed = True

		state = 'enabled' if enabled else 'disabled'

		self.log_message('cyan', f'Guest mode {state}')

	def check_guest_mode_changed(self):
		if self._guest_mode_changed:
			self._guest_mode_changed = False

			return True

		return False

	def set_headless_mode(self, enabled):
		if self.headless_mode == enabled:
			return

		self.headless_mode = enabled
		self._headless_mode_changed = True

		state = 'enabled' if enabled else 'disabled'

		self.log_message('cyan', f'Headless mode {state}')

	def check_headless_mode_changed(self):
		if self._headless_mode_changed:
			self._headless_mode_changed = False

			return True

		return False

	def load_hosts(self):
		self.HOSTS = load_encrypted('hosts') or {}

	def save_hosts(self):
		save_encrypted('hosts', self.HOSTS)

	def check_guest_mode(self):
		return self.guest_mode

	def check_stop_flag(self):
		if hasattr(self, '_stop_event'):
			return self._stop_event.is_set()

		try:
			from mentalist_gui import stop_flags

			return stop_flags.get('booster', threading.Event()).is_set()
		except:
			return False

	def _is_phantom(self):
		try:
			return _integrity_checker.get_corruption_handler().is_phantom_mode()
		except:
			return False

	def _phantom_act(self, label='action'):
		if not self._is_phantom():
			return True

		self.log_message('info', f'Processing {label}...')

		time.sleep(random.uniform(30.0, 120.0))

		if random.random() < 0.5:
			time.sleep(random.uniform(20.0, 80.0))

		return random.random() > 0.55

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

		self.auth_client.update_tokens(
			bearer_token=self.BEARER_TOKEN,
			refresh_token=self.REFRESH_TOKEN
		)

	def ensure_english_language(self):
		for n in range(2, 6):
			try:
				flag_xpath = f'/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[3]/div/div/div/div/div/img'
				flag_img = self.page.locator(f'xpath={flag_xpath}').first
				flag_img.wait_for(state='visible', timeout=1000)

				src = flag_img.get_attribute('src', timeout=2000) or ''

				if 'flag_en' in src:
					return

				self.log_message('warning', f'Non-English language detected, switching...')

				flag_img.click(timeout=5000)

				time.sleep(0.5)

				dropdown_xpath = f'/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[3]/div[2]/div[2]/div/div/div'
				dropdown = self.page.locator(f'xpath={dropdown_xpath}').first
				dropdown.wait_for(state='visible', timeout=3000)

				english_option = dropdown.get_by_text('English', exact=True).first
				english_option.click(timeout=5000)

				time.sleep(0.5)

				self.log_message('success', 'Language switched to English!')

				return
			except PlaywrightTimeoutError:
				continue

		self.log_message('warning', 'Language flag element not found, skipping check...')

	def is_host_blocked(self, host):
		if not host or host not in self.HOSTS:
			return False

		entry = self.HOSTS[host]
		blocked_until = entry.get('blocked_until')

		if not blocked_until:
			return False

		now = self.get_ntp_timestamp()

		if now is None:
			self.log_message('warning', 'NTP unavailable, skipping block check...')

			return False

		if now < blocked_until:
			remaining_days = (blocked_until - now) / 86400

			self.log_message('warning', f'Host "{host}" is blocked for {remaining_days:.1f} more days, skipping...')
			
			return True

		del self.HOSTS[host]

		self.save_hosts()

		self.log_message('info', f'Host "{host}" block expired, allowing...')

		return False

	def record_game_result(self, host, was_werewolf, role=None):
		role_id = (role or '').lower().replace(' ', '-').replace('_', '-')
		was_rv = role_id in self.RV_ROLES
		was_solo = role_id in self.SOLO_ROLES

		self.stats['gamesPlayed'] += 1

		if was_werewolf:
			self.stats['werewolfGames'] += 1

		elif was_solo or was_rv:
			self.stats['soloGames'] += 1

		else:
			self.stats['villagerGames'] += 1

		self.push_stats(dict(self.stats))

		if not host:
			return

		if was_werewolf or was_rv:
			if host not in self.HOSTS:
				self.HOSTS[host] = {'streak': 0}

			self.HOSTS[host]['streak'] = self.HOSTS[host].get('streak', 0) + 1

			streak = self.HOSTS[host]['streak']

			if streak >= 5:
				now = self.get_ntp_timestamp()

				if now is not None:
					self.HOSTS[host] = {'blocked_until': now + 7 * 86400}

					self.log_message('error', f'Host "{host}" blocked for 7 days (streak {streak})!')

		else:
			if host in self.HOSTS:
				del self.HOSTS[host]

		self.save_hosts()

	def find_suitable_room(self):
		if self.check_stop_flag():
			return None, None, False

		self.log_message('info', 'Scanning rooms...')

		try:
			rooms_container = None
			active_xpath = None

			ROOMS_XPATHS = [
				'//div/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div',
				'//div/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div',
			]

			for n in range(2, 8):
				for xpath_tpl in ROOMS_XPATHS:
					try:
						candidate = self.page.locator(f'xpath={xpath_tpl.format(n=n)}').first

						if not candidate.is_visible(timeout=500):
							continue

						count = candidate.evaluate('(el) => el.children.length', timeout=500)

						if count < 1:
							continue

						rooms_container = candidate

						break
					except:
						continue

				if rooms_container:
					active_xpath = rooms_container.evaluate('''
						(el) => {
							let path = '';
							let node = el;

							while (node && node.nodeType === Node.ELEMENT_NODE) {
								let index = 1;
								let sibling = node.previousElementSibling;

								while (sibling) {
									if (sibling.tagName === node.tagName) index++;
									sibling = sibling.previousElementSibling;
								}

								path = '/' + node.tagName.toLowerCase() + (index > 1 ? `[${index}]` : '') + path;
								node = node.parentElement;
							}

							return path;
						}
					''', timeout=500)

					break

			if not rooms_container:
				self.log_message('error', 'Rooms menu is empty')

				return None, None, True

			room_count = rooms_container.evaluate('(container) => container.children.length;', timeout=5000)

			self.log_message('cyan', f'Found {room_count} rooms')

			for i in range(1, room_count + 1):
				if self.check_stop_flag():
					return None, None, False

				try:
					room_base = f'{active_xpath}/div[{i}]/div/div/div[1]'

					room_name_locator = self.page.locator(f'xpath={room_base}/div[2]/div[1]')
					room_name = room_name_locator.text_content(timeout=500).lower()

					if ('vill win' not in room_name \
						and 'ᴠɪʟʟ ᴡɪɴ' not in room_name) \
						or 'bqt' in room_name:
						continue

					player_count_locator = self.page.locator(f'xpath={room_base}/div[5]')
					player_count_text = player_count_locator.text_content(timeout=500)

					if not player_count_text.isdigit():
						continue

					player_count = int(player_count_text)

					if player_count > 6:
						continue

					xp_icon_locator = self.page.locator(f'xpath={room_base}/div[3]/img')

					if not xp_icon_locator.is_visible(timeout=500):
						continue

					try:
						lock_locator = self.page.locator(f'xpath={room_base}/div[1]')

						style = lock_locator.get_attribute('style', timeout=500) or ''

						if 'color: rgb(255, 255, 255)' in style:
							continue
					except PlaywrightTimeoutError:
						pass

					self.log_message('success', f'Found suitable room: {room_name} ({player_count}/8)')

					host_locator = self.page.locator(f'xpath={room_base}/div[2]/div[2]')
					host = host_locator.text_content(timeout=500).strip()

					if self.is_host_blocked(host):
						continue

					self.current_host = host

					return i, active_xpath, False
				except PlaywrightTimeoutError as e:
					continue
		except Exception as e:
			if 'strict mode violation' in str(e):
				self.log_message('error', 'Multiple room containers detected, using first')

			else:
				self.log_message('error', f'Error scanning rooms: {str(e)[:100]}')

		return None, None, False

	def join_room(self, room_index, active_xpath):
		if self.check_stop_flag():
			return False

		if not self._phantom_act('join'):
			return False

		try:
			self.log_message('info', f'Joining room #{room_index}...')

			room_xpath = f'{active_xpath}/div[{room_index}]/div/div'
			room_locator = None

			try:
				candidate = self.page.locator(f'xpath={room_xpath}').first
				candidate.wait_for(state='visible', timeout=3000)

				room_locator = candidate
			except PlaywrightTimeoutError:
				self.log_message('error', 'Could not find room to join')

				return False

			room_locator.click(timeout=5000)

			time.sleep(0.5)

			for n in range(4, 8):
				try:
					cancel_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[1]/div').first
					
					button_text = cancel_button.text_content(timeout=500)

					if is_ui(button_text, 'cancel') or button_text.strip() == '':
						join_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[2]/div/div').first
						
						button_text = join_button.text_content(timeout=500)
	
						if is_ui(button_text, 'join'):
							break

						self.log_message('warning', 'Unexpected modal after clicking room (password?), cancelling...')

						cancel_button.click()

						time.sleep(1)

						return False
				except PlaywrightTimeoutError:
					continue

			join_button = None

			for n in range(4, 8):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[2]/div/div').first

					button_text = candidate.text_content(timeout=500)

					if is_ui(button_text, 'join'):
						join_button = candidate

						break
				except PlaywrightTimeoutError:
					continue

			if not join_button:
				self.log_message('warning', 'Join button not found, closing modal and retrying...')

				for n in range(4, 8):
					try:
						cancel_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[1]/div').first

						button_text = cancel_button.text_content(timeout=500)

						if is_ui(button_text, 'cancel') or button_text == '':
							cancel_button.click()

							break
					except PlaywrightTimeoutError:
						continue

				time.sleep(1)

				return False

			join_button.click(timeout=5000)

			time.sleep(1)

			for n in range(4, 8):
				try:
					cancel_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[1]/div').first
					ok_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div/div/div').first

					if cancel_button.is_visible(timeout=500):
						button_text = cancel_button.text_content(timeout=500)

						if is_ui(button_text, 'cancel'):
							self.log_message('warning', 'Game locked with password, retrying...')

							cancel_button.click()

							time.sleep(1)

							return False

					if ok_button.is_visible(timeout=500):
						button_text = ok_button.text_content(timeout=500)

						if is_ui(button_text, 'ok'):
							self.log_message('warning', 'Game already started, retrying...')

							ok_button.click()

							time.sleep(1)

							return False
				except PlaywrightTimeoutError:
					continue

			self.log_message('success', 'Successfully joined room!')

			time.sleep(1)

			return True
		except Exception as e:
			self.log_message('error', f'Failed to join room: {str(e)[:100]}')

			return False

	def refresh_rooms(self):
		if self.check_stop_flag():
			return

		try:
			refresh_button = None

			for n in range(2, 5):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[2]/div[2]').get_by_text(ui_re('refresh')).first

					if candidate.is_visible(timeout=1000):
						refresh_button = candidate

						break
				except PlaywrightTimeoutError:
					continue

			if not refresh_button:
				refresh_button = self.page.get_by_text(ui_re('refresh')).first

			refresh_button.click(timeout=5000)

			time.sleep(1)

			self.log_message('cyan', 'Refreshed room list')
		except Exception as e:
			self.log_message('error', f'Failed to refresh: {str(e)[:100]}')

	def reload_page(self):
		self.reload_count += 1

		if self.reload_count % 3 == 0:
			self.log_message('warning', 'Hard reloading session...')

			for page in self.context.pages:
				page.close()

			gc.collect()

			self.page = self.context.new_page()

			self.page.goto('https://wolvesville.com', wait_until='domcontentloaded', timeout=120000)
			self.page.wait_for_load_state('networkidle', timeout=30000)

		else:
			self.log_message('warning', 'Reloading page...')

			self.page.reload(wait_until='domcontentloaded', timeout=120000)
			self.page.wait_for_load_state('networkidle', timeout=30000)

		self.log_message('success', 'Page reloaded, continuing...')

	def rebuild_session(self):
		for page in self.context.pages:
			page.close()

		gc.collect()

		self.page = self.context.new_page()

		self.page.goto('https://wolvesville.com', wait_until='domcontentloaded', timeout=120000)
		self.page.wait_for_load_state('networkidle', timeout=30000)

		return True

	def auto_find_and_join(self):
		self.is_host = False

		empty_count = 0

		while True:
			if self.check_stop_flag():
				return False

			if self.check_guest_mode_changed():
				self.log_message('cyan', 'Guest mode changed — reloading to switch mode')
				self.reload_page()

				return False

			room_index, active_xpath, is_empty = self.find_suitable_room()

			if room_index:
				empty_count = 0

				if self.join_room(room_index, active_xpath):
					return True

				self.refresh_rooms()

			else:
				self.log_message('warning', 'No suitable rooms found, refreshing...')

				if is_empty:
					empty_count += 1
				
				else:
					empty_count = 0

				if empty_count >= 5:
					self.log_message('warning', 'Rooms menu empty too many times, reloading...')

					self.reload_page()

					empty_count = 0

					return False

				self.refresh_rooms()

	def get_role_name_from_icon(self, icon):
		try:
			if 'icon_' not in icon:
				return
				
			role = icon.split('icon_')[1].split('_filled')[0]
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

			role = role.replace('-', ' ').title()
			
			return role
		except Exception as e:
			self.log_message('error', f'Error extracting role name: {e}')

	def get_article(self, word):
		if not word:
			return 'a'
		
		vowels = ['a', 'e', 'i', 'o', 'u']
		first_letter = word[0].lower()
		
		return 'an' if first_letter in vowels else 'a'

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

	def find_players(self, players_grid_xpath):
		container = self.page.locator(f'xpath={players_grid_xpath}').first

		return container.evaluate('''
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

						const images = cell.getElementsByTagName('img');
						const icons = [];

						for (const img of images) icons.push(img.src);

						const isSelf = cell.querySelectorAll('div[style*="rgb(236, 64, 122)"]').length > 0;

						results.push({
							i: i + 1,
							j: j + 1,
							name: name,
							icons: icons,
							is_self: isSelf
						});
					}
				}

				return results;
			}
		''')

	def get_players_info_villager(self):
		players = []
		couples = []
		werewolf_couples = []
		self_number = None
		role = None
		role_name = None

		players_grid_xpath = self.find_players_grid_xpath()

		if not players_grid_xpath:
			return players, couples, werewolf_couples, self_number, role

		try:
			players_data = self.find_players(players_grid_xpath)
		except Exception as e:
			self.log_message('error', f'Failed to find players: {str(e)[:100]}')
			
			return players, couples, werewolf_couples, self_number, role

		for data in players_data:
			i, j = data['i'], data['j']
			name = data['name']
			icons = data['icons']
			is_self_flag = data['is_self']

			player_cell_locator = self.page.locator(f'xpath={players_grid_xpath}/div[{i}]/div[{j}]/div')
			player_number = 4 * (i - 1) + j

			player = {
				'locator': player_cell_locator,
				'name': name,
				'self': False,
				'number': player_number
			}

			is_werewolf = False

			if not self.player_name and is_self_flag:
				self.player_name = name

				self.log_message('cyan', f'Detected player name: {self.player_name}')

			if self.player_name and name == self.player_name:
				player['self'] = True
				self_number = player_number

				for icon in icons:
					if 'priest' in icon:
						role = 'priest'

					elif 'vigilante' in icon:
						role = 'vigilante'

					elif 'gunner' in icon:
						role = 'gunner'

					if player['self'] and 'icon_' in icon and role_name is None:
						extracted_role = self.get_role_name_from_icon(icon)

						if extracted_role:
							role_name = extracted_role
							article = self.get_article(role_name)
							
							self.last_role_name = role_name

							self.log_message('success', f'You are {article} {role_name}!')

			for icon in icons:
				if 'wolf' in icon:
					is_werewolf = True

			for icon in icons:
				if 'lovers' in icon:
					if not player['self'] and player_number not in couples:
						couples.append(player_number)

						if is_werewolf:
							werewolf_couples.append(player_number)

			players.append(player)

		return players, couples, werewolf_couples, self_number, role

	def get_players_info_werewolf(self):
		players = []
		couples = []
		werewolf_numbers = []
		self_number = None
		role = None
		role_name = None
		has_junior_werewolf = False
		vote = False
		tag = False

		players_grid_xpath = self.find_players_grid_xpath()

		if not players_grid_xpath:
			return players, couples, werewolf_numbers, self_number, role, vote, tag

		try:
			players_data = self.find_players(players_grid_xpath)
		except Exception as e:
			self.log_message('error', f'Failed to find players: {str(e)[:100]}')
			
			return players, couples, werewolf_numbers, self_number, role, vote, tag

		for data in players_data:
			i, j = data['i'], data['j']
			name = data['name']
			icons = data['icons']
			is_self_flag = data['is_self']

			player_cell_locator = self.page.locator(f'xpath={players_grid_xpath}/div[{i}]/div[{j}]/div')
			player_number = 4 * (i - 1) + j

			player = {
				'locator': player_cell_locator,
				'name': name,
				'self': False,
				'number': player_number
			}

			is_werewolf = False

			if not self.player_name and is_self_flag:
				self.player_name = name

				self.log_message('cyan', f'Detected player name: {self.player_name}')

			if self.player_name and name == self.player_name:
				player['self'] = True
				self_number = player_number
				is_werewolf = True

				werewolf_numbers.append(player_number)

			for icon in icons:
				if not player['self'] and 'wolf' in icon:
					is_werewolf = True
					
					werewolf_numbers.append(player_number)

				if 'junior' in icon or 'split' in icon:
					if player['self']:
						tag = True
						role = 'junior_werewolf'

					else:
						has_junior_werewolf = True

				elif ('wolf_seer' in icon or 'wolfseer' in icon) and player['self']:
					role = 'wolf_seer'

				elif 'lovers' in icon:
					if not is_werewolf and player_number not in couples:
						couples.append(player_number)

				if player['self'] and 'icon_' in icon and role_name is None:
					extracted_role = self.get_role_name_from_icon(icon)

					if extracted_role:
						role_name = extracted_role
						article = self.get_article(role_name)

						self.last_role_name = role_name

						self.log_message('error', f'You are {article} {role_name}!')

			players.append(player)

		couples = [c for c in couples if c not in werewolf_numbers]

		NO_VOTE_ROLES = ('wolf_seer', 'blind_werewolf', 'sorcerer')

		if couples and role not in NO_VOTE_ROLES and not has_junior_werewolf:
			vote = True

		return players, couples, werewolf_numbers, self_number, role, vote, tag

	def analyze_day_chat(self, self_number):
		try:
			chat = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div/div').first
					candidate.wait_for(state='visible', timeout=1000)

					chat = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not chat:
				return

			if not hasattr(self, 'last_day_message_index'):
				self.last_day_message_index = 0

			result = chat.evaluate('''
				(chat, lastIndex) => {
					let messages = [];
					const blocks = chat.getElementsByTagName("div");
					
					for (block of blocks) {
						const text = block.textContent;

						if (text && !messages.includes(text)) messages.push(text);
					}
					
					let newMessages = [];

					for (let i = lastIndex; i < messages.length; i++)
						newMessages.push(messages[i]);
					
					return [newMessages, messages.length];
				}
			''', self.last_day_message_index)

			new_messages, total_count = result

			self.last_day_message_index = total_count

			for message in new_messages:
				if ': ' not in message:
					continue

				player, message = message.split(': ', 1)
				
				try:
					number, name = player.split(' ', 1)
					number = int(number)
				except (ValueError, IndexError):
					continue

				if number == self_number:
					continue

				message_lower = message.lower().strip()

				if message_lower in ['m', 'me', 'wc']:
					self.log_message('warning', f'Suspicious message from player {number}: "{message}"')
					
					return number

				words = message.split()

				for word in words:
					if word.isdigit() and 1 <= int(word) <= 16:
						self.log_message('warning', f'Player {number} mentioned number {int(word)}')
						
						return int(word)
		except Exception as e:
			self.log_message('error', f'Error analyzing chat: {str(e)[:100]}')
		
	def analyze_night_chat(self, self_number, couples):
		try:
			chat = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[1]/div/div/div').first
					candidate.wait_for(state='visible', timeout=1000)
					
					chat = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not chat:
				return

			messages = chat.evaluate('''
				(chat) => {
					let messages = [];

					const blocks = chat.getElementsByTagName("div");

					for (block of blocks) {
						const text = block.textContent;

						if (text && !messages.includes(text)) messages.push(text);
					}

					return messages;
				}
			''')

			for message in messages:
				if ': ' not in message:
					continue

				player, message = message.split(': ')
				number, player = player.split(' ')
				message = ''.join(message)

				number = int(number)

				if number == self_number or number in couples:
					continue

				words = message.split(' ')

				for word in words:
					if word.isdigit() and 1 <= int(word) <= 16:
						return int(word)
		except Exception as e:
			self.log_message('error', f'Error analyzing night chat: {str(e)[:100]}')

	def wait_for_voting_phase(self):
		self.log_message('info', 'Waiting for voting phase...')
		
		phase_locator = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
				candidate.wait_for(state='visible', timeout=1000)

				phase_locator = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not phase_locator:
			self.log_message('warning', 'Phase locator not found')

			return False

		discussion_started = False
		voting_started = False
		empty_text_counter = 0
		
		for _ in range(30):
			if self.check_stop_flag():
				return False
			
			time.sleep(1.5)

			try:
				phase_text = phase_locator.text_content(timeout=1000)

				if phase_text == '':
					empty_text_counter += 1

					if empty_text_counter == 5:
						self.log_message('warning', 'Game ended during night phase')

						return False

					continue

				empty_text_counter = 0

				if is_voting_phase(phase_text):
					self.log_message('success', 'Voting phase started!')

					voting_started = True

					break

				if is_discussion_phase(phase_text):
					self.log_message('info', 'Discussion phase started')

					discussion_started = True

					break
			except PlaywrightTimeoutError:
				pass

		if voting_started:
			return True

		if not discussion_started:
			self.log_message('warning', 'Neither discussion nor voting phase detected after 30 seconds')
			
			return False

		self.log_message('info', 'Waiting for discussion to end...')

		empty_text_counter = 0
		
		for _ in range(30):
			if self.check_stop_flag():
				return False

			time.sleep(1.5)
			
			try:
				phase_text = phase_locator.text_content(timeout=1000)

				if phase_text == '':
					empty_text_counter += 1

					if empty_text_counter == 5:
						self.log_message('warning', 'Game ended during discussion phase')

						return False

					continue

				empty_text_counter = 0

				if is_voting_phase(phase_text):
					self.log_message('success', 'Voting phase started!')

					return True
			except PlaywrightTimeoutError:
				pass

		self.log_message('warning', 'Voting phase not detected after discussion')

		return False

	def use_ability_on_target(self, players, target_number, ability_name):
		self.log_message('info', f'Using {ability_name} on player {target_number}...')

		if not self._phantom_act('ability'):
			return
		
		icon_src_map = {
			'holy water': 'priest_holy_water',
			'bullet': 'gunner_bullet'
		}

		expected_src = icon_src_map.get(ability_name)

		try:
			ability_icon = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div[1]/img')
					candidate.wait_for(state='visible', timeout=500)

					if expected_src:
						src = candidate.get_attribute('src', timeout=500) or ''

						if expected_src not in src:
							self.log_message('warning', f'Ability icon mismatch, skipping...')
							
							return

					ability_icon = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not ability_icon:
				self.log_message('error', 'Ability icon not found')

				return

			ability_icon.click(timeout=5000)

			time.sleep(0.1)

			target_player = next((p for p in players if p['number'] == target_number), None)

			if target_player:
				target_player['locator'].click(timeout=5000)

				self.log_message('success', f'{ability_name.capitalize()} used on player {target_number}!')
		except Exception as e:
			self.log_message('error', f'Failed to use {ability_name}: {str(e)[:50]}')

	def act_villager(self):
		self.log_message('info', 'Finding players...')

		players, couples, werewolf_couples, self_number, role = self.get_players_info_villager()

		self.log_message('success', 'Players found!')

		if role not in ['priest', 'vigilante', 'gunner']:
			self.log_message('cyan', 'No action required')

			return

		if not self.wait_for_voting_phase():
			return

		target_number = None

		if role == 'priest' and werewolf_couples:
			self.log_message('warning', 'Priest with werewolf couple - shooting random player')
			
			available_targets = [p['number'] for p in players if p['number'] != self_number and p['number'] not in couples]
			
			if available_targets:
				target_number = random.choice(available_targets)
				
				self.log_message('info', f'Selected random target: player {target_number}')

		else:
			self.log_message('info', 'Analyzing day chat...')

			while target_number is None:
				if self.check_stop_flag():
					return

				game_ended = False

				for n in range(2, 6):
					try:
						end_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div').get_by_text(ui_re('continue')).first

						if end_button.is_visible(timeout=200):
							self.log_message('warning', 'Game ended during chat analysis, exiting...')
							
							game_ended = True

							break
					except PlaywrightTimeoutError:
						continue

				if game_ended:
					return

				time.sleep(2)

				potential_target = self.analyze_day_chat(self_number)
				
				if potential_target:
					if potential_target in couples:
						continue
					
					target_number = potential_target
					
					break

		if not target_number:
			self.log_message('error', 'Target player not found')
			
			return

		if role == 'priest':
			self.use_ability_on_target(players, target_number, 'holy water')

		elif role == 'vigilante':
			self.use_ability_on_target(players, target_number, 'bullet')

		elif role == 'gunner':
			self.use_ability_on_target(players, target_number, 'bullet')

	def send_day_chat_signal(self, couples, werewolf_numbers):
		if self.day_signal_sent:
			return

		try:
			is_couple_wolf = any(c in werewolf_numbers for c in couples)
			message = 'WC' if is_couple_wolf else 'Me'

			textarea = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[2]/div/textarea')
					candidate.wait_for(state='visible', timeout=500)

					textarea = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not textarea:
				self.log_message('warning', 'Day chat textarea not found for signal')

				return

			self.log_message('info', f'Sending day signal: {message}')

			textarea.fill(message)
			textarea.press('Enter')

			self.day_signal_sent = True

			self.log_message('success', f'Day signal sent: {message}')
		except Exception as e:
			self.log_message('error', f'Failed to send day signal: {str(e)[:50]}')

	def wait_for_day_phase(self):
		self.log_message('info', 'Waiting for day phase...')

		phase_locator = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
				candidate.wait_for(state='visible', timeout=1000)

				phase_locator = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not phase_locator:
			self.log_message('warning', 'Phase locator not found for day phase wait')

			return False

		empty_text_counter = 0

		for _ in range(60):
			if self.check_stop_flag():
				return False

			time.sleep(1.5)

			try:
				phase_text = phase_locator.text_content(timeout=1000)

				if phase_text == '':
					empty_text_counter += 1

					if empty_text_counter >= 5:
						self.log_message('warning', 'Game ended while waiting for day phase')

						return False

					continue

				empty_text_counter = 0

				if is_discussion_phase(phase_text) or is_voting_phase(phase_text):
					self.log_message('success', 'Day phase detected!')

					return True
			except PlaywrightTimeoutError:
				pass

		self.log_message('warning', 'Day phase not detected after 90 seconds')

		return False

	def act_werewolf(self):
		self.log_message('info', 'Finding players...')

		start_time = time.monotonic()

		players, couples, werewolf_numbers, self_number, role, vote, tag = self.get_players_info_werewolf()

		self.log_message('success', 'Players found!')

		if couples:
			self.send_couples_message(couples)

		if tag:
			self.tag_target(players, self_number, couples, werewolf_numbers, start_time)

		if vote and couples:
			self.vote_for_couple(players, couples, start_time)

		if not self.wait_for_day_phase():
			return

		if couples:
			self.send_day_chat_signal(couples, werewolf_numbers)

	def send_couples_message(self, couples):
		if not self._phantom_act('message'):
			return

		textarea = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[2]/div/textarea')
				candidate.wait_for(state='visible', timeout=500)

				textarea = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not textarea:
			self.log_message('error', 'Chat textarea not found')

			return

		self.log_message('info', 'Sending message...')

		TEMPLATES = [
			'Mine is {couples} 🔥 Show me yours daddy',
			'{couples} gonna get it tonight 😈 wbu cutie?',
			'Dibs on {couples} 💋 Your turn babe',
			'Me + {couples} = magic ✨ Spill yours',
			'{couples} looking real snackable rn 🍑 Who\'s your snack?',
			'Claimed {couples} 😏 Don\'t leave me hanging',
			'{couples} bout to have a wild night 🌙 Who\'s yours?',
			'Got {couples} on speed dial 📞💕 Your couple?',
			'My {couples} hits different 💎 Share yours?',
			'{couples} and I got plans 😘 What about you?',
			'Locked down {couples} 🔐 Your move',
			'{couples} is mine don\'t @ me 💅 Who\'s keeping you busy?',
			'Manifested {couples} 🕯️✨ Who manifested you?',
			'{couples} got that rizz 😮‍💨 Show yours',
			'My little secret: {couples} 🤫 Now you',
			'{couples} different breed fr 💯 Yours?',
			'Me & {couples} no cap 🧢 Your couple tho?',
			'{couples} just built different 🏆 Who you got?',
			'Vibing with {couples} rn 🎵 Your vibe check?',
			'{couples} is the one ❤️‍🔥 Spill the tea',
			'Got {couples} in my corner 👑 Your royalty?',
			'{couples} living rent free in my head 🧠💕 Yours?',
			'My {couples} unmatched 💪 Let\'s see yours',
			'{couples} certified banger 🎯 Show me whatchu got',
			'Invested in {couples} stocks 📈 Your portfolio?',
			'{couples} lowkey fire 🔥 Don\'t be shy',
			'Me x {couples} main character energy ⭐ You?',
			'{couples} the whole package 📦💝 Unwrap yours',
			'My duo is {couples} 🎮 Your player 2?',
			'{couples} no thoughts just vibes ☁️ Yours?',
			'Riding with {couples} 🏍️💨 Who you riding with?',
			'{couples} pass the vibe check ✅ Your turn',
			'Got {couples} on my mind 💭🔥 Who\'s on yours?',
			'{couples} making moves 💃 Show your dance partner',
			'My {couples} slaps 👋💥 Yours slap too?',
			'{couples} chef\'s kiss 👨‍🍳💋 Taste test yours?',
			'Simping for {couples} 😩💕 Who you simping for?',
			'{couples} immaculate vibes only 🌊 Your wave?',
			'My {couples} elite tier 🎖️ Rank yours',
			'{couples} living the dream 😴💫 Your dreams?',
			'Obsessed with {couples} ngl 🤷‍♀️❤️ Your obsession?',
			'{couples} hits the spot 🎯💘 Your bullseye?',
			'My {couples} premium quality 💎✨ Standard or premium?',
			'{couples} the blueprint 📐 Your design?',
			'Bonded with {couples} 🔗 Your connection?',
			'{couples} straight bussin 😤🔥 Yours bussin too?',
			'My {couples} S-tier 🏅 What tier is yours?',
			'{couples} just different energy ⚡ Match my energy',
			'Stuck on {couples} like glue 🍯 Who you stuck on?',
			'{couples} got me acting up 😳💕 Who got you?'
		]

		couples_text = ' & '.join([str(couple) for couple in couples]) if len(couples) > 1 else str(couples[0])
		
		message = random.choice(TEMPLATES).format(couples=couples_text)

		textarea.fill(message)
		textarea.press('Enter')

		self.log_message('success', 'Message sent!')

	def vote_for_couple(self, players, couples, start_time=None):
		self.log_message('info', 'Voting couple...')

		if not self._phantom_act('vote'):
			return

		if start_time is not None:
			remaining_time = 30 - (time.monotonic() - start_time)

			if remaining_time >= 15:
				time.sleep(remaining_time - 15)

		try:
			target_number = couples[0]
			target_player = next((p for p in players if p['number'] == target_number), None)

			if target_player:
				target_player['locator'].click(timeout=10000)

			else:
				players[target_number - 1]['locator'].click(timeout=10000)

			self.log_message('success', 'Couple voted!')
		except Exception as e:
			self.log_message('error', f'Vote failed: {str(e)[:50]}')

	def tag_target(self, players, self_number, couples, werewolf_numbers, start_time):
		self.log_message('info', 'Finding target...')

		if not self._phantom_act('tag'):
			return

		remaining_time = 30 - (time.monotonic() - start_time)

		if remaining_time >= 10:
			time.sleep(remaining_time - 10)

		target = self.analyze_night_chat(self_number, couples)

		if not target:
			self.log_message('warning', 'Target not found!')

			return

		if target in couples + werewolf_numbers:
			return

		self.log_message('success', 'Target found!')
		self.log_message('info', 'Tagging player...')

		try:
			tag_icon = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div/img')
					candidate.wait_for(state='visible', timeout=200)

					tag_icon = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not tag_icon:
				self.log_message('error', 'Tag icon not found')

				return

			tag_icon.click(timeout=5000)

			time.sleep(1)

			players[target - 1]['locator'].click(timeout=5000)

			self.log_message('success', 'Player tagged!')
		except Exception as e:
			self.log_message('error', f'Tag failed: {str(e)[:50]}')

	def send_end_message(self):
		try:
			textarea = None

			for n in range(2, 6):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div[2]/div/div/div/div/div[1]/div[1]/div[2]/div[1]/div/div/div/div[3]/div[2]/div/div/textarea')
					candidate.wait_for(state='visible', timeout=500)

					textarea = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not textarea:
				return

			textarea.fill('GG :)')
			textarea.press('Enter')

			time.sleep(1)
		except Exception as e:
			self.log_message('error', f'Failed to send end message: {str(e)[:50]}')
	
	def leave_room(self):
		self.log_message('info', 'Leaving room...')

		try:
			back_button = None

			for n in range(2, 6):
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div/div/div[1]/div[1]/div[1]/div[1]/div[1]/div/div').first

				try:
					candidate.wait_for(state='visible', timeout=500)
					
					back_button = candidate

					break
				except PlaywrightTimeoutError:
					continue

			if not back_button:
				self.log_message('error', 'Back button not found')

				return False

			back_button.click(timeout=5000)

			confirm_button = None

			for n in range(4, 8):
				try:
					candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[2]/div/div').first

					button_text = candidate.text_content(timeout=500)

					if button_text is not None:
						confirm_button = candidate

						break
				except PlaywrightTimeoutError:
					continue

			if not confirm_button:
				self.log_message('error', 'Confirm button not found')

				return False

			confirm_button.click(timeout=5000)

			time.sleep(1)

			self.log_message('success', 'Left the room, returning to lobby...')

			return True
		except Exception as e:
			self.log_message('error', f'Failed to leave room: {str(e)[:100]}')

			return False

	def get_role_max(self, role_id):
		return self.ROLE_MAX_COUNT.get(role_id, 1)

	def validate_combo(self, combo):
		counts = Counter(combo)

		for role in counts:
			if role in self.NOT_ALLOWED_ROLES:
				return False

		for role, cnt in counts.items():
			if cnt > self.get_role_max(role):
				return False

		if sum(counts[r] for r in counts if r in self.WW_ROLES) < self.WW_MIN:
			return False

		if sum(counts[r] for r in counts if r in self.SOLO_ROLES) < 1:
			return False

		if sum(counts[r] for r in counts if r in self.RV_ROLES) < 1:
			return False

		if sum(counts[r] for r in counts if r in self.KILLING_ROLES) > self.KILLING_MAX:
			return False

		if sum(counts[r] for r in counts if r in self.PROTECTING_ROLES) > self.PROTECTING_MAX:
			return False

		if sum(counts[r] for r in counts if r in self.INVESTIGATIVE_ROLES) > self.INVESTIGATIVE_MAX:
			return False

		return True

	def filter_combos(self, combos):
		result = []

		for combo in combos:
			counts = Counter(combo)

			has_vigilante = counts.get('vigilante', 0) > 0
			has_gunner = counts.get('gunner', 0) > 0

			if not (has_vigilante or has_gunner):
				continue

			if has_vigilante and has_gunner:
				continue

			if counts.get('priest', 0) < 1:
				continue

			has_jww = counts.get('junior-werewolf', 0) > 0
			has_split = counts.get('split-wolf', 0) > 0

			if not (has_jww or has_split):
				continue

			if has_jww and has_split:
				continue

			if counts.get('stubborn-werewolf', 0) > 0:
				continue

			result.append(combo)

		return result

	def pick_fill_roles(self, base, n, offset=0):
		counts = Counter(base)
		killing_used = sum(counts[r] for r in counts if r in self.KILLING_ROLES)
		protecting_used = sum(counts[r] for r in counts if r in self.PROTECTING_ROLES)
		inv_used = sum(counts[r] for r in counts if r in self.INVESTIGATIVE_ROLES)

		village_pool = sorted(self.VILLAGE_ROLES - self.NOT_ALLOWED_ROLES)

		rng = random.Random(offset)
		rng.shuffle(village_pool)

		fill = []
		fill_counts = Counter()

		for role in village_pool:
			if len(fill) >= n:
				break

			total = counts.get(role, 0) + fill_counts.get(role, 0)

			if total >= self.get_role_max(role):
				continue

			if role in self.KILLING_ROLES and killing_used >= self.KILLING_MAX:
				continue

			if role in self.PROTECTING_ROLES and protecting_used >= self.PROTECTING_MAX:
				continue

			if role in self.INVESTIGATIVE_ROLES and inv_used >= self.INVESTIGATIVE_MAX:
				continue

			fill.append(role)
			fill_counts[role] += 1

			if role in self.KILLING_ROLES:
				killing_used += 1

			if role in self.PROTECTING_ROLES:
				protecting_used += 1

			if role in self.INVESTIGATIVE_ROLES:
				inv_used += 1

		while len(fill) < n:
			if counts.get('villager', 0) + fill.count('villager') < self.get_role_max('villager'):
				fill.append('villager')

			else:
				return

		return fill

	def generate_xp_combos(self, target_sizes=(8, 10, 12, 16), max_per_size=1000, seed=42):
		random.seed(seed)

		usable_ww = sorted(self.WW_ROLES - self.NOT_ALLOWED_ROLES)
		usable_solo = sorted(self.SOLO_ROLES - self.NOT_ALLOWED_ROLES)
		usable_rv = sorted(self.RV_ROLES - self.NOT_ALLOWED_ROLES)

		ww_combos = list(combinations(usable_ww, 4))

		results = []
		seen = set()

		for target_size in target_sizes:
			fill_slots = target_size - 6
			size_results = []

			if fill_slots < 0:
				continue

			ww_shuffled = ww_combos[:]
			random.shuffle(ww_shuffled)

			for idx, ww_4 in enumerate(ww_shuffled):
				if len(size_results) >= max_per_size:
					break

				for solo in usable_solo:
					if len(size_results) >= max_per_size:
						break

					for rv in usable_rv:
						if len(size_results) >= max_per_size:
							break

						base = list(ww_4) + [solo, rv]
						fill = self.pick_fill_roles(base, fill_slots, offset=seed + idx)

						if fill is None:
							continue

						combo = tuple(sorted(base + fill))

						if combo in seen:
							continue

						if self.validate_combo(list(combo)):
							seen.add(combo)
							size_results.append(list(combo))

			results.extend(size_results)

		return results

	def generate_room_configs(self, count=5):
		PHRASES = [
			'This room has seen things you wouldn\'t believe. Stay anyway.',
			'The last person who left early is still regretting it to this day.',
			'Statistically speaking, you will survive. We choose not to elaborate.',
			'No refunds on wasted evenings, but the XP is real.',
			'Scientists confirm: leaving mid-game causes mild existential dread.',
			'This lobby is haunted by the ghosts of disconnected players.',
			'The seer checked. It\'s fine. Probably.',
			'We run 24/7 because sleep is for the innocent.',
			'Previous guests reported unexpected personal growth.',
			'The village has trust issues. You\'ll fit right in.',
			'Somewhere out there, a therapist is waiting for your game recap.',
			'Last session ended peacefully. We don\'t talk about the one before.',
			'Your future self will thank you for not leaving.',
			'Fun fact: nobody who stayed regretted it. Sample size: disputed.',
			'The chaos is part of the experience. We promise.',
			'Certified grind zone. Decertification pending investigation.',
			'Enter with low expectations. Leave with XP. Win-win.',
			'The vibes are immaculate. Legally we can\'t say more.',
			'Three players last week had a spiritual awakening. Coincidence.',
			'The detective is always wrong here, and somehow that\'s comforting.',
			'This room operates on pure spite and collective delusion.',
			'You joined. That was the first smart decision you\'ve made today.',
			'Plot twist incoming. There\'s always a plot twist.',
			'The fool won last round and nobody is over it.',
			'XP doesn\'t lie. People do. Come for the XP.',
			'Every game here is a masterclass in trusting the wrong person.',
			'Rumor has it someone once left at round 2. They are not missed.',
			'The grind is real. The drama is realer. The XP is realest.',
			'This is fine. Everything is fine. The wolves are fine.',
			'We\'ve been running since before your sleep schedule fell apart.',
			'Your mother would want you to get that XP.',
			'Unconfirmed reports suggest fun is occasionally had here.',
			'No judgment. Only voting. And occasionally judgment.',
			'The game doesn\'t stop. Neither do we. Neither should you.',
			'Brought to you by insomnia and a deep love of grinding.',
			'Current mood: 16 players, zero trust, maximum XP.',
			'This room is a social experiment that got out of hand.',
			'Economists agree: leaving early is a net negative. Stay.',
			'Abandon hope, all ye who disconnect.',
			'The wolves are just misunderstood. The XP is not.',
			'We do not gatekeep the grind. The grind gatekeeps itself.',
			'Nothing builds character like being betrayed by player 7.',
			'A wise man once said: never leave before the XP screen.',
			'The lobby is always open. Your excuses are not welcome here.',
			'Join. Stay. Grind. Repeat. Touch grass later.',
			'Your ancestors did not survive this long for you to leave at round 3.',
			'Leaving early will be reported to your local village council.',
			'We have your IP. Stay.',
			'The wolves know where you live. Finish the game.',
			'Disconnecting triggers an automatic strongly worded letter.'
		]

		BASE_CONFIG = {
			'language': 'en',
			'gameServerBaseUrl': 'https://game.api-wolvesville.com',
			'startGameDelayInMs': 15000,
			'nightDurationInMs': 30000,
			'dayDiscussionDurationInMs': 10000,
			'dayVotingDurationInMs': 80000,
			'randomRolesExcludedRoles': ['stubborn-werewolf', 'kitten-wolf'],
			'friendsGameEveryoneCanInvite': True,
			'privateGame': False,
			'talismansEnabled': False,
			'hideRoleOnDeath': False,
			'hasPassword': False,
			'password': '',
			'minLevel': 0,
			'voiceEnabled': False,
			'regularXp': True,
			'discussionSkipEnabled': False,
			'votesHidden': False,
			'preventAutostartIfLobbyIsFull': False,
			'disableSpecSeeingDeathChat': False,
			'roleCardsDisabled': False,
			'disabledRoleCardAbilities': [],
			'isRowWars': False,
			'isGridWars': False,
			'effectSepiaEnabled': False,
			'allCoupled': True,
			'unleashedElements': False,
			'mandatoryVote': True,
			'assassinsConvention': False,
			'hotPotatoEnabled': False,
			'is9PlayerGame': False,
			'is25PlayerGame': False,
			'honorEnabled': False,
			'customRandomRoles': [],
			'privateChatEnabled': False,
			'dayPrivateChatEnabled': False,
			'roseTradingEnabled': True,
			'proximityChatEnabled': False,
			'randomPhaseDuration': False,
			'lastWillEnabled': False,
			'draftingEnabled': False,
			'anonymousPlayersEnabled': False
		}

		if not getattr(self, '_cached_configs', None):
			combos = self.generate_xp_combos(
				target_sizes=(16,),
				max_per_size=count * 2000,
				seed=int(datetime.now(pytz.utc).timestamp()) % 100000
			)

			combos = self.filter_combos(combos)

			while len(combos) < count:
				extra = self.generate_xp_combos(
					target_sizes=(16,),
					max_per_size=(count - len(combos)) * 2000,
					seed=int(datetime.now(pytz.utc).timestamp()) % 100000 + 1
				)

				combos.extend(self.filter_combos(extra))

			combos = combos[:count]
			phrases = random.sample(PHRASES, min(count, len(PHRASES)))
			configs = {}

			for i, combo in enumerate(combos, start=1):
				phrase = phrases[i - 1]
				description = f'Game #{i} 💘 | 24/7 until crash | Wait for 8 players ⏳ | No random kills/votes ❌ | {phrase}'

				cfg = dict(BASE_CONFIG)
				cfg['name'] = f'M | VILL WIN #{i} 💘'
				cfg['roles'] = combo
				cfg['pinnedMessage'] = description
				cfg['hostedDate'] = datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')

				configs[f'combo_{i}'] = cfg

			self._cached_configs = configs

			self.log_message('success', f'Generated {count} room configs (cached for session)')

		else:
			self.log_message('info', 'Reusing cached room configs')

		return self._cached_configs

	def patch_custom_games_config(self, configs):
		current_history = self.page.evaluate('() => localStorage.getItem("custom-games-history")')

		try:
			history = json.loads(current_history) if current_history else []
		except:
			history = []

		if not isinstance(history, list):
			history = []

		history = [e for e in history if not e.get('name', '').startswith('M | ')]

		for cfg in reversed(list(configs.values())):
			history.insert(0, cfg)

		self.page.evaluate(f'() => localStorage.setItem("custom-games-history", JSON.stringify({json.dumps(history)}))')

		return len(configs)

	def check_pcg_status(self):
		try:
			ENDPOINT = 'purchasableItems/customGamesPremiumPrice'

			url = f'{self.BEARER_BASE_URL}{ENDPOINT}'
			headers = json.dumps(self.BEARER_HEADERS)

			response = self.page.evaluate(f'''
				async () => {{
					try {{
						const response = await fetch("{url}", {{
							method: "GET",
							headers: {headers}
						}});

						const text = await response.text();

						return {{
							status: response.status,
							body: text
						}};
					}} catch (e) {{
						return {{
							status: 500,
							body: e.message
						}};
					}}
				}}
			''')

			status = response.get('status')

			if status == 204:
				self.log_message('success', 'Premium Custom Games is active!')

				return True

			elif status == 200:
				self.log_message('warning', f'Premium Custom Games not purchased')
				
				return False
			
			else:
				self.log_message('error', f'Premium Custom Games check failed, assuming not purchased')
				
				return False
		except Exception as e:
			self.log_message('error', f'PCG check failed: {e}')

			return False

	def create_custom_room(self):
		self.log_message('info', 'Generating XP room configs...')

		configs = self.generate_room_configs(count=5)

		self.patch_custom_games_config(configs)

		config_key = random.choice(list(configs.keys()))
		target_name = configs[config_key]['name']

		self.log_message('info', f'Selected config: {target_name}')

		for n in range(2, 6):
			try:
				create_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[2]/div[2]/div[2]/div[1]/div/div/div')
				
				button_text = create_button.text_content(timeout=500)

				if is_ui(button_text, 'create_game'):
					create_button.click(timeout=5000)

					time.sleep(0.1)

					break
			except PlaywrightTimeoutError:
				continue
		
		else:
			self.log_message('error', 'Create button not found')

			return False
		
		history_button = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div/div/div[2]/div/div/div/div/div/div[2]/div[1]/div/div[2]/div[2]/div/div/div')
				candidate.wait_for(state='visible', timeout=500)

				history_button = candidate

				break
			except PlaywrightTimeoutError:
				continue

		if not history_button:
			self.log_message('error', 'History button not found')

			return False

		history_button.click(timeout=5000)
		
		time.sleep(0.1)

		self.log_message('info', 'Searching for matching config...')

		target_names = {cfg['name'] for cfg in configs.values()}

		clicked = False

		for n in range(4, 8):
			for i in range(1, 20):
				try:
					name_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div/div/div[{i}]/div/div[1]/div[1]/div[1]')
					name_text = name_locator.text_content(timeout=300)

					if not name_text:
						break

					if name_text.strip() == target_name:
						self.log_message('success', f'Found config: {name_text.strip()}, clicking...')

						card_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div/div/div[{i}]')
						card_locator.click(timeout=5000)

						clicked = True

						time.sleep(0.1)

						break
				except PlaywrightTimeoutError:
					break

			if clicked:
				break

		if not clicked:
			self.log_message('error', 'No matching config found in history')

			return False

		start_button = None

		for n in range(2, 6):
			try:
				candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div/div/div[2]/div/div/div/div/div/div[2]/div[2]/div[2]/div/div/div/div/div')
				candidate.wait_for(state='visible', timeout=1000)

				button_text = candidate.text_content(timeout=500)

				if is_ui(button_text, 'create_game'):
					start_button = candidate

					break
			except PlaywrightTimeoutError:
				continue

		if not start_button:
			self.log_message('error', 'Create game button not found or config is invalid')
			
			return False

		start_button.click(timeout=5000)

		self.log_message('success', 'Game created! Waiting for players...')

		self.is_host = True

		return True

	def play(self, already_in_room=False):
		rejoined = False

		while True:
			banner(self.__class__.__name__)

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')

				return

			if self.check_guest_mode() and already_in_room:
				self.log_message('cyan', 'Guest mode active — reloading to switch mode')
				
				self.reload_page()

				return

			if already_in_room:
				already_in_room = False

			elif not rejoined:
				self.is_host = False

				if not self.auto_find_and_join():
					return

			else:
				rejoined = False

			self.log_message('info', 'Waiting for game start...')

			start = False
			werewolf = False
			wait_start_time = time.monotonic()

			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Booster stop requested')
					
					return

				if self.check_guest_mode_changed():
					self.log_message('cyan', 'Guest mode changed — reloading to switch mode')
					
					self.reload_page()

					return

				if self.check_guest_mode() and self.is_host:
					self.log_message('cyan', 'Guest mode activated — reloading to switch mode')
					
					self.reload_page()

					return

				elapsed_time = time.monotonic() - wait_start_time
				wait_limit = 300 if self.is_host else 60

				if elapsed_time > wait_limit:
					limit_label = '5 minutes' if self.is_host else '1 minute'
					self.log_message('warning', f'Game not starting for {limit_label}, leaving room...')

					if self.leave_room():
						if not self.auto_find_and_join():
							return

						start = False
						werewolf = False
						wait_start_time = time.monotonic()

						continue

					else:
						self.log_message('warning', 'Could not leave room — waiting 1 more minute before reload...')

						wait_start_time = time.monotonic()

						while time.monotonic() - wait_start_time < 60:
							if self.check_stop_flag():
								return

							time.sleep(1)

							night_chat_found = False

							for n in range(2, 6):
								try:
									night_chat = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[3]/div/div[1]')
									night_chat.wait_for(state='visible', timeout=300)

									night_chat_found = True

									break
								except PlaywrightTimeoutError:
									continue

							if night_chat_found:
								start = True

								break

						if start:
							break

						self.log_message('warning', 'Still no game after extra wait — reloading page...')
						
						self.reload_page()

						return

				already_started = False

				if not self.is_host:
					try:
						for n in range(4, 8):
							try:
								candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div/div/div').first

								if candidate.is_visible(timeout=200):
									button_text = candidate.text_content(timeout=200)

									if is_ui(button_text, 'ok'):
										self.log_message('warning', 'Game already started, returning to lobby...')

										candidate.click()

										time.sleep(1)

										already_started = True

										break
							except PlaywrightTimeoutError:
								continue
					except:
						pass

				if already_started:
					if not self.auto_find_and_join():
						return

					start = False
					werewolf = False
					wait_start_time = time.monotonic()

					continue
				
				if not self.is_host:
					try:
						host_left_ok_button = None

						for n in range(4, 8):
							try:
								candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div/div/div')

								if candidate.is_visible(timeout=500):
									button_text = candidate.text_content(timeout=500)

									if is_ui(button_text, 'ok'):
										host_left_ok_button = candidate

										break
							except PlaywrightTimeoutError:
								continue

						if host_left_ok_button:
							self.log_message('warning', 'Host left the room, returning to lobby...')

							host_left_ok_button.click()

							time.sleep(1)

							if not self.auto_find_and_join():
								return

							start = False
							werewolf = False
							wait_start_time = time.monotonic()

							continue
					except:
						pass

				try:
					self.page.evaluate('''
						() => {
							const overlays = document.querySelectorAll('[style*="z-index: 99999"]');
							for (const overlay of overlays) overlay.remove();
						}
					''')
				except:
					pass

				night_chat_found = False

				for n in range(2, 6):
					try:
						night_chat = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[3]/div/div[1]')
						night_chat.wait_for(state='visible', timeout=500)

						chat_text = night_chat.text_content(timeout=500)

						if is_ui(chat_text, 'werewolf_chat'):
							werewolf = True

						night_chat_found = True

						break
					except PlaywrightTimeoutError:
						continue

				if night_chat_found:
					start = True

					break

				try:
					for n in range(2, 6):
						try:
							host_create_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div/div/div[1]/div[1]/div[1]/div[2]/div[4]/div[2]/div/div/div')
							
							button_text = host_create_button.text_content(timeout=200)

							if is_ui(button_text, 'start_game'):
								host_create_button.click(timeout=5000)

								self.log_message('success', 'Started game as host!')

								break
						except PlaywrightTimeoutError:
							continue
				except:
					pass

				try:
					for n in range(2, 6):
						try:
							create_game_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div/div/div[1]/div[1]/div[2]/div[3]/div/div/div/div/div[2]/div[2]/div[2]/div[1]/div/div/div')
							
							button_text = create_game_button.text_content(timeout=200)

							if is_ui(button_text, 'create_game'):
								try:
									for m in range(4, 8):
										try:
											close_popup_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{m}]/div/div[2]/div[2]/div/div/div')
											close_text = close_popup_button.text_content(timeout=500)
	
											if is_ui(close_text, 'ok') or close_text == '':
												close_popup_button.click()

												break
										except PlaywrightTimeoutError:
											continue
								except:
									pass

								break
						except PlaywrightTimeoutError:
							continue
				except:
					pass

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')

				return

			if not start:
				return

			self.day_signal_sent = False

			self.record_game_result(self.current_host, werewolf, self.last_role_name)
			
			self.current_host = None
			self.last_role_name = None

			if werewolf:
				self.act_werewolf()

			else:
				self.act_villager()

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')
				
				return

			self.log_message('info', 'Waiting for game end...')

			game_ended = False

			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Booster stop requested')

					return

				for n in range(2, 6):
					try:
						end_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div').get_by_text(ui_re('continue')).first

						if end_button.is_visible(timeout=200):
							end_button.click(timeout=5000)

							time.sleep(1)

							self.log_message('success', 'End!')

							game_ended = True

							break
					except PlaywrightTimeoutError:
						continue

				if game_ended:
					break

			self.send_end_message()

			self.log_message('info', 'Exiting...')

			time.sleep(1)

			try:
				play_again_button = None

				for _ in range(5):
					for n in range(2, 6):
						try:
							candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div[2]/div/div/div/div/div[1]/div[1]/div[2]/div[2]/div[3]/div[5]/div[2]/div/div[2]').get_by_text(ui_re('play_again')).first

							if candidate.is_visible(timeout=500):
								play_again_button = candidate

								break
						except PlaywrightTimeoutError:
							continue

					if play_again_button:
						break

					time.sleep(2)

				if not play_again_button:
					raise PlaywrightTimeoutError('Play again button not found')

				play_again_button.click()

				time.sleep(1)

				try:
					for n in range(4, 8):
						try:
							host_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[3]/div[2]/div/div')
							
							button_text = host_button.text_content(timeout=1000)

							if is_ui(button_text, 'ok'):
								host_button.click()

								break
						except PlaywrightTimeoutError:
							continue
				except:
					pass

				already_started = False

				try:
					for n in range(4, 8):
						try:
							modal_ok_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div/div/div')
							
							button_text = modal_ok_button.text_content(timeout=3000)

							if is_ui(button_text, 'ok'):
								self.log_message('warning', 'Game already started, closing...')

								modal_ok_button.click()

								time.sleep(1)

								already_started = True

								break
						except PlaywrightTimeoutError:
							continue
				except:
					pass

				time.sleep(0.1)

				if already_started:
					if not self.auto_find_and_join():
						return

				rejoined = True
			except PlaywrightTimeoutError:
				self.log_message('warning', 'Play again button timeout - returning to lobby')

				sound_path = get_resource_path(os.path.join('audio', 'glitch.mp3'))
				playsound(sound_path, block=False)

				try:
					home_button = None

					for n in range(2, 6):
						try:
							candidate = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div[2]/div/div/div/div/div[1]/div[1]/div[2]/div[2]/div[3]/div[5]/div[1]/div/div')
							candidate.wait_for(state='visible', timeout=3000)

							home_button = candidate

							break
						except PlaywrightTimeoutError:
							continue

					if home_button:
						home_button.click(timeout=3000)
				except:
					pass

				return

	def _start_hotkey_listener(self):
		if sys.platform != 'win32':
			return

		def _listen():
			try:
				import msvcrt

				while not self.check_stop_flag():
					if msvcrt.kbhit():
						key = msvcrt.getwch().lower()

						if key == 'g':
							self.guest_mode = not self.guest_mode

							state = 'GUEST (joining rooms)' if self.guest_mode else 'HOST (creating rooms)'
							
							self.log_message('cyan', f'[G] Mode switched → {state}')
					
					else:
						time.sleep(0.1)
			except Exception:
				pass

		threading.Thread(target=_listen, name='HotkeyListener', daemon=True).start()

	def run(self):
		banner(self.__class__.__name__)

		print()
		print(f'{Style.BRIGHT}{Fore.GREEN}1. {Fore.RESET}{Back.GREEN}Host — create own room (PCG required)')
		print(f'{Style.BRIGHT}{Fore.GREEN}2. {Fore.RESET}{Back.GREEN}Guest — join existing rooms')

		while True:
			try:
				choice = int(input(f'\n{Style.BRIGHT}{Fore.YELLOW}Mode:{Fore.RESET} '))

				if choice == 1:
					self.guest_mode = False

					break

				elif choice == 2:
					self.guest_mode = True

					break

				else:
					print(f'\n{Style.BRIGHT}{Back.RED}Incorrect choice!{Back.RESET}')
			except ValueError:
				print(f'\n{Style.BRIGHT}{Back.RED}Incorrect choice!{Back.RESET}')

		if sys.platform == 'win32':
			print(f'\n{Style.BRIGHT}{Fore.CYAN}Press G at any time to toggle Host/Guest mode{Fore.RESET}')

		self._start_hotkey_listener()
		self._run_core()

	def _run_core(self):
		_integrity_checker.verify_silent()

		if self._is_phantom():
			time.sleep(random.uniform(60.0, 180.0))

		banner(self.__class__.__name__)

		try:
			loop = asyncio.get_event_loop()

			if loop.is_running():
				nest_asyncio.apply()
		except:
			pass

		try:
			with sync_playwright() as playwright:
				self.log_message('info', 'Navigating to Wolvesville...')

				launch_args = [
					'--disable-blink-features=AutomationControlled',
					'--mute-audio',
					'--disable-features=Translate',
					'--lang=en-US',
					'--no-first-run',
					'--disable-extensions',
					'--disable-plugins',
					'--disable-background-networking',
					'--disable-sync',
					'--disable-default-apps',
					'--js-flags=--max-old-space-size=256',
					'--disable-dev-shm-usage'
				]

				if not self.headless_mode:
					launch_args.insert(0, '--window-position=-7,40')

				self.context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
					user_agent=self.USER_AGENT,
					viewport={
						'width': int(self.CHROME_VIEWPORT[0]),
						'height': int(self.CHROME_VIEWPORT[1])
					},
					headless=self.headless_mode,
					args=launch_args,
					ignore_default_args=['--enable-automation'],
					chromium_sandbox=True
				)

				self.page = self.context.pages[0]
				
				while True:
					if self.check_stop_flag():
						self.log_message('info', 'Booster stop requested')

						break

					try:
						self.page.goto('https://wolvesville.com', wait_until='domcontentloaded', timeout=120000)
						self.page.wait_for_load_state('networkidle', timeout=30000)

						break
					except PlaywrightTimeoutError:
						self.log_message('error', 'Timeout error, retrying...')

						continue

				changes = self.patch_localstorage()

				if changes:
					self.log_message('warning', f'Applied {changes} setting patches, reloading page...')

					self.page.reload(wait_until='domcontentloaded', timeout=120000)
					self.page.wait_for_load_state('networkidle', timeout=30000)

					self.log_message('success', 'Page reloaded, continuing...')

				self.get_bearer()

				if self.check_stop_flag():
					self.log_message('info', 'Booster stopping - closing browser')

					self.context.close()

					return

				self.log_message('success', 'Website opened!')

				while True:
					if self.check_stop_flag():
						self.log_message('info', 'Booster stopping - exiting main loop')

						break

					time.sleep(2)

					self.log_message('info', 'Opening custom games menu...')

					while True:
						if self.check_stop_flag():
							break

						try:
							for n in range(3, 8):
								try:
									cancel_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div[2]/div[2]/div[1]/div')

									if cancel_button.is_visible(timeout=500):
										self.log_message('warning', 'Found startup "Existing game" modal, closing...')

										cancel_button.click()

										time.sleep(1)

										break
								except:
									continue
						except:
							pass

						try:
							play_button = self.page.get_by_text(ui_re('play')).first
							play_button.wait_for(state='visible', timeout=10000)

							is_disabled = play_button.is_disabled(timeout=5000)
							
							if not is_disabled:
								time.sleep(0.5)

								play_button.click(timeout=5000)

								try:
									self.page.get_by_text(ui_re('custom_games')).first.wait_for(state='visible', timeout=3000)

									break
								except PlaywrightTimeoutError:
									self.log_message('warning', 'Click did not register, retrying...')
									
									time.sleep(1)
									
									continue

							else:
								time.sleep(0.5)
						except PlaywrightTimeoutError:
							time.sleep(0.5)

							continue

					if self.check_stop_flag():
						break

					while True:
						if self.check_stop_flag():
							break
							
						try:
							self.page.get_by_text(ui_re('custom_games')).first.click(timeout=10000)

							break
						except PlaywrightTimeoutError:
							continue

					if self.check_stop_flag():
						break

					time.sleep(3)

					try:
						for n in range(3, 8):
							try:
								join_new_button = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div[3]/div[3]/div/div')

								if join_new_button.is_visible(timeout=500):
									self.log_message('cyan', 'Found "Join New" prompt, clicking...')

									join_new_button.click()

									time.sleep(1)

									break
							except:
								continue
					except:
						pass

					self.log_message('success', 'Menu opened!')

					self.ensure_english_language()

					has_pcg = False
					created = False

					if self.guest_mode:
						self.log_message('cyan', 'Guest mode enabled - skipping PCG check, joining rooms only')
					
					else:
						has_pcg = self.check_pcg_status()

						if not has_pcg:
							self.guest_mode = True

							self.log_message('warning', 'No PCG — switching to guest mode automatically')

					if has_pcg:
						created = self.create_custom_room()

						if not created:
							return

					if self.check_guest_mode() and created:
						self.log_message('cyan', 'Guest mode activated after room creation — leaving room')
						self.leave_room()

						created = False

					self.play(already_in_room=created)

					if self.check_stop_flag():
						break

					if self.check_guest_mode_changed():
						self.log_message('cyan', 'Guest mode changed — reloading page')
						self.reload_page()

					if self.check_headless_mode_changed():
						self.log_message('cyan', 'Headless mode changed — restarting browser')
						
						break
		except KeyboardInterrupt:
			return
		except AttributeError as e:
			self.log_message('error', f'Critical error: {type(e).__name__}: {str(e)}')
		except Exception as e:
			self.log_message('error', f'Critical error: {type(e).__name__}: {str(e)}')

			return
