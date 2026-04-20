import os
import sys
import warnings

warnings.filterwarnings('ignore', category=Warning, module='gevent')

from gevent import monkey

if sys.platform != 'darwin':
    monkey.patch_all(subprocess=False)

import eel
import requests
import threading
import queue

import time
import logging
import traceback
import tkinter as tk

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS

    ms_playwright_path = os.path.join(base_path, 'ms-playwright')

    if os.path.exists(ms_playwright_path):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = ms_playwright_path

    for node_path in [
        os.path.join(base_path, 'playwright', 'driver', 'node.exe'),
        os.path.join(base_path, 'ms-playwright', 'node.exe'),
        os.path.join(base_path, 'node', 'node.exe'),
    ]:
        if os.path.exists(node_path):
            os.environ['PLAYWRIGHT_NODEJS_PATH'] = node_path

            break

try:
	import pyi_splash
except ImportError:
	pyi_splash = None

from colorama import Fore, Style, init
from dotenv import dotenv_values
from utils import set_launch_mode, check_updates_on_startup, banner
from translations import is_game_phase
from updater import EelUpdater
from tracker import Tracker
from booster import Booster
from stalker import Stalker

from spinner import SpinnerMobile

if os.name == 'nt':
    from spinner import SpinnerDesktop

set_launch_mode('GUI')

try:
	log = logging.getLogger('geventwebsocket.handler')
	log.setLevel(logging.ERROR)
except:
	pass

logging.getLogger('eel').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s [%(threadName)s] %(message)s',
	handlers=[logging.StreamHandler(sys.stdout)]
)

init(autoreset=True)

eel.init('gui')

VERSION = '1.0.4'
updater_instance = None

locks = {
	'tracker': threading.RLock(),
	'stalker': threading.RLock(),
	'booster': threading.RLock(),
	'spinner': threading.RLock()
}

active_modules = {
	'tracker': None,
	'stalker': None,
	'booster': None,
	'spinner': None
}

module_threads = {
	'tracker': None,
	'stalker': None,
	'booster': None,
	'spinner': None
}

stop_flags = {
	'tracker': threading.Event(),
	'stalker': threading.Event(),
	'booster': threading.Event(),
	'spinner': threading.Event()
}

pending_logs = {
	'tracker': [],
	'stalker': [],	
	'booster': [],
	'spinner': []
}

pending_states = {
	'tracker': [],
	'stalker': [],
	'booster': [],
	'spinner': []
}

logs_lock = threading.Lock()

_booster_stats_session = {
	'gamesPlayed': 0,
	'villagerGames': 0,
	'werewolfGames': 0,
	'soloGames': 0
}


def _start_watchdog(module_name, thread):
	def _watch():
		while True:
			time.sleep(5)

			if not active_modules.get(module_name):
				break

			if not thread.is_alive():
				logging.warning(f'{module_name} watchdog: thread is dead')

				with logs_lock:
					pending_states[module_name].append({'initialized': False, 'phase': 'Crashed', 'action': 'Idle'})

				break

	threading.Thread(target=_watch, name=f'{module_name.capitalize()}Watchdog', daemon=True).start()


class ModuleWrapper:
	def __init__(self, module_instance, module_name):
		self.module = module_instance
		self.name = module_name
		self.thread = None
		self.stop_flag = stop_flags[module_name]
		self.playwright_context = None
		self.status = 'idle'
		self.status_message = ''
		self.end_requested = False
		self.game_ended = False
		self.command_queue = queue.Queue()

		self.log_message = lambda msg_type, message: logging.info(f'{self.name} [{msg_type}]: {message}')

		if hasattr(module_instance, 'log_message'):
			self._inject_logging(module_instance, module_name)
		
	def _inject_logging(self, module_instance, module_name):
		original_log_message = module_instance.log_message
		
		def new_log_message(msg_type, message):
			original_log_message(msg_type, message)
			
			log_entry = {
				'type': msg_type,
				'message': message
			}
			
			with logs_lock:
				pending_logs[module_name].append(log_entry)

				if len(pending_logs[module_name]) > 500:
					pending_logs[module_name] = pending_logs[module_name][-500:]
		
		module_instance.log_message = new_log_message

		if hasattr(module_instance, 'log_state'):
			original_log_state = module_instance.log_state
			
			def new_log_state(phase, action):
				original_log_state(phase, action)

				state_entry = {
					'phase': phase,
					'action': action
				}
				
				with logs_lock:
					last = pending_states[module_name][-1] if pending_states[module_name] else None

					if last and 'phase' in last and 'stats' not in last and 'initialized' not in last:
						pending_states[module_name][-1] = state_entry
					
					else:
						pending_states[module_name].append(state_entry)
			
			module_instance.log_state = new_log_state

		if hasattr(module_instance, 'push_stats'):
			def new_push_stats(stats_dict):
				with logs_lock:
					last = pending_states[module_name][-1] if pending_states[module_name] else None

					if last and 'stats' in last and 'initialized' not in last:
						pending_states[module_name][-1] = {'stats': stats_dict}
					
					else:
						pending_states[module_name].append({'stats': stats_dict})

			module_instance.push_stats = new_push_stats
		
	def safe_close_browser(self):
		try:
			if hasattr(self.module, 'page') and self.module.page:
				logging.info(f'{self.name}: Closing browser page...')

				try:
					self.module.page.close()
				except Exception as e:
					logging.warning(f'{self.name}: Page close error: {e}')

				self.module.page = None

			if self.playwright_context:
				try:
					self.playwright_context.close()
				except Exception as e:
					logging.warning(f'{self.name}: Context close error: {e}')

				self.playwright_context = None
		except Exception as e:
			logging.error(f'{self.name}: Browser cleanup error: {e}')
	
	def stop(self):
		logging.info(f'{self.name}: Stop requested')

		self.stop_flag.set()
		self.safe_close_browser()

		if self.thread and self.thread.is_alive():
			logging.info(f'{self.name}: Waiting for thread to finish...')

			self.thread.join(timeout=5)
			
			if self.thread.is_alive():
				logging.warning(f'{self.name}: Thread did not stop in time')

			else:
				logging.info(f'{self.name}: Thread stopped successfully')
		
	def is_running(self):
		return self.thread is not None and self.thread.is_alive()


@eel.expose
def get_modules_status():
	status = {
		'version': f'{VERSION} GUI',
		'modules': {
			'tracker': False,
			'stalker': False,
			'booster': False,
			'spinner': False
		},
		'active_count': 0,
		'ready': True
	}
	
	try:
		tracker = Tracker()

		if hasattr(tracker, 'is_valid') and tracker.is_valid:
			status['modules']['tracker'] = True
	except Exception as e:
		logging.debug(f'Tracker unavailable: {e}')
	
	try:
		stalker = Stalker()

		if hasattr(stalker, 'is_valid') and stalker.is_valid:
			status['modules']['stalker'] = True
	except Exception as e:
		logging.debug(f'Stalker unavailable: {e}')
	
	try:
		booster = Booster()

		if hasattr(booster, 'is_valid') and booster.is_valid:
			status['modules']['booster'] = True
	except Exception as e:
		logging.debug(f'Booster unavailable: {e}')
	
	try:
		spinner = SpinnerMobile()

		if hasattr(spinner, 'is_valid') and spinner.is_valid:
			status['modules']['spinner'] = True
	except Exception as e:
		logging.debug(f'Spinner unavailable: {e}')

	status['active_count'] = sum(1 for v in status['modules'].values() if v)
	status['ready'] = status['active_count'] > 0
	
	return status

@eel.expose
def tracker_start():
	with locks['tracker']:
		if active_modules['tracker'] is not None:
			return {'success': True, 'status': 'already_running'}

	try:
		logging.info('Initializing Tracker module...')
		tracker = Tracker()

		if hasattr(tracker, 'is_valid') and not tracker.is_valid:
			return {'success': False, 'error': 'Tracker validation failed (Check API Keys)'}

		wrapper = ModuleWrapper(tracker, 'tracker')

		tracker.check_stop_flag = lambda: stop_flags['tracker'].is_set()

		wrapper.status = 'starting'
		wrapper.status_message = 'Initializing browser...'
		
		active_modules['tracker'] = wrapper
		stop_flags['tracker'].clear()

		def run_tracker_logic():
			from undetected_playwright.sync_api import sync_playwright

			def update_status(state, msg):
				wrapper.status = state
				wrapper.status_message = msg
				wrapper.log_message('info', f'[{state.upper()}] {msg}')

			try:
				update_status('starting', 'Launching browser...')
				
				with sync_playwright() as playwright:
					if tracker.check_stop_flag():
						return

					context = playwright.chromium.launch_persistent_context(
						executable_path=tracker.CHROME_EXECUTABLE,
						user_data_dir=tracker.CHROME_USER_DATA,
						viewport={
							'width': int(tracker.CHROME_VIEWPORT[0]), 
							'height': int(tracker.CHROME_VIEWPORT[1])
						},
						headless=False,
						args=[
							'--window-position=-7,40', 
							'--disable-blink-features=AutomationControlled'
						],
						ignore_default_args=['--enable-automation'],
						chromium_sandbox=True
					)
					
					wrapper.playwright_context = context
					tracker.page = context.pages[0]
					
					update_status('starting', 'Navigating to Wolvesville...')

					from undetected_playwright.sync_api import TimeoutError as PlaywrightTimeoutError

					while not tracker.check_stop_flag():
						try:
							tracker.page.goto('https://wolvesville.com', wait_until='domcontentloaded', timeout=120000)

							try:
								tracker.page.wait_for_load_state('networkidle', timeout=30000)
							except PlaywrightTimeoutError:
								pass

							break
						except PlaywrightTimeoutError:
							update_status('starting', 'Timeout navigating to Wolvesville, retrying...')

							continue
						except:
							update_status('starting', f'Navigation error, retrying...')

							time.sleep(3)

							continue

					if tracker.check_stop_flag():
						return

					update_status('starting', 'Website opened!')

					changes = tracker.patch_localstorage()

					if changes:
						update_status('starting', f'Applied {changes} setting patches, reloading page...')

						tracker.page.reload(wait_until='domcontentloaded', timeout=120000)

						try:
							tracker.page.wait_for_load_state('networkidle', timeout=30000)
						except PlaywrightTimeoutError:
							pass

						update_status('starting', 'Page reloaded, continuing...')

					while not tracker.check_stop_flag():
						if not tracker.page or tracker.page.is_closed():
							logging.warning('Browser closed externally.')

							break

						if tracker.prepare():
							logging.error('Tracker prepare failed.')

							break

						update_status('waiting_for_game', 'Waiting for game start...')

						while not tracker.check_stop_flag():
							if not tracker.page or tracker.page.is_closed():
								break

							try:
								phase_locator = None

								for n in range(2, 6):
									try:
										candidate = tracker.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[{n}]/div/div/div/div/div[2]/div/div/div/div/div[1]/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
										candidate.wait_for(state='visible', timeout=500)

										phase_locator = candidate.first

										break
									except:
										continue

								if phase_locator:
									phase_text = phase_locator.text_content(timeout=1000)

									if is_game_phase(phase_text):
										break
							except:
								pass

							time.sleep(1)

						time.sleep(1)

						if tracker.check_stop_flag():
							break

						if not tracker.page or tracker.page.is_closed():
							break

						update_status('scanning', 'Game found!')
						
						try:
							tracker.get_bearer()
							
							if tracker.check_stop_flag():
								break

							tracker.load_css()
							tracker.load_modal()
							
							update_status('scanning', 'Finding players...')

							wrapper.game_ended = False

							players_grid_xpath = tracker.find_players_grid_xpath()

							if players_grid_xpath is None:
								logging.warning('Player grid not found, waiting for next game...')
								update_status('waiting_for_game', 'Player grid not found. Waiting for next game...')

								time.sleep(3)

								continue

							tracker.find_players(players_grid_xpath)
							
							update_status('scanning', 'Analyzing setup...')

							roles = tracker.find_roles()
							rotations = tracker.get_rotations()
							tracker.ROTATION = tracker.choose_rotation(rotations, roles)

							if tracker.ROTATION is None:
								logging.warning('Rotation not found (Custom game?), continuing with partial data...')
							
							update_status('running', 'Tracker Active')

							while not tracker.check_stop_flag():
								if not tracker.page or tracker.page.is_closed():
									break

								if wrapper.end_requested:
									wrapper.end_requested = False
									wrapper.game_ended = True

									tracker.PLAYERS = []
									tracker.PLAYER_LAYERS = []
									tracker.PLAYER_CARDS = {}
									tracker.PLAYER_ICONS = {}
									tracker.ROTATION = None
									tracker.PLAYER_ALLIANCES = {}
									tracker.PLAYER_CLAIMS = {}

									update_status('waiting_for_game', 'Game ended. Waiting for next game...')

									break

								try:
									while True:
										cmd_fn = wrapper.command_queue.get_nowait()
										cmd_fn()
								except queue.Empty:
									pass
								
								try:
									tracker.update_players()
								except Exception as e:
									logging.error(f'Tracker error: {e}')
									logging.error(traceback.format_exc())

								time.sleep(3)
						except Exception as e:
							logging.error(f'Tracker game loop error: {e}')
							logging.error(traceback.format_exc())
							
							update_status('error', f'Game Error: {str(e)[:50]}')

							time.sleep(3)
			except Exception as e:
				logging.error(f'Tracker Critical Thread Error: {e}')
				logging.error(traceback.format_exc())

				try:
					wrapper.status = 'error'
					wrapper.status_message = str(e)
				except:
					pass
			finally:
				with logs_lock:
					pending_states['tracker'].append({'initialized': False, 'phase': 'Stopped', 'action': 'Idle'})

				wrapper.safe_close_browser()

				with locks['tracker']:
					active_modules['tracker'] = None

				logging.info('Tracker thread finished.')

		thread = threading.Thread(target=run_tracker_logic, name='TrackerThread', daemon=True)
		module_threads['tracker'] = thread
		thread.start()

		_start_watchdog('tracker', thread)

		return {'success': True}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def tracker_get_state():
	tracker_wrapper = active_modules.get('tracker')

	response = {
		'success': False,
		'status': 'stopped',
		'message': 'Tracker not running',
		'players': [],
		'rotation': [],
		'threat_levels': {},
		'player_alliances': {},
		'player_claims': {},
		'bayes': {},
		'nlp': {}
	}

	if not tracker_wrapper:
		return response

	tracker = tracker_wrapper.module

	response['success'] = True
	response['status'] = getattr(tracker_wrapper, 'status', 'unknown')
	response['message'] = getattr(tracker_wrapper, 'status_message', '')

	if response['status'] in ['running', 'scanning', 'waiting_for_game']:
		try:
			with locks['tracker']:
				state = tracker.to_dict()

				if state:
					response.update(state)

				response['player_alliances'] = getattr(tracker, 'PLAYER_ALLIANCES', {})
				response['threat_levels'] = getattr(tracker, 'THREAT_LEVELS', {})
				response['player_claims'] = getattr(tracker, 'PLAYER_CLAIMS', {})
				response['bayes'] = tracker.bayes.serialise_for_frontend() if hasattr(tracker, 'bayes') else {}
				response['nlp'] = tracker.nlp.serialise_for_frontend() if hasattr(tracker, 'nlp') else {}

				has_rotation = hasattr(tracker, 'ROTATION') and tracker.ROTATION
				remaining = {'GOOD': [], 'EVIL': [], 'UNKNOWN': []}

				if getattr(tracker_wrapper, 'game_ended', False):
					has_rotation = False
				
				if has_rotation:
					distinct_rotation = []
					for role in tracker.ROTATION:
						if role not in distinct_rotation:
							distinct_rotation.append(role)

					for role in distinct_rotation:
						total = tracker.ROTATION.count(role)
						found = sum(1 for p in tracker.PLAYERS if p.get('role') == role.get('id'))
						role_info = tracker.ROLES.get(role['id'], {})
						role_name = role_info.get('name', 'Unknown')

						for _ in range(max(0, total - found)):
							remaining[role['aura']].append(role_name)

				response['remaining'] = remaining

				if 'players' in response and response['players']:
					for i, p_data in enumerate(response['players']):
						try:
							if i >= len(tracker.PLAYERS):
								break
							
							player_obj = tracker.PLAYERS[i]
							name = p_data['name']

							role_id = p_data.get('role')
							p_data['role_name'] = role_id 

							if role_id:
								if hasattr(tracker, 'ROLES') and role_id in tracker.ROLES:
									p_data['role_name'] = tracker.ROLES[role_id].get('name', role_id)

								elif isinstance(role_id, str):
									p_data['role_name'] = role_id.replace('-', ' ').title()

							msgs = player_obj.get('messages') or []
							mentions = player_obj.get('mentions') or []
							
							p_data['messages'] = msgs
							p_data['mentions'] = mentions
							p_data['messages_count'] = len(msgs)
							p_data['mentions_count'] = len(mentions)
							
							p_data['teams_exclude'] = list(player_obj.get('teams_exclude', []))
							p_data['equal'] = list(player_obj.get('equal', []))
							p_data['not_equal'] = list(player_obj.get('not_equal', []))
							p_data['hero'] = player_obj.get('hero', False)
							
							p_data['claim'] = tracker.PLAYER_CLAIMS.get(name, {}).get('role')
							p_data['contradiction'] = player_obj.get('contradiction')

							if p_data.get('role'):
								role_id = p_data['role']
								role_def = tracker.ROLES.get(role_id)
								p_data['role_name'] = role_def.get('name', role_id) if role_def else role_id.title()
							
							else:
								p_data['role_name'] = None

							possible = []

							if has_rotation and not p_data.get('role'):
								cards_dict = getattr(tracker, 'PLAYER_CARDS', {}).get(name, {})
								flatten_cards = []

								for c in cards_dict.values():
									if isinstance(c, list): 
										flatten_cards.extend(c)

									else:
										flatten_cards.append(c)

								icons = getattr(tracker, 'PLAYER_ICONS', {}).get(name, {})
								team = player_obj.get('team')
								aura = player_obj.get('aura')

								for role in tracker.ROTATION:
									if 'random' in role['id']:
										continue

									r_id = role['id']
									r_info = tracker.ROLES.get(r_id, {})
									r_name = r_info.get('name', 'Unknown')
									
									player_icon = icons.get(r_id)
									role_icon = getattr(tracker, 'ROTATION_ICONS', {}).get(r_id)
									
									base_test = [
										role['team'] not in p_data['teams_exclude'],
										not team or team == role['team'],
										not aura or aura == role['aura'],
										r_name in remaining.get(role['aura'], [])
									]
									role_test = [
										r_id in flatten_cards,
										not player_icon or player_icon == role_icon
									]

									if all(base_test) and all(role_test):
										possible.append({
											'role': r_name,
											'has_card': r_id in flatten_cards,
											'has_icon': player_icon == role_icon if player_icon else True
										})

							p_data['possible_roles'] = possible
						except Exception as inner_e:
							logging.error(f'Error enriching data for player {i}: {inner_e}')
							
							continue
		except Exception as e:
			logging.error(f'Error retrieving state inside get_state: {e}')
	
	return response

@eel.expose
def tracker_update_analytics():
    pass

@eel.expose
def tracker_send_command(command):
	tracker_wrapper = active_modules.get('tracker')

	if not tracker_wrapper:
		return {'success': False, 'error': 'Tracker is not running'}
	
	tracker = tracker_wrapper.module

	try:
		cmd = command.strip()

		if cmd.lower() == 'end':
			tracker_wrapper.end_requested = True
			tracker_wrapper.game_ended = True
			tracker.PLAYERS = []
			tracker.PLAYER_LAYERS = []
			tracker.PLAYER_CARDS = {}
			tracker.PLAYER_ICONS = {}
			tracker.ROTATION = None
			tracker.PLAYER_ALLIANCES = {}
			tracker.PLAYER_CLAIMS = {}

			return {'success': True}

		def execute_command():
			try:
				if cmd.lower() == 'end':
					tracker_wrapper.end_requested = True

				elif cmd.lower().startswith('name of '):
					parts = cmd.split(' is ', 1)

					if len(parts) == 2:
						p_part = parts[0].lower().replace('name of ', '').strip()

						if p_part.isdigit():
							p_idx = int(p_part) - 1

							tracker.set_name(p_idx, parts[1].strip())

				elif cmd.lower().startswith('change '):
					parts = cmd.lower().replace('change ', '').split(' to ')

					if len(parts) == 2:
						tracker.change_role(parts[0].strip(), parts[1].strip())

				elif cmd.lower().startswith('remove '):
					parts = cmd.lower().replace('remove ', '').split(' from ')

					if len(parts) == 2:
						role_name = parts[0].strip()
						p_idx = int(parts[1].strip()) - 1

						tracker.remove_role(p_idx, role_name)

				elif cmd.lower().startswith('clear '):
					p_part = cmd.lower().replace('clear ', '').strip()

					if p_part.isdigit():
						p_idx = int(p_part) - 1

						tracker.PLAYERS[p_idx].update({
							'role': None, 'team': None,
							'teams_exclude': set(), 'equal': set(), 'not_equal': set(),
							'aura': 'UNKNOWN', 'contradiction': None
						})

				elif ' is ' in cmd:
					p, info = cmd.split(' is ', 1)

					tracker.set_player_info(p.strip(), info.strip())

				elif '=' in cmd or '!=' in cmd:
					is_equal = '!=' not in cmd
					parts = cmd.split('!=' if not is_equal else '=')
					indices = [int(p.strip()) - 1 for p in parts if p.strip().isdigit()]
					
					if len(indices) == 2:
						tracker.set_equal(indices, is_equal)

				elif cmd.lower() == 'storm':
					tracker.storm()

				elif cmd.lower() == 'update':
					tracker.update_players()

				elif cmd.lower() == 'cursed turned':
					tracker.set_cursed()
			except Exception as e:
				logging.error(f'Error executing queued command: {e}')

		tracker_wrapper.command_queue.put(execute_command)

		return {'success': True}
	except Exception as e:
		logging.error(f'Error executing command: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def tracker_predict(player_name=None):
	tracker_wrapper = active_modules.get('tracker')

	if not tracker_wrapper:
		return {'success': False, 'error': 'Tracker not running'}
	
	tracker = tracker_wrapper.module
	
	if not getattr(tracker, 'mastermind', None):
		return {'success': False, 'error': 'Mastermind unavailable'}

	try:
		with locks['tracker']:
			tracker.mastermind.update_state()
			scenarios = tracker.mastermind.predict(max_depth=3, player_name=player_name)
			formatted = []

			for s in scenarios[:10]:
				path = []

				for a in s.get('path', []):
					path.append({
						'actor': a['actor']['name'],
						'ability': a['ability']['description'],
						'target': str(a.get('target', ''))
					})

				formatted.append({
					'probability': s.get('prob', 0),
					'score': s.get('score', 0),
					'path': path
				})

			return {'success': True, 'scenarios': formatted}
	except Exception as e:
		logging.error(f'Mastermind error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def tracker_stop():
	if not active_modules['tracker']:
		return {'success': True, 'message': 'Not running'}
	
	logging.info('Stopping Tracker module...')

	stop_flags['tracker'].set()

	try:
		if active_modules['tracker']:
			active_modules['tracker'].status = 'stopped'
			active_modules['tracker'].status_message = 'Stopping...'
	except:
		pass

	return {'success': True}

@eel.expose
def stalker_start():
	with locks['stalker']:
		if active_modules['stalker'] is not None:
			return {'success': True, 'status': 'already_running'}

	try:
		stalker = Stalker()
		
		if hasattr(stalker, 'is_valid') and not stalker.is_valid:
			return {'success': False, 'error': 'Authentication failed'}
		
		wrapper = ModuleWrapper(stalker, 'stalker')
		active_modules['stalker'] = wrapper
		
		return {'success': True}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def stalker_get_targets(page=1):
	stalker_wrapper = active_modules.get('stalker')

	if not stalker_wrapper:
		stalker = Stalker()
		wrapper = ModuleWrapper(stalker, 'stalker')
		active_modules['stalker'] = wrapper
		stalker_wrapper = wrapper

	stalker = stalker_wrapper.module

	try:
		with locks['stalker']:
			per_page = 5
			target_items = list(stalker.TARGETS.items())
			total_targets = len(target_items)
			total_pages = max(1, (total_targets + per_page - 1) // per_page)
			start = (page - 1) * per_page
			end = start + per_page
			targets = []

			for i, (tid, history) in enumerate(target_items[start:end]):
				if history:
					t = history[-1].copy()
					t['id'] = tid
					t['index'] = start + i + 1

					if 'clan' in t and t['clan']:
						t['clan'] = {k: (f'{v}xp' if 'xp' in k.lower() and isinstance(v, (int, float)) else v)
									for k, v in t['clan'].items()}

					targets.append(t)

			return {
				'success': True,
				'targets': targets,
				'current_page': page,
				'total_pages': total_pages
			}
	except Exception as e:
		logging.error(f'Stalker error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def stalker_add_target(username):
	stalker_wrapper = active_modules.get('stalker')

	if not stalker_wrapper:
		return {'success': False, 'error': 'Stalker not initialized'}

	stalker = stalker_wrapper.module

	try:
		with locks['stalker']:
			res_id = stalker.get_player_id(username)

			if res_id[0]: 
				return {'success': False, 'error': res_id[1]}

			tid = res_id[1]
			res_p = stalker.get_player(tid)

			if res_p[0]:
				return {'success': False, 'error': res_p[1]}

			stalker.write_target(tid, res_p[1])
			stalker.save_targets()

			return {'success': True}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def stalker_update_targets():
	stalker_wrapper = active_modules.get('stalker')

	if not stalker_wrapper:
		return {'success': False}

	stalker = stalker_wrapper.module

	def task():
		with locks['stalker']: 
			stalker.update_targets()

	threading.Thread(target=task, daemon=True).start()

	return {'success': True}

@eel.expose
def stalker_delete_target(target_id):
	stalker_wrapper = active_modules.get('stalker')

	if not stalker_wrapper:
		return {'success': False, 'error': 'Stalker not initialized'}

	stalker = stalker_wrapper.module

	try:
		with locks['stalker']:
			if target_id not in stalker.TARGETS:
				return {'success': False, 'error': 'Target not found'}

			stalker.write_target(target_id)
			stalker.save_targets()

			return {'success': True}
	except Exception as e:
		logging.error(f'stalker_delete_target error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def booster_start():
	try:
		with locks['booster']:
			if active_modules['booster'] and active_modules['booster'].is_running():
				return {'success': False, 'error': 'Booster is already running'}
			
			stop_flags['booster'].clear()
			
			booster_instance = Booster()
			
			if not booster_instance.is_valid:
				return {'success': False, 'error': 'Booster configuration is invalid'}

			booster_instance.stats = dict(_booster_stats_session)

			booster_stop_flag = stop_flags['booster']

			def patched_check_stop():
				return booster_stop_flag.is_set()

			booster_instance.check_stop_flag = patched_check_stop
			
			wrapper = ModuleWrapper(booster_instance, 'booster')
			active_modules['booster'] = wrapper
			
			def run_booster():
				try:
					logging.info('Booster thread started')
					booster_instance._run_core()
					logging.info('Booster thread finished normally')
				except Exception as e:
					logging.error(f'Booster error: {e}')
					logging.error(traceback.format_exc())
				finally:
					global _booster_stats_session
					_booster_stats_session = dict(booster_instance.stats)

					with logs_lock:
						pending_states['booster'].append({'initialized': False, 'phase': 'Stopped', 'action': 'Idle'})

					with locks['booster']:
						if active_modules['booster']:
							active_modules['booster'].safe_close_browser()

			thread = threading.Thread(target=run_booster, name='BoosterThread', daemon=True)
			wrapper.thread = thread
			module_threads['booster'] = thread

			with logs_lock:
				pending_states['booster'].append({
					'initialized': True,
					'phase': 'Starting',
					'action': 'Initializing'
				})

			thread.start()

			_start_watchdog('booster', thread)

			time.sleep(0.1)

			return {'success': True}
	except Exception as e:
		logging.error(f'booster_start error: {e}')
		logging.error(traceback.format_exc())

		return {'success': False, 'error': str(e)}

@eel.expose
def booster_get_stats():
	try:
		wrapper = active_modules.get('booster')

		if wrapper:
			return {'success': True, 'stats': wrapper.module.stats}

		return {'success': True, 'stats': dict(_booster_stats_session)}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def booster_get_guest_mode():
	try:
		wrapper = active_modules.get('booster')

		if wrapper:
			return {'success': True, 'guest_mode': wrapper.module.guest_mode}

		return {'success': True, 'guest_mode': False}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def booster_set_guest_mode(enabled):
	try:
		enabled = bool(enabled)

		wrapper = active_modules.get('booster')

		if wrapper:
			wrapper.module.set_guest_mode(enabled)

		state = 'enabled' if enabled else 'disabled'
		logging.info(f'Booster guest mode {state}')

		return {'success': True, 'guest_mode': enabled}
	except Exception as e:
		logging.error(f'booster_set_guest_mode error: {e}')
		return {'success': False, 'error': str(e)}

@eel.expose
def booster_get_headless_mode():
	try:
		wrapper = active_modules.get('booster')

		if wrapper:
			return {'success': True, 'headless_mode': wrapper.module.headless_mode}

		return {'success': True, 'headless_mode': False}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def booster_set_headless_mode(enabled):
	try:
		enabled = bool(enabled)

		wrapper = active_modules.get('booster')

		if wrapper:
			wrapper.module.set_headless_mode(enabled)

		state = 'enabled' if enabled else 'disabled'

		logging.info(f'Booster headless mode {state}')

		return {'success': True, 'headless_mode': enabled}
	except Exception as e:
		logging.error(f'booster_set_headless_mode error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def booster_stop():
	try:
		with locks['booster']:
			if not active_modules['booster']:
				return {'success': False, 'error': 'Booster is not running'}
			
			logging.info('Stopping Booster...')
			active_modules['booster'].stop()
			
			if active_modules['booster'].thread:
				active_modules['booster'].thread.join(timeout=10)
			
			active_modules['booster'] = None
			module_threads['booster'] = None
			
			return {'success': True}
			
	except Exception as e:
		logging.error(f'booster_stop error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def spinner_start():
	try:
		with locks['spinner']:
			if active_modules['spinner'] and active_modules['spinner'].is_running():
				return {'success': False, 'error': 'Spinner is already running'}

			stop_flags['spinner'].clear()

			spinner_instance = SpinnerMobile()

			if not spinner_instance.is_valid:
				return {'success': False, 'error': 'Spinner configuration is invalid'}

			spinner_instance._stop_event = stop_flags['spinner']

			original_log = spinner_instance.log

			def patched_log(msg_type, message):
				original_log(msg_type, message)

				with logs_lock:
					pending_logs['spinner'].append({'type': msg_type, 'message': message})

			spinner_instance.log = patched_log

			wrapper = ModuleWrapper(spinner_instance, 'spinner')
			active_modules['spinner'] = wrapper

			def run_spinner():
				try:
					logging.info('Spinner thread started')

					spinner_instance.run()

					logging.info('Spinner thread finished normally')
				except Exception as e:
					logging.error(f'Spinner error: {e}')
					logging.error(traceback.format_exc())
				finally:
					with logs_lock:
						pending_states['spinner'].append({'initialized': False, 'phase': 'Stopped', 'action': 'Idle'})

					with locks['spinner']:
						active_modules['spinner'] = None
						module_threads['spinner'] = None

			thread = threading.Thread(target=run_spinner, name='SpinnerThread', daemon=True)
			wrapper.thread = thread
			module_threads['spinner'] = thread

			with logs_lock:
				pending_states['spinner'].append({
					'initialized': True,
					'phase': 'Starting',
					'action': 'Initializing'
				})

			thread.start()

			_start_watchdog('spinner', thread)

			return {'success': True}
	except Exception as e:
		logging.error(f'spinner_start error: {e}')
		logging.error(traceback.format_exc())

		return {'success': False, 'error': str(e)}

@eel.expose
def spinner_adb_scan():
	try:
		from spinner import _adb_out, list_adb_devices, connect_wifi, _auto_setup_device

		serial = _auto_setup_device(None)

		if serial:
			return {'serial': serial, 'devices': []}

		devices = list_adb_devices()

		ready = [d for d in devices if d['state'] == 'device']

		return {'serial': None, 'devices': ready}
	except Exception as e:
		logging.error(f'spinner_adb_scan error: {e}')

		return {'serial': None, 'devices': [], 'error': str(e)}

@eel.expose
def spinner_adb_connect(host, port='5555'):
	try:
		from spinner import connect_wifi

		ok, msg = connect_wifi(host, int(port))

		if ok:
			return {'success': True}

		return {'success': False, 'error': msg}
	except Exception as e:
		return {'success': False, 'error': str(e)}

@eel.expose
def spinner_start_mobile(serial):
	try:
		with locks['spinner']:
			if active_modules['spinner'] and active_modules['spinner'].is_running():
				return {'success': False, 'error': 'Spinner is already running'}

			stop_flags['spinner'].clear()

			spinner_instance = SpinnerMobile()

			if not spinner_instance.is_valid:
				return {'success': False, 'error': 'Spinner configuration is invalid'}

			spinner_instance._stop_event = stop_flags['spinner']
			spinner_instance.serial = serial

			from spinner import get_screen_resolution

			try:
				spinner_instance.width, spinner_instance.height = get_screen_resolution(serial)
			except Exception:
				pass

			original_log = spinner_instance.log

			def patched_log(msg_type, message):
				original_log(msg_type, message)

				with logs_lock:
					pending_logs['spinner'].append({'type': msg_type, 'message': message})

			spinner_instance.log = patched_log

			import uiautomator2 as u2

			try:
				spinner_instance.d = u2.connect(serial)
				spinner_instance.d.info
			except Exception as e:
				return {'success': False, 'error': f'uiautomator2 connect failed: {e}'}

			wrapper = ModuleWrapper(spinner_instance, 'spinner')
			active_modules['spinner'] = wrapper

			def run_spinner():
				try:
					logging.info('SpinnerMobile thread started')

					while True:
						if stop_flags['spinner'].is_set():
							break

						if not spinner_instance.prepare():
							break

						result = spinner_instance.spin()

						if result == -1 or result == 1:
							break

						try:
							spinner_instance.d.app_stop('com.werewolfapps.online')
						except Exception:
							pass

						time.sleep(3)

					logging.info('SpinnerMobile thread finished')
				except Exception as e:
					logging.error(f'SpinnerMobile error: {e}')
					logging.error(traceback.format_exc())
				finally:
					with logs_lock:
						pending_states['spinner'].append({'initialized': False, 'phase': 'Stopped', 'action': 'Idle'})

					with locks['spinner']:
						active_modules['spinner'] = None
						module_threads['spinner'] = None

			thread = threading.Thread(target=run_spinner, name='SpinnerThread', daemon=True)
			wrapper.thread = thread
			module_threads['spinner'] = thread
			thread.start()

			_start_watchdog('spinner', thread)

			return {'success': True}
	except Exception as e:
		logging.error(f'spinner_start_mobile error: {e}')
		logging.error(traceback.format_exc())

		return {'success': False, 'error': str(e)}

@eel.expose
def spinner_stop():
	try:
		with locks['spinner']:
			if not active_modules['spinner']:
				return {'success': False, 'error': 'Spinner is not running'}
			
			logging.info('Stopping Spinner...')

			active_modules['spinner'].stop()
			
			if active_modules['spinner'].thread:
				active_modules['spinner'].thread.join(timeout=10)
			
			active_modules['spinner'] = None
			module_threads['spinner'] = None
			
			return {'success': True}
	except Exception as e:
		logging.error(f'spinner_stop error: {e}')

		return {'success': False, 'error': str(e)}

@eel.expose
def get_booster_data():
	with logs_lock:
		logs = pending_logs.get('booster', [])[:]
		states = pending_states.get('booster', [])[:]
		
		pending_logs['booster'] = []
		pending_states['booster'] = []
	
	return {
		'logs': logs,
		'states': states
	}

@eel.expose
def get_spinner_data():
	with logs_lock:
		logs = pending_logs.get('spinner', [])[:]
		states = pending_states.get('spinner', [])[:]
		
		pending_logs['spinner'] = []
		pending_states['spinner'] = []
	
	return {
		'logs': logs,
		'states': states
	}

@eel.expose
def get_pending_logs(module_name):
	with logs_lock:
		logs = pending_logs.get(module_name, [])[:]
		pending_logs[module_name] = []

	return logs

@eel.expose
def get_pending_states(module_name):
	with logs_lock:
		states = pending_states.get(module_name, [])[:]
		pending_states[module_name] = []

	return states

@eel.expose
def check_server_connection():
	try:
		config = dotenv_values('config.txt')

		if config.get('SERVER_SYNC_ENABLED', 'false').lower() != 'true':
			return {'connected': False, 'reason': 'disabled'}

		server_url = config.get('MENTALIST_SERVER_URL', '')
		api_key = config.get('MENTALIST_SERVER_API_KEY', '')
		r = requests.get(
			f'{server_url}/health',
			headers={'X-API-Key': api_key},
			timeout=5
		)

		if r.status_code == 200:
			d = r.json()

			return {
				'connected': True,
				'uptime': d.get('uptime_seconds'),
				'syncs': d.get('total_syncs')
			}

		return {'connected': False, 'reason': 'auth_failed'}
	except Exception:
		return {'connected': False, 'reason': 'offline'}

@eel.expose
def check_for_updates():
	global updater_instance

	if not updater_instance:
		updater_instance = EelUpdater(
			server_url=config.get('MENTALIST_SERVER_URL'),
			current_version=VERSION,
			api_key=config.get('MENTALIST_SERVER_API_KEY')
		)

	return updater_instance.check_for_updates_gui()

@eel.expose
def download_and_install_update(update_info):
	global updater_instance

	def update_thread():
		download_result = updater_instance.download_update_gui(update_info)

		if download_result.get('success'):
			updater_instance.apply_update_gui(download_result.get('file'), update_info)
	
	threading.Thread(target=update_thread, daemon=True).start()

	return {'success': True}

@eel.expose
def restart_application():
	if updater_instance:
		updater_instance.restart_application()

	return {'success': True}

@eel.expose
def update_progress(event_type, data):
	pass

def check_updates_on_startup():
	global updater_instance

	try:
		config = dotenv_values('config.txt')
		updater_instance = EelUpdater(
			server_url=config.get('MENTALIST_SERVER_URL'),
			current_version=VERSION,
			api_key=config.get('MENTALIST_SERVER_API_KEY')
		)
		
		def check_thread():
			time.sleep(2)
			
			update_available, info = updater_instance.check_for_updates(silent=True)
			
			try:
				if update_available:
					eel.notify_update_available(info)
			except AttributeError:
				pass
		
		threading.Thread(target=check_thread, daemon=True).start()
	except:
		pass

def main():
	os.system('cls' if os.name == 'nt' else 'clear')

	print(f'{Style.BRIGHT}{Fore.RED}{"=" * 60}{Fore.RESET}')
	print(f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist {Fore.CYAN}GUI{Fore.RESET}')
	print(f'{Style.BRIGHT}{Fore.MAGENTA}by Corruptor{Fore.RESET}')
	print(f'{Style.BRIGHT}{Fore.RED}{"=" * 60}{Fore.RESET}')
	print()

	check_updates_on_startup()
	
	sw, sh = 1920, 1080

	try:
		root = tk.Tk()
		root.withdraw()
		root.update_idletasks()
		sw = root.winfo_screenwidth()
		sh = root.winfo_screenheight()
		root.quit()
		root.destroy()
	except Exception as e:
		logging.error(f'Tkinter size detection failed: {e}')

	if sys.platform == 'darwin':
		sw += 100

	print(f'{Style.BRIGHT}{Fore.GREEN}Starting Mentalist GUI...{Fore.RESET}')
	print(f'{Style.BRIGHT}{Fore.CYAN}Screen Resolution: {sw}x{sh}{Fore.RESET}')
	print(f'{Style.BRIGHT}{Fore.CYAN}Window Size: {sw // 2}x{sh}{Fore.RESET}')
	print()

	eel_options = {
		'mode': 'chrome',
		'host': 'localhost',
		'port': 8080,
		'size': (sw // 2, sh),
		'position': (sw // 2, 0)
	}

	if pyi_splash:
		pyi_splash.close()

	try:
		eel.start('index.html', **eel_options)
	except (SystemExit, KeyboardInterrupt):
		print(f'\n{Style.BRIGHT}{Fore.YELLOW}Shutting down Mentalist GUI...{Fore.RESET}')
		
		sys.exit(0)


if __name__ == '__main__':
	main()
