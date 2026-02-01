from gevent import monkey
monkey.patch_socket()
monkey.patch_ssl()

import asyncio
import eel
import requests
import threading
import os
import sys
import re
import time
import logging
import traceback
import queue
import tkinter as tk
from colorama import Fore, Style, init
from dotenv import dotenv_values
from mentalist import Tracker, Stalker, Booster, Spinner
from updater import EelUpdater

try:
	log = logging.getLogger('geventwebsocket.handler')
	log.setLevel(logging.ERROR)
except:
	pass

logging.getLogger('eel').setLevel(logging.ERROR)
logging.basicConfig(level=logging.ERROR)
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s [%(threadName)s] %(message)s',
	handlers=[logging.StreamHandler(sys.stdout)]
)

init(autoreset=True)

eel.init('gui')

VERSION = '1.0.0'
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
	'booster': [],
	'spinner': [],
	'tracker': [],
	'stalker': []
}

pending_states = {
	'booster': [],
	'spinner': [],
	'tracker': [],
	'stalker': []
}

logs_lock = threading.Lock()


class ModuleWrapper:
	def __init__(self, module_instance, module_name):
		self.module = module_instance
		self.name = module_name
		self.thread = None
		self.stop_flag = stop_flags[module_name]
		self.playwright_context = None
		self.status = 'idle'
		self.status_message = ''

		self.log_message = lambda msg_type, message: logging.info(f"{self.name} [{msg_type}]: {message}")

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
					pending_states[module_name].append(state_entry)
			
			module_instance.log_state = new_log_state
		
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
		if os.name == 'nt':
			spinner = Spinner()

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
				wrapper.log_message('info', f"[{state.upper()}] {msg}")

			try:
				update_status('starting', 'Launching Browser...')
				
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

					try:
						tracker.page.goto('https://wolvesville.com', wait_until='commit', timeout=60000)
					except Exception as e:
						logging.warning(f'Navigation timeout (non-critical): {e}')

					while not tracker.check_stop_flag():
						if not tracker.page or tracker.page.is_closed():
							logging.warning('Browser closed externally.')

							break

						if tracker.prepare():
							logging.error('Tracker prepare failed.')

							break

						update_status('waiting_for_game', 'Waiting for game start...')

						game_started = False
						
						while not tracker.check_stop_flag() and not game_started:
							if not tracker.page or tracker.page.is_closed():
								break

							try:
								phase_locator = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div[1]/div/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
								phase_text = phase_locator.text_content(timeout=1000)

								if phase_text.isdigit() or \
									phase_text.startswith('Обсуждение') or \
									phase_text.startswith('Голосование') or \
									phase_text.enswith('s'):

									game_started = True
							except:
								pass
							
							if not game_started:
								time.sleep(1)
						
						if tracker.check_stop_flag():
							break

						if not tracker.page or tracker.page.is_closed():
							break

						update_status('scanning', 'Game found! Getting token...')
						
						try:
							tracker.get_bearer()
							
							if tracker.check_stop_flag(): break

							tracker.load_css()
							tracker.load_modal()
							
							update_status('scanning', 'Finding players...')
							tracker.find_players()
							
							update_status('scanning', 'Analyzing setup...')
							roles = tracker.find_roles()
							rotations = tracker.get_rotations()
							tracker.ROTATION = tracker.choose_rotation(rotations, roles)

							if tracker.ROTATION is None:
								logging.warning('Rotation not found (Custom game?), continuing with partial data...')
							
							update_status('running', 'Tracking Active')

							while not tracker.check_stop_flag():
								if not tracker.page or tracker.page.is_closed(): break
								
								try:
									tracker.update_players()
								except Exception as e:
									logging.debug(f'Update error: {e}')

								time.sleep(1.5)
						except Exception as e:
							logging.error(f'Game Loop Error: {e}')
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
				wrapper.safe_close_browser()

				with locks['tracker']:
					active_modules['tracker'] = None

				logging.info('Tracker thread finished.')

		thread = threading.Thread(target=run_tracker_logic, name='TrackerThread', daemon=True)
		module_threads['tracker'] = thread
		thread.start()

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
		'player_claims': {}
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

				has_rotation = hasattr(tracker, 'ROTATION') and tracker.ROTATION
				remaining = {'GOOD': [], 'EVIL': [], 'UNKNOWN': []}
				
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
							if i >= len(tracker.PLAYERS): break
							
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
									if isinstance(c, list): flatten_cards.extend(c)
									else: flatten_cards.append(c)

								icons = getattr(tracker, 'PLAYER_ICONS', {}).get(name, {})
								team = player_obj.get('team')
								aura = player_obj.get('aura')

								for role in tracker.ROTATION:
									if 'random' in role['id']: continue

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
def tracker_send_command(command):
	tracker_wrapper = active_modules.get('tracker')

	if not tracker_wrapper:
		return {'success': False, 'error': 'Tracker is not running'}
	
	tracker = tracker_wrapper.module

	try:
		with locks['tracker']:
			cmd = command.strip()

			if cmd.lower() == 'end':
				tracker.storm(hard=True)

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
def booster_start():
	try:
		with locks['booster']:
			if active_modules['booster'] and active_modules['booster'].is_running():
				return {'success': False, 'error': 'Booster is already running'}
			
			stop_flags['booster'].clear()
			
			booster_instance = Booster()
			
			if not booster_instance.is_valid:
				return {'success': False, 'error': 'Booster configuration is invalid'}

			booster_stop_flag = stop_flags['booster']

			def patched_check_stop():
				return booster_stop_flag.is_set()

			booster_instance.check_stop_flag = patched_check_stop
			
			wrapper = ModuleWrapper(booster_instance, 'booster')
			active_modules['booster'] = wrapper
			
			def run_booster():
				try:
					logging.info('Booster thread started')
					booster_instance.run()
					logging.info('Booster thread finished normally')
				except Exception as e:
					logging.error(f'Booster error: {e}')
					logging.error(traceback.format_exc())
				finally:
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

			import time as time_module

			time_module.sleep(0.1)
			
			return {'success': True}
	except Exception as e:
		logging.error(f'booster_start error: {e}')
		logging.error(traceback.format_exc())

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
			
			spinner_instance = Spinner()
			
			if not spinner_instance.is_valid:
				return {'success': False, 'error': 'Spinner configuration is invalid'}

			spinner_stop_flag = stop_flags['spinner']

			def patched_check_stop():
				return spinner_stop_flag.is_set()

			spinner_instance.check_stop_flag = patched_check_stop
			
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
					with locks['spinner']:
						if active_modules['spinner']:
							active_modules['spinner'].safe_close_browser()
			
			thread = threading.Thread(target=run_spinner, name='SpinnerThread', daemon=True)
			wrapper.thread = thread
			module_threads['spinner'] = thread
			thread.start()

			with logs_lock:
				pending_states['spinner'].append({
					'initialized': True,
					'phase': 'Starting',
					'action': 'Initializing'
				})

			return {'success': True}
			
	except Exception as e:
		logging.error(f'spinner_start error: {e}')
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
			updater_instance.apply_update_gui(download_result.get('file'))
	
	threading.Thread(target=update_thread, daemon=True).start()

	return {'success': True}

@eel.expose
def restart_application():
	if updater_instance:
		updater_instance.restart_application()

	return {'success': True}

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
			
			if update_available:
				eel.notify_update_available(info)
		
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

	try:
		eel.start('index.html', **eel_options)
	except (SystemExit, KeyboardInterrupt):
		print(f'\n{Style.BRIGHT}{Fore.YELLOW}Shutting down Mentalist GUI...{Fore.RESET}')
		
		sys.exit(0)


if __name__ == '__main__':
	main()
