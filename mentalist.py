import sys
from gevent import monkey

if sys.platform == 'darwin':
	monkey.patch_all(subprocess=False, thread=False, Event=False)

else:
	monkey.patch_all(subprocess=False)

import asyncio
import nest_asyncio
import eel
import requests
import threading
import subprocess
import pyautogui
import pywinauto
import pygetwindow
import hashlib
import psutil
import shutil
import ntplib
import json
import os
import re
import dateutil
import pytz
import time
import random
import uuid
import inspect
from undetected_playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from collections import OrderedDict
from copy import deepcopy
from itertools import combinations
from functools import lru_cache
from playsound3 import playsound
from tzlocal import get_localzone
from datetime import datetime, timedelta
from colorama import Back, Fore, Style, init
from dotenv import dotenv_values
from path import Path
from auth_decorator import require_module_auth
from auth_protection import _integrity_checker
from data_protection import save_encrypted, load_encrypted
from updater import MentalistUpdater

init(autoreset=True)

requests.packages.urllib3.disable_warnings()

VERSION = '1.0.0'
MACOS_DISABLE_PLAYWRIGHT_THREADING = (sys.platform == 'darwin')


def find_chrome_executable():
	if sys.platform == 'win32':
		try:
			import winreg

			key = winreg.OpenKey(
				winreg.HKEY_LOCAL_MACHINE, 
				r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe'
			)
			chrome_path, _ = winreg.QueryValueEx(key, '')
			winreg.CloseKey(key)
			
			if os.path.exists(chrome_path):
				return chrome_path
		except:
			pass

	possible_paths = []
	
	if sys.platform == 'win32':
		possible_paths = [
			r'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
			r'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
			os.path.expandvars(r'%LOCALAPPDATA%\\Google\\Chrome\\Application\\chrome.exe'),
			os.path.expandvars(r'%PROGRAMFILES%\\Google\\Chrome\\Application\\chrome.exe'),
			os.path.expandvars(r'%PROGRAMFILES(X86)%\\Google\\Chrome\\Application\\chrome.exe'),
		]

	elif sys.platform == 'darwin':
		possible_paths = [
			'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
			os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
		]

	else:
		possible_paths = [
			'/usr/bin/google-chrome',
			'/usr/bin/chromium',
			'/usr/bin/chromium-browser',
			'/snap/bin/chromium',
		]

	for path in possible_paths:
		if os.path.exists(path):
			return path

	if sys.platform != 'win32':
		try:
			chrome = shutil.which('google-chrome') or shutil.which('chromium')

			if chrome:
				return chrome
		except:
			pass

def generate_random_user_agent(device_type=None, browser_type=None, chrome_versions=[125, 138], firefox_versions=[120, 135]):
	if not device_type:
		device_type = random.choice(['android', 'ios', 'windows', 'ubuntu'])

	if not browser_type:
		browser_type = random.choice(['chrome', 'firefox'])

	if browser_type == 'chrome':
		chrome_versions = list(range(chrome_versions[0], chrome_versions[1]))
		major_version = random.choice(chrome_versions)
		minor_version = random.randint(0, 9)
		build_version = random.randint(1000, 9999)
		patch_version = random.randint(0, 99)
		browser_version = f'{major_version}.{minor_version}.{build_version}.{patch_version}'
	
	elif browser_type == 'firefox':
		firefox_versions = list(range(firefox_versions[0], firefox_versions[1]))
		browser_version = random.choice(firefox_versions)

	if device_type == 'android':
		android_versions = ['10.0', '11.0', '12.0', '13.0', '14.0', '15.0', '16.0']
		android_device = random.choice([
			'SM-G960F', 'Pixel 5', 'SM-A505F', 'Pixel 4a', 'Pixel 6 Pro', 'SM-N975F',
			'SM-G973F', 'Pixel 3', 'SM-G980F', 'Pixel 5a', 'SM-G998B', 'Pixel 4',
			'SM-G991B', 'SM-G996B', 'SM-F711B', 'SM-F916B', 'SM-G781B', 'SM-N986B',
			'SM-N981B', 'Pixel 2', 'Pixel 2 XL', 'Pixel 3 XL', 'Pixel 4 XL',
			'Pixel 5 XL', 'Pixel 6', 'Pixel 6 XL', 'Pixel 6a', 'Pixel 7', 'Pixel 7 Pro',
			'OnePlus 8', 'OnePlus 8 Pro', 'OnePlus 9', 'OnePlus 9 Pro', 'OnePlus Nord', 'OnePlus Nord 2', 'OnePlus Nord CE', 'OnePlus 10', 'OnePlus 10 Pro', 'OnePlus 10T', 'OnePlus 10T Pro',
			'Xiaomi Mi 9', 'Xiaomi Mi 10', 'Xiaomi Mi 11', 'Xiaomi Redmi Note 8', 'Xiaomi Redmi Note 9',
			'Huawei P30', 'Huawei P40', 'Huawei Mate 30', 'Huawei Mate 40', 'Sony Xperia 1',
			'Sony Xperia 5', 'LG G8', 'LG V50', 'LG V60', 'Nokia 8.3', 'Nokia 9 PureView'
		])

		android_version = random.choice(android_versions)
		
		if browser_type == 'chrome':
			return f'Mozilla/5.0 (Linux; Android {android_version}; {android_device}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Mobile Safari/537.36'
		
		elif browser_type == 'firefox':
			return f'Mozilla/5.0 (Android {android_version}; Mobile; rv:{browser_version}.0) Gecko/{browser_version}.0 Firefox/{browser_version}.0'

	elif device_type == 'ios':
		ios_versions = ['13.0', '14.0', '15.0', '16.0']
		ios_device = random.choice([
			'iPhone X', 'iPhone 11', 'iPhone 12', 'iPhone 13', 'iPad Pro', 'iPad Mini'
		])
		
		ios_version = random.choice(ios_versions)
		
		if browser_type == 'chrome':
			return f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_version.replace(".", "_")} like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) CriOS/{browser_version} Mobile/15E148 Safari/604.1'
		
		elif browser_type == 'firefox':
			return f'Mozilla/5.0 (iPhone; CPU iPhone OS {ios_version.replace(".", "_")} like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/{browser_version}.0 Mobile/15E148 Safari/605.1.15'

	elif device_type == 'windows':
		windows_versions = ['10.0', '11.0']
		windows_version = random.choice(windows_versions)
		
		if browser_type == 'chrome':
			return f'Mozilla/5.0 (Windows NT {windows_version}; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36'
		
		elif browser_type == 'firefox':
			return f'Mozilla/5.0 (Windows NT {windows_version}; Win64; x64; rv:{browser_version}.0) Gecko/{browser_version}.0 Firefox/{browser_version}.0'

	elif device_type == 'ubuntu':
		ubuntu_versions = ['20.04', '22.04']
		ubuntu_version = random.choice(ubuntu_versions)
		
		if browser_type == 'chrome':
			return f'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:94.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{browser_version} Safari/537.36'
		
		elif browser_type == 'firefox':
			return f'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:{browser_version}.0) Gecko/{browser_version}.0 Firefox/{browser_version}.0'

def get_executable_path():
	if getattr(sys, 'frozen', False):
		return os.path.dirname(sys.executable)

	return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path):
	try:
		base_path = sys._MEIPASS
	except:
		base_path = os.path.abspath('.')

	return os.path.join(base_path, relative_path)


BASE_DIR = get_executable_path()
MENTALIST_DATA_DIR = Path(os.path.join(BASE_DIR, '.mentalist_data'))
USER_DATA_DIR = Path(os.path.join(BASE_DIR, '.user_data'))


class GameState:
	def __init__(self, tracker):
		self.players = []

		for p_template in deepcopy(tracker.PLAYERS):
			player = {
				'name': p_template.get('name'),
				'role': p_template.get('role'),
				'team': p_template.get('team'),
				'dead': p_template.get('dead', False),
				'abilities_used': {},
				'protected': 0,
				'blocked': False,
				'jailed': False,
				'doused': False,
				'wounded': False,
				'lover': None,
				'marked_by_marksman': False,
				'recruits': [],
				'is_accomplice': False
			}

			self.players.append(player)

		self.rotation = tracker.ROTATION
		self.pending_effects = []


class Mastermind:
	def __init__(self, tracker):
		self.tracker = tracker
		self.profiles = self.load_profiles()
		self.action_history = []
		self.update_state()

	def load_profiles(self):
		if not os.path.isdir(MENTALIST_DATA_DIR):
			os.mkdir(MENTALIST_DATA_DIR)

		local_profiles = load_encrypted('role_profiles') or {}
		
		if not local_profiles:
			print(f'{Style.BRIGHT}{Back.YELLOW}Local role profiles not found. Trying Mentalist Server...{Back.RESET}')
		
		if self.tracker.SERVER_ENABLED:
			if not self.tracker.auth_client.check_module_permission('mastermind'):
				print(f'{Style.BRIGHT}{Back.RED}Mastermind module not available - upgrade your subscription{Back.RESET}')
				
				return {}

			success, server_profiles = self.tracker.sync_with_server(
				'role_profiles',
				local_profiles,
				bidirectional=False
			)
			
			if success and server_profiles:
				try:
					save_encrypted('role_profiles', server_profiles)

					print(f'{Style.BRIGHT}{Fore.GREEN}Role profiles synced from Mentalist Server!{Fore.RESET}')
					
					return server_profiles
				except Exception as e:
					print(f'{Style.BRIGHT}{Fore.YELLOW}Could not save profiles: {e}{Fore.RESET}')

					return server_profiles
		
		if not local_profiles:
			print(f'{Style.BRIGHT}{Back.RED}Role profiles not found!{Back.RESET}')
		
		return local_profiles

	def update_state(self):
		self.state = GameState(self.tracker)
		self.initialize_special_roles(self.state)
		self.action_history = []

	def initialize_special_roles(self, state):
		pass

	def get_role_strategic_value(self, role_id):
		if not role_id:
			return 5

		role_profile = self.profiles.get(role_id)

		if role_profile and 'strategic_value' in role_profile:
			return role_profile['strategic_value']
		
		team_map = {
			'VILLAGER': 10,
			'WEREWOLF': -15,
			'SOLO': -10
		}
		
		role_data = self.tracker.ROLES.get(role_id)
		
		if role_data and role_data.get('team') in team_map:
			return team_map[role_data.get('team')]

		return 5

	def calculate_lynch_scores(self, state):
		scores = {}
		original_players = {p['name']: p for p in self.tracker.PLAYERS}
		living_players = [p for p in state.players if not p['dead']]
		
		for player in living_players:
			score = 100.0
			
			player_data = original_players.get(player['name'])

			if not player_data:
				scores[player['name']] = score

				continue

			known_role = player.get('role')
			known_team = player_data.get('team')
			known_aura = player_data.get('aura')

			if known_role and self.tracker.ROLES.get(known_role):
				role_info = self.tracker.ROLES.get(known_role)
				role_team = role_info.get('team')

				if role_team == 'VILLAGER':
					score *= 0.1

				elif role_team == 'SOLO':
					score *= 5

				elif role_team == 'WEREWOLF':
					score *= 10.0
			
			elif known_team:
				if known_team == 'VILLAGER':
					score *= 0.2

				elif known_team == 'SOLO':
					score *= 2.5

				elif known_team == 'WEREWOLF':
					score *= 10.0

			elif known_aura:
				if known_aura == 'GOOD':
					score *= 0.3

				elif known_aura == 'UNKNOWN':
					score *= 1.5

				elif known_aura == 'EVIL':
					score *= 10.0

			msg_count = len(player_data.get('messages', []))

			if msg_count <= 2:
				score *= 1.5

			elif msg_count > 10:
				score *= 0.8

			mention_count = len(player_data.get('mentions', []))

			score *= (1 + (mention_count * 0.25))

			scores[player['name']] = max(1, score)
			
		return scores

	def calculate_target_priority_scores(self, actor, ability, state, lynch_scores):
		scores = {}
		ability_type = ability.get('type', '')
		
		for player in state.players:
			if player['dead']:
				continue

			name = player['name']
			base_suspicion = lynch_scores.get(name, 100)
			strategic_value = self.get_role_strategic_value(player['role'])

			if 'kill' in ability_type or 'douse' in ability_type:
				if strategic_value > 0:
					scores[name] = strategic_value * 2 + base_suspicion

				else:
					scores[name] = base_suspicion * 0.1
			
			elif 'protect' in ability_type:
				if strategic_value > 0:
					scores[name] = strategic_value * 2 + (200 - base_suspicion)
				
				else:
					scores[name] = 0
			
			elif 'investigate' in ability_type or 'check' in ability_type:
				if player['role']:
					scores[name] = 0

				else:
					scores[name] = base_suspicion

			else:
				scores[name] = base_suspicion

		return scores

	@lru_cache(maxsize=2048)
	def get_possible_actions(self, state_tuple):
		state = self.tuple_to_state(state_tuple)
		all_actions = []
		
		alive_players = [p for p in state.players if not p['dead']]
		lynch_scores = self.calculate_lynch_scores(state)

		for player in alive_players:
			if not player['role'] or player.get('blocked') or player.get('jailed'):
				continue
			
			role_abilities = self.profiles.get(player['role'], {}).get('abilities', [])

			for ability in role_abilities:
				if self.is_ability_valid(player, ability, state):
					potential_targets = self.get_potential_targets(player, ability.get('targets', {}), state)
					
					if potential_targets:
						max_t = ability.get('max_targets', 1)
						
						TARGET_LIMIT = 5

						if len(potential_targets) > TARGET_LIMIT:
							priority_scores = self.calculate_target_priority_scores(player, ability, state, lynch_scores)
							sorted_targets = sorted(potential_targets, key=lambda p: priority_scores.get(p['name'], 0), reverse=True)
							interesting_targets = sorted_targets[:TARGET_LIMIT]
						
						else:
							interesting_targets = potential_targets

						for k in range(1, max_t + 1):
							if len(interesting_targets) < k:
								continue
							
							for target_combo in combinations(interesting_targets, k):
								final_target = target_combo[0] if len(target_combo) == 1 else target_combo
								
								all_actions.append({
									'actor': player,
									'ability': ability,
									'target': final_target
								})

					elif ability.get('max_targets', 1) == 0:
						all_actions.append({
							'actor': player,
							'ability': ability,
							'target': None
						})

		total_score = sum(lynch_scores.values())
		no_lynch_score = total_score * 0.15
		total_score_with_no_lynch = total_score + no_lynch_score

		if total_score_with_no_lynch > 0:
			living_players_map = {p['name']: p for p in alive_players}

			for name, score in lynch_scores.items():
				prob = score / total_score_with_no_lynch

				if prob > 0:
					target_player = living_players_map.get(name)
					all_actions.append({
						'actor': {
							'name': 'Village',
							'role': 'vote'
						},
						'ability': {
							'description': f'Lynch {name}',
							'type': 'lynch',
							'base_prob': prob
						},
						'target': target_player
					})
			
			no_lynch_prob = no_lynch_score / total_score_with_no_lynch
			all_actions.append({
				'actor': {
					'name': 'Village',
					'role': 'vote'
				},
				'ability': {
					'description': 'No Lynch',
					'type': 'no_lynch',
					'base_prob': no_lynch_prob
				},
				'target': None
			})

		return all_actions

	def is_ability_valid(self, player, ability, state):
		uses = player.get('abilities_used', {}).get(ability.get('type'), 0)

		if uses >= ability.get('max_uses', 1):
			return 0

		ability_type = ability.get('type')

		if player['role'] == 'instigator' and ability_type == 'kill':
			alive_recruits = [p for name in player.get('recruits', []) for p in state.players if p['name'] == name and not p['dead']]

			if alive_recruits:
				return 0

		if player['role'] == 'marksman' and ability_type == 'kill':
			return player.get('marked_by_marksman', False)

		return 1

	def get_potential_targets(self, actor, constraints, state):
		targets = []

		for player in state.players:
			if player['name'] == actor['name'] and not constraints.get('can_target_self', False):
				continue

			valid = True

			for key, val in constraints.items():
				if key == 'status' and player['dead'] != val:
					valid = False; break

				if key == 'team' and player.get('team') != val:
					valid = False; break

				if key == 'is_doused' and not player.get('doused'):
					valid = False; break

			if valid:
				targets.append(player)

		return targets

	def get_action_signature(self, action):
			actor_name = action['actor']['name']
			ability_type = action['ability'].get('type')

			target = action.get('target')
			target_signature = None

			if isinstance(target, dict):
				target_signature = target['name'] or ''

			elif isinstance(target, tuple):
				target_signature = tuple(sorted([t['name'] or '' for t in target]))
				
			return (actor_name, ability_type, target_signature)

	def predict(self, max_depth=3, prob_threshold=0.01, player_name=None):
		if _integrity_checker.get_corruption_handler().is_phantom_mode():
			fake_scenarios = []
			for _ in range(3):
				fake_scenarios.append({
					'state_tuple': (),
					'prob': random.random(),
					'path': [], 
					'score': random.randint(10, 100),
					'path_signature_set': set()
				})

			return fake_scenarios

		initial_state_tuple = self.state_to_tuple(self.state)

		scenarios = [{
			'state_tuple': initial_state_tuple,
			'prob': 1.0,
			'path': [],
			'score': 0,
			'path_signature_set': set()
		}]
		final_scenarios = []

		for depth in range(max_depth):
			next_scenarios = []

			if not scenarios:
				break

			for scenario in scenarios:
				possible_actions = self.get_possible_actions(scenario['state_tuple'])

				if not possible_actions:
					final_scenarios.append(scenario)

					continue

				for action in possible_actions:
					action_signature = self.get_action_signature(action)

					if action_signature in scenario['path_signature_set']:
						continue

					new_scenario = self.apply_action(scenario, action, action_signature)
					next_scenarios.append(new_scenario)
			
			scenarios = self.prune_scenarios(next_scenarios, prob_threshold)

		final_scenarios.extend(scenarios)

		for s in final_scenarios:
			s['state_obj'] = self.tuple_to_state(s['state_tuple'])

		def get_sort_key(scenario):
			score = scenario.get('score', 0)

			if player_name and scenario['path']:
				last_action = scenario['path'][-1]
				target_in_action = last_action.get('target')
				is_involved = False

				if target_in_action:
					if isinstance(target_in_action, tuple):
						is_involved = any(t['name'] == player_name for t in target_in_action)

					else:
						is_involved = target_in_action['name'] == player_name
				
				if is_involved or last_action['actor']['name'] == player_name:
					score *= 2.0
			
			return score

		return sorted(final_scenarios, key=get_sort_key, reverse=True)

	def check_vengeance_deaths(self, state, dead_player=None):
		if not dead_player:
			return

		dead_player_name = dead_player['name']
		target_to_kill = next((p for p in state.players if p.get('marked_to_die_with') == dead_player_name and not p['dead']), None)
		
		if target_to_kill:
			target_to_kill['dead'] = True

			self.check_lover_deaths(state, dead_player=target_to_kill)

	def apply_action(self, scenario, action, action_signature):
		state = self.tuple_to_state(scenario['state_tuple'])
		new_path = scenario['path'] + [action]
		ability = action['ability']
		prob = ability.get('base_prob', 0.8)
		actor_name = action['actor']['name']

		if actor_name == 'Village':
			actor = None

		else:
			actor = next((p for p in state.players if p['name'] == actor_name), None)

		if actor_name != 'Village' and not actor:
			return scenario

		action_target = action['target']
		targets_to_process = []

		if isinstance(action_target, tuple):
			targets_to_process.extend(action_target)

		elif action_target:
			targets_to_process.append(action_target)
		
		if actor:
			ability_type = ability.get('type')
			uses = actor['abilities_used'].get(ability_type, 0)
			actor['abilities_used'][ability_type] = uses + 1

		for target_data in targets_to_process:
			target = next((p for p in state.players if p['name'] == target_data['name']), None)
			
			if not target:
				continue
			
			ability_type = ability.get('type')

			if ability_type == 'lynch':
				target['dead'] = True

				self.check_lover_deaths(state, dead_player=target)
				self.check_vengeance_deaths(state, dead_player=target)

			elif ability_type == 'jail':
				target['jailed'] = True

			elif ability_type in {'mark_for_vengeance', 'tag'}:
				for p in state.players:
					if p.get('marked_to_die_with') == actor['name']:
						del p['marked_to_die_with']

				target['marked_to_die_with'] = actor['name']

			elif 'kill' in ability_type:
				immune_roles = {
					'arsonist', 'serial-killer', 'corruptor', 'bandit', 'werewolf'
				}

				is_killer_vs_killer = (actor and actor.get('team') == 'WEREWOLF' and target.get('role') in immune_roles) or \
									  (actor and actor.get('role') in immune_roles and target.get('team') == 'WEREWOLF')

				if is_killer_vs_killer:
					pass

				elif target['role'] == 'stubborn-werewolf' and not target.get('wounded'):
					target['wounded'] = True

				elif target['protected'] < 1:
					target['dead'] = True

					self.check_lover_deaths(state, dead_player=target)
					self.check_vengeance_deaths(state, dead_player=target)

				else:
					target['protected'] -= 1

			elif ability_type == 'protect':
				target['protected'] += 1

			elif ability_type in {'block', 'mute'}:
				target['blocked'] = True

			elif ability_type == 'douse':
				target['doused'] = True

			elif ability_type == 'convert' and actor:
				if target['team'] == 'VILLAGER':
					target['team'] = actor['team']
					target['is_accomplice'] = True

				elif target['team'] == 'WEREWOLF':
					target['dead'] = True

			elif ability_type == 'zombie_bite':
				state.pending_effects.append({
					'type': 'zombie_conversion',
					'target': target['name'],
					'delay': 2
				})

		ability_type_no_target = ability.get('type')

		if ability_type_no_target == 'no_lynch':
			pass

		elif ability_type_no_target == 'reveal_mayor' and actor:
			actor['revealed_mayor'] = True

		elif ability_type_no_target == 'reveal_and_pacify':
			pass

		elif ability_type_no_target == 'ignite':
			for p in state.players:
				if p.get('doused'):
					if p.get('protected') < 1:
						p['dead'] = True

					else:
						p['protected'] -= 1

					p['doused'] = False

		win_metric = self.calculate_win_metric(state)
		current_prob = scenario['prob'] * prob
		score = current_prob * win_metric

		new_signature_set = scenario['path_signature_set'].copy()
		new_signature_set.add(action_signature)

		return {
			'state_tuple': self.state_to_tuple(state),
			'prob': current_prob,
			'path': new_path,
			'score': score,
			'path_signature_set': new_signature_set
		}
	
	def check_lover_deaths(self, state, dead_player=None):
		if dead_player and dead_player.get('lover'):
			lover_name = dead_player['lover']
			lover_player = next((p for p in state.players if p['name'] == lover_name and not p['dead']), None)

			if lover_player:
				lover_player['dead'] = True

				self.check_lover_deaths(state, dead_player=lover_player)
				self.check_vengeance_deaths(state, dead_player=target)

	def process_pending_effects(self, state):
		remaining_effects = []

		for effect in state.pending_effects:
			effect['delay'] -= 1

			if effect['delay'] <= 0:
				target = next((p for p in state.players if p['name'] == effect['target']), None)

				if target:
					if effect['type'] == 'zombie_conversion':
						target['team'] = 'ZOMBIE'

					elif effect['type'] == 'corruptor_kill':
						target['dead'] = True

			else:
				remaining_effects.append(effect)

		state.pending_effects = remaining_effects

	def prune_scenarios(self, scenarios, threshold):
		if not scenarios: 
			return []
		
		BEAM_WIDTH = 25 

		sorted_scenarios = sorted(scenarios, key=lambda x: x.get('score', 0), reverse=True)
		
		return sorted_scenarios[:BEAM_WIDTH]

	def calculate_win_metric(self, state):
		alive = [p for p in state.players if not p['dead']]

		if not alive:
			return 0.0

		teams = [p.get('team') for p in alive]

		villager_count = teams.count('VILLAGER')
		werewolf_count = teams.count('WEREWOLF')
		
		if werewolf_count == 0:
			return villager_count / len(alive)

		if villager_count <= werewolf_count:
			return werewolf_count / len(alive)

		return 0.5

	def optimize_strategy(self, scenarios):
		if not scenarios:
			return {'action': None, 'expected_success': 0}

		best_scenario = max(scenarios, key=lambda x: x['prob'] * self.calculate_win_metric(x['state_obj']))
		first_action = best_scenario['path'][0] if best_scenario['path'] else None

		return {
			'action': first_action,
			'expected_success': self.calculate_win_metric(best_scenario['state_obj'])
		}

	def tuple_to_state(self, state_tuple):
		players_list = []

		for p_tuple in state_tuple[0]:
			player_dict = dict(p_tuple)
			
			if 'abilities_used' in player_dict:
				player_dict['abilities_used'] = dict(player_dict['abilities_used'])
			
			players_list.append(player_dict)
		
		state = GameState(self.tracker)
		state.players = players_list
		state.rotation = [dict(r) for r in state_tuple[1]]
		state.pending_effects = [dict(e) for e in state_tuple[2]]

		return state

	def state_to_tuple(self, state):
		player_tuples = []
		sorted_players = sorted(state.players, key=lambda x: x.get('name') or '')

		for p in sorted_players:
			def sanitize(val):
				if isinstance(val, set):
					return frozenset(val)

				if isinstance(val, list):
					return tuple(val)

				if isinstance(val, dict):
					return tuple(sorted(val.items()))

				return val

			items_tuple = tuple((k, sanitize(v)) for k, v in sorted(p.items()))
			player_tuples.append(items_tuple)
		
		players_tuple = tuple(player_tuples)
		rotation_tuple = tuple(tuple(sorted(role.items())) for role in state.rotation)
		pending_effects_tuple = tuple(tuple(sorted(effect.items())) for effect in state.pending_effects)
		
		return (players_tuple, rotation_tuple, pending_effects_tuple)


class Tracker:
	@require_module_auth('tracker')
	def __init__(self):
		self.config = dotenv_values('config.txt')
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

		self.CHROME_USER_DATA = USER_DATA_DIR / 'Mentalist'

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

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.page = None
		self.day_chat = None
		self.dead_chat = None
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
	
	def _check_phantom_mode(self):
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

	def get_bearer(self):
		self.BEARER_TOKEN = self.page.evaluate('() => JSON.parse(localStorage.getItem("authtokens"))["idToken"]')
		self.CF_JWT = self.page.evaluate('() => localStorage.getItem("cloudflare-turnstile-jwt")')

		self.BEARER_HEADERS = {
			'Authorization': f'Bearer {self.BEARER_TOKEN}',
			'Cf-Jwt': f'{self.CF_JWT}',
			'Ids': '1'
		}


		if hasattr(self, 'auth_client'):
			try:
				self.auth_client.update_tokens(
					bearer_token=self.BEARER_TOKEN,
					tracker_keys=self.API_KEYS
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

		if self._check_phantom_mode():
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
				endpoint = f'{self.SERVER_URL}/sync/{data_type}'
				payload = {
					'data': local_data,
					'hash': current_hash
				}
				
				response = requests.post(
					endpoint,
					json=payload,
					headers=headers,
					timeout=self.SERVER_TIMEOUT
				)

			else:
				endpoint = f'{self.SERVER_URL}/sync/{data_type}?hash={current_hash}'
				response = requests.get(
					endpoint,
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
			input(f'{Style.BRIGHT}{Back.RED}{path} not found!{Back.RESET}')

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

		field = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]')

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
	
	def write_cards(self, player, cards):
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
	
	def write_icons(self, player, icons):
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

		self.find_players()

		if not hard:
			old_players_dict = {old['name']: old for old in PLAYERS_OLD}

			for p in range(16):
				player_name = self.PLAYERS[p]['name']

				if player_name in old_players_dict:
					self.PLAYERS[p] = old_players_dict[player_name]

	def revert(self, action):
		if not self.PREV_PLAYERS:
			input(f'\n{Style.BRIGHT}{Back.RED}Last revert reached!{Back.RESET}')

		else:
			self.PLAYERS = deepcopy(self.PREV_PLAYERS[-1])

			if action:
				self.PREV_PLAYERS.pop()

		return -1

	def set_name(self, player, name, threaded=False):
		data = self.get_player(name)

		if data[0] == 404:
			input(f'\n{Style.BRIGHT}{Back.RED}Invalid name!{Back.RESET}')

			return 404

		elif data[0]:
			input(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

			return data[0]

		level, min_level, cards, icons = data[1:]

		self.PLAYERS[player]['name'] = name

		if self.PLAYERS[player]['hero']:
			return

		self.PLAYERS[player]['level'] = level
		self.PLAYERS[player]['min_level'] = min_level

		self.write_cards(name, cards)
		self.write_icons(name, icons)

		role = self.PLAYERS[player]['role']

		if role and role not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if role in self.ADVANCED_ROLES[src_role]:
					self.write_cards(name, {src_role: role})

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

			self.write_cards(name, {src_role: role_id})
			self.save_cards()

		if role_id in self.ROTATION_ICONS:
			self.write_icons(name, {role_id: self.ROTATION_ICONS[role_id]})
			self.save_icons()

	def change_role(self, src_role, dst_role):
		is_random = False

		for role in self.ROLES:
			if self.ROLES[role]['name'].lower() == dst_role.lower():
				dst_role = self.ROLES[role]
				dst_role['id'] = role

				break

		else:
			input(f'\n{Style.BRIGHT}{Back.RED}Incorrect destination role!{Back.RESET}')

			return

		for r, role in enumerate(self.ROTATION):
			if role['name'].lower() == src_role.lower():
				src_role = role['id']

				if 'random' in src_role:
					is_random = True

				break

		else:
			input(f'\n{Style.BRIGHT}{Back.RED}Incorrect source role!{Back.RESET}')

			return

		self.ROTATION[r] = dst_role
		self.ROTATION[r]['id'] = dst_role['id']

		for p, player in enumerate(self.PLAYERS):
			if self.PLAYERS[p]['role'] == src_role:
				self.PLAYERS[p]['role'] = dst_role['id']
				self.PLAYERS[p]['team'] = dst_role['team']
				self.PLAYERS[p]['aura'] = dst_role['aura']

				if player['name'] and not player['hero'] and not is_random and dst_role['id'] not in self.ADVANCED_ROLES:
					self.write_cards(player['name'], {src_role: dst_role['id']})

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
			input(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

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
				input(f'\n{Style.BRIGHT}{Back.RED}Incorrect info!{Back.RESET}')

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
					
					if not target: continue
					
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

	def parse_chat_messages(self, player_messages):
		claim_patterns = {
			'role_claim_self': re.compile(r"^(?:i am|im|iam|my role is) ([\w\-]+)"),
			'player_is_role': re.compile(r"(\d{1,2}) is ([\w\-]+)"),
			'seer_check': re.compile(r"^(?:seer on|check on) (\d{1,2}) is (good|evil|unknown)"),
			'doctor_protection': re.compile(r"^(?:doc on|protecting) (\d{1,2})")
		}
		
		unique_claims = {}

		self.PLAYER_ALLIANCES = {}

		for p in self.PLAYERS:
			if 'contradiction' in p:
				del p['contradiction']

		for msg_text in player_messages:
			try:
				player_num_str, message = msg_text.split(': ', 1)
				player_name = player_num_str.split(' ', 1)[1]
			except (ValueError, IndexError):
				continue

			message_lower = message.lower()
			
			for claim_type, pattern in claim_patterns.items():
				match = pattern.search(message_lower)

				if not match:
					continue

				if claim_type == 'role_claim_self':
					claimed_role = match.group(1)

					if player_name not in self.PLAYER_CLAIMS:
						self.PLAYER_CLAIMS[player_name] = {}

					self.PLAYER_CLAIMS[player_name]['role'] = claimed_role

				elif claim_type == 'player_is_role':
					target_num, claimed_role = int(match.group(1)) - 1, match.group(2)

					if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
						target_name = self.PLAYERS[target_num]['name']

						if target_name not in self.PLAYER_CLAIMS:
							self.PLAYER_CLAIMS[target_name] = {}

						self.PLAYER_CLAIMS[target_name]['role'] = claimed_role
						self.PLAYER_CLAIMS[target_name]['claimed_by'] = player_name
				
				elif claim_type == 'seer_check':
					target_num, aura = int(match.group(1)) - 1, match.group(2).upper()

					if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
						self.PLAYERS[target_num]['aura'] = aura

						if player_name not in self.PLAYER_CLAIMS:
							self.PLAYER_CLAIMS[player_name] = {}

						if 'seer_checks' not in self.PLAYER_CLAIMS[player_name]:
							self.PLAYER_CLAIMS[player_name]['seer_checks'] = {}

						self.PLAYER_CLAIMS[player_name]['seer_checks'][target_num + 1] = aura

				elif claim_type == 'doctor_protection':
					target_num = int(match.group(1)) - 1

					if 0 <= target_num < 16 and self.PLAYERS[target_num]['name']:
						target_name = self.PLAYERS[target_num]['name']

						if player_name not in self.PLAYER_ALLIANCES:
							self.PLAYER_ALLIANCES[player_name] = {}

						self.PLAYER_ALLIANCES[player_name][target_name] = self.PLAYER_ALLIANCES[player_name].get(target_name, 0) + 1

		unique_role_ids = {
			'seer', 'jailer', 'fool', 'arsonist', 'serial-killer', 'mayor', 'alpha-werewolf', 'aura-seer', 'detective'
		}

		for player_name, claim_data in self.PLAYER_CLAIMS.items():
			role = claim_data.get('role')

			if role in unique_role_ids:
				if role in unique_claims:
					original_claimer_name = unique_claims[role]

					for p in self.PLAYERS:
						if p['name'] in [player_name, original_claimer_name]:
							p['contradiction'] = role

				else:
					unique_claims[role] = player_name

	def update_players(self):
		updates = 0

		service_messages = []
		player_messages = []

		for chat in (self.day_chat, self.dead_chat):
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
							blocks = messages[m].querySelectorAll("div > span");

							if (!blocks.length || blocks.length >= 3) service_messages.push(messages[m].textContent);
							else player_messages.push(messages[m].textContent);
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

		if len(service_messages):
			if len(self.PREV_PLAYERS) == 3:
				self.PREV_PLAYERS.pop(0)

			self.PREV_PLAYERS.append(deepcopy(self.PLAYERS))

		for service_message in service_messages:
			player = None
			number = None
			name = None
			role = None
			dead = True

			if 'монстра' in service_message:
				continue

			if 'убил' in service_message:
				if 'дождь' in service_message:
					player = service_message.split(' дождь на ')[1].split(' и убил его.')[0]

				elif 'воду' in service_message:
					if 'себя' in service_message:
						players = service_message.split(' кинул святую воду в ')

						for p in range(2):
							number = int(players[p].split(' ')[0]) - 1
							name = players[p].split(' ')[1]	

							if '/' in players[p]:
								role = players[p].split(' / ')[1].split(')')[0]

							else:
								role = None

							self.set_name(number, name)
							self.PLAYERS[number]['dead'] = not p

							if role:
								self.set_role(number, role)

					else:
						players = service_message.split(' кинул святую воду и убил ')

						for p in range(2):
							number = int(players[p].split(' ')[0]) - 1
							name = players[p].split(' ')[1]	

							if '/' in players[p]:
								role = players[p].split(' / ')[1].split(')')[0]

							else:
								role = None

							self.set_name(number, name)
							self.PLAYERS[number]['dead'] = p

							if role:
								self.set_role(number, role)

					continue

				elif 'выстрелить' in service_message:
					players = service_message.split(', но убил')[0].split(' попытался выстрелить в ')

					for p in range(2):
						number = int(players[p].split(' ')[0]) - 1
						name = players[p].split(' ')[1]	

						if '/' in players[p]:
							role = players[p].split(' / ')[1].split(')')[0]

						else:
							role = None

						self.set_name(number, name)
						self.PLAYERS[number]['dead'] = not p

						if role:
							self.set_role(number, role)

					continue

				elif 'камень' in service_message:
					players = service_message.split(' и убил его')[0].split(' бросил камень в ')

					for p in range(2):
						number = int(players[p].split(' ')[0]) - 1
						name = players[p].split(' ')[1]	

						if '/' in players[p]:
							role = players[p].split(' / ')[1].split(')')[0]

						else:
							role = None

						self.set_name(number, name)
						self.PLAYERS[number]['dead'] = p

						if role:
							self.set_role(number, role)

					continue

				else:
					if 'прошлой ночью' in service_message:
						service_message = service_message.replace('прошлой ночью', '')

					if 'убили' in service_message:
						sep = ' убили '

					elif 'убила' in service_message:
						sep = ' убила '

					else:
						sep = ' убил '

					player = service_message.split(sep)[1]

			elif 'сделал выстрел' in service_message:
				player = service_message.split(' сделал выстрел в ')[1]

			elif 'зарезал' in service_message:
				player = service_message.split(' зарезал ')[1]

			elif 'съел' in service_message:
				player = service_message.split(' съел ')[1]

			elif 'поджёг' in service_message:
				player = service_message.split(' поджёг ')[1]

			elif 'взрывом' in service_message:
				player = service_message.split(' был убит взрывом!')[0]

			elif 'застрелил' in service_message:
				if 'Надзиратель' in service_message:
					player = service_message.split(' застрелил ')[1]

				else:
					players = service_message.split(' застрелил ')

					for p in range(2):
						number = int(players[p].split(' ')[0]) - 1
						name = players[p].split(' ')[1]	

						if '/' in players[p]:
							role = players[p].split(' / ')[1].split(')')[0]

						else:
							role = None

						self.set_name(number, name)
						self.PLAYERS[number]['dead'] = p

						if role:
							self.set_role(number, role)

					continue

			elif 'казнил' in service_message:
				if 'Тюремщик' in service_message:
					player = service_message.split(' ночью. ')[1].split(' умер.')[0]

				else:
					player = service_message.split(' казнил ')[1]

			elif 'Меч' in service_message:
				player = service_message.split(' чтобы убить ')[1]

			elif 'посетил' in service_message and 'Ты' not in service_message:
				player = service_message.split(' посетил ')[0]
				role = 'Red lady'

			elif 'был ранен' in service_message:
				player = service_message.split(' был ')[0][6:]

			elif 'раскрыть роль' in service_message:
				player = service_message.split(' раскрыть роль ')[1]
				dead = False

			elif 'отомщена' in service_message:
				player = service_message.split(' отомщена, ')[1].split(' погиб!')[0]

			elif 'душе' in service_message:
				player = service_message.split(' погиб ')[0]

			elif 'привязан' in service_message:
				player = service_message.split(' был убит ')[0]

			elif 'связал' in service_message and 'Ты' not in service_message:
				player = service_message.split('Роль ')[1].split(' была ')[0]

			elif 'отравлен' in service_message:
				player = service_message.split(' отравлен ')[0]

			elif 'мэр!' in service_message:
				player = service_message.split('Игрок ')[1].split(' - ')[0]

				number, name = player.split(' ')
				number = int(number) - 1
				role = 'Mayor'
				dead = False

			elif 'проповедник!' in service_message:
				player = service_message.split('Игрок ')[1].split(' - ')[0]

				number, name = player.split(' ')
				number = int(number) - 1
				role = 'Preacher'
				dead = False

			elif 'воскресил' in service_message:
				player = service_message.split(' воскресил ')[1].replace('.', '')

				number, name = player.split(' ')
				number = int(number) - 1
				dead = False

			elif 'использовал карту гадалки' in service_message:
				player = service_message.split(' использовал карту гадалки')[0]

			elif 'сбежал из деревни' in service_message:
				if 'любви' in service_message:
					player = service_message.split('Игрок ')[1].split(' лишился')[0]

				elif 'рекрутом' in service_message:
					player = service_message.split('Игрок ')[1].split(' был')[0]

				else:
					player = service_message.split(' сбежал из деревни.')[0]

			elif 'героически' in service_message:
				player = service_message.split(' героически занял место ')[0].split('Игрок ')[1]
				number = int(player.split(' ')[0]) - 1
				name = player.split(' ')[1]

				self.PLAYERS[number]['dead'] = False
				self.PLAYERS[number]['hero'] = True
				self.set_name(number, name)

				continue

			elif 'победил' in service_message:
				return 1

			if player:
				player = player.replace('.', '').replace('!', '')

				if not number:
					number = int(player.split(' ')[0]) - 1
					name = player.split(' ')[1]

				if role is None and '/' in service_message:
					role = player.split(' / ')[1].split(')')[0]

				self.set_name(number, name)
				self.PLAYERS[number]['dead'] = dead

				if role:
					self.set_role(number, role)

		for player_message in player_messages:
			if 'Приватное' in player_message or 'Личное' in player_message or 'Сбежавший' in player_message or 'Для ' in player_message:
				continue

			player_message = player_message.split(': ', 1)

			if len(player_message) != 2:
				continue

			player, message = player_message

			if ' ' not in player:
				continue

			number = int(player.split(' ')[0]) - 1
			name = player.split(' ')[1]

			self.PLAYERS[number]['messages'].append(message)

			for pp in range(len(self.PREV_PLAYERS)):
				self.PREV_PLAYERS[pp][number]['messages'].append(message)

			number = ''

			for s in message:
				if s.isdigit():
					number += s

				elif number:
					if int(number) in range(1, 17):
						self.PLAYERS[int(number) - 1]['mentions'].append(message)

						for pp in range(len(self.PREV_PLAYERS)):
							self.PREV_PLAYERS[pp][int(number) - 1]['mentions'].append(message)

					number = ''

		self.page.evaluate('(players) => localStorage.setItem("players", players)', json.dumps(self.PLAYERS, default=list))
		
		if self.mastermind:
			self.mastermind.update_state()
			self.calculate_threats()

		self.parse_chat_messages(player_messages)

	def set_players_range(self, number=0, start=0, end=16):
		for player in self.PLAYER_LAYERS[start:end]:
			self.set_name(player['number'], player['name'], threaded=True)

		if not number:
			self.DISCOVERED = [True, True]

		else:
			self.DISCOVERED[number - 1] = True

	def find_players(self):
		self.DISCOVERED = [False, False]
		self.PLAYER_LAYERS = []

		print(f'{Style.BRIGHT}{Fore.YELLOW}Finding players...')

		for i in range(1, 5):
			for j in range(1, 5):
				try:
					number = 4 * (i - 1) + j - 1

					player_layer_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/div[{i}]/div[{j}]/div')
					player_name_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/div[{i}]/div[{j}]/div/div[1]/div/div[4]/div/div')
					name = player_name_locator.text_content(timeout=1000).split(' ')[1]

					self.PLAYER_LAYERS.append({
						'number': number,
						'name': name,
						'locator': player_layer_locator
					})

					time.sleep(0.1)
				except PlaywrightTimeoutError:
					continue

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

		roles_base_locator = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[2]/div')

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
					input(rotation_icon, 'not found!')

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

		self.day_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div/div').first
		self.dead_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div[1]/div')

		self.mastermind = Mastermind(self)

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

			info += f' ({len(messages)})'

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

		return

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
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=120000)

						break
					except PlaywrightTimeoutError:
						print(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')

						continue

				self.log_message('success', 'Website opened!')

				while True:
					banner(self.__class__.__name__)

					if self.prepare():
						input(f'\n{Style.BRIGHT}{Back.RED}Invalid API key!{Back.RESET}')

						return

					self.log_message('info', 'Waiting for game start...')

					while True:
						try:
							phase_locator = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div[1]/div/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div').first
							phase_text = phase_locator.text_content(timeout=1000)

							if phase_text.endswith('s') or \
								phase_text.startswith('Обсуждение') or \
								phase_text.startswith('Голосование'):

								break
						except KeyboardInterrupt:
							return
						except PlaywrightTimeoutError:
							pass

						time.sleep(1)

					print(f'{Style.BRIGHT}{Fore.GREEN}Game found!')

					self.get_bearer()
					self.load_css()
					self.load_modal()
					self.find_players()

					roles = self.find_roles()
					rotations = self.get_rotations()

					print(f'{Style.BRIGHT}{Fore.YELLOW}Finding rotation...')

					self.ROTATION = self.choose_rotation(rotations, roles)

					if self.ROTATION is None:
						input(f'\n{Style.BRIGHT}{Back.RED}Rotation not found!{Back.RESET}')

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
		except Exception as e:
			input(f'\n{Style.BRIGHT}{Back.RED}{str(e)}{Back.RESET}')

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


class Booster:
	@require_module_auth('booster')
	def __init__(self):
		self.config = dotenv_values('config.txt')
		self.is_valid = True
		self.should_stop = False

		self.CHROME_EXECUTABLE = find_chrome_executable()

		if not self.CHROME_EXECUTABLE:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_USER_DATA = USER_DATA_DIR / 'Mentalist'

		os.makedirs(self.CHROME_USER_DATA, exist_ok=True)

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Booster Error: Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			input(f'{Style.BRIGHT}{Back.RED}Booster Error: Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.context = None
		self.page = None
		self.player_name = None

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

	def find_suitable_room(self):
		if self.check_stop_flag():
			return

		self.log_message('info', 'Scanning rooms...')

		time.sleep(1)
		
		try:
			xpath_variants = [
				'/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div[3]/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div',
				'/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div'
			]
			
			rooms_container = None
			active_xpath = None

			for xpath in xpath_variants:
				try:
					container = self.page.locator(f'xpath={xpath}').first
					container.wait_for(state='visible', timeout=3000)
					rooms_container = container
					active_xpath = xpath

					break
				except PlaywrightTimeoutError:
					continue
			
			if not rooms_container:
				self.log_message('error', 'Could not find rooms container')
				
				return
			
			room_count = rooms_container.evaluate('(container) => container.children.length;', timeout=10000)
			
			self.log_message('cyan', f'Found {room_count} rooms')
			
			for i in range(1, room_count + 1):
				if self.check_stop_flag():
					return

			for i in range(1, room_count + 1):
				try:
					room_base = f'{active_xpath}/div[{i}]/div/div'
					room_name_locator = self.page.locator(f'xpath={room_base}/div[1]/div[2]/div[1]')
					room_name = room_name_locator.text_content(timeout=2000).lower()

					if 'vill win' not in room_name or 'bqt' in room_name:
						continue

					player_count_locator = self.page.locator(f'xpath={room_base}/div[1]/div[5]')
					player_count_text = player_count_locator.text_content(timeout=2000)

					if not player_count_text.isdigit():
						continue

					player_count = int(player_count_text)

					if player_count > 6:
						continue
			
					xp_icon_locator = self.page.locator(f'xpath={room_base}/div[1]/div[3]/img')

					if not xp_icon_locator.is_visible(timeout=2000):
						continue

					self.log_message('success', f'Found suitable room: {room_name} ({player_count}/8)')
					
					return i
				except PlaywrightTimeoutError:
					continue
		except Exception as e:
			if 'strict mode violation' in str(e):
				self.log_message('error', 'Multiple room containers detected, using first')

			else:
				self.log_message('error', f'Error scanning rooms: {str(e)[:100]}')

	def join_room(self, room_index):
		if self.check_stop_flag():
			return False

		try:
			self.log_message('info', f'Joining room #{room_index}...')

			xpath_variants = [
				f'/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div[3]/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div/div[{room_index}]/div/div',
				f'/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div/div/div/div/div/div[2]/div[2]/div[1]/div/div/div/div/div[{room_index}]/div/div'
			]
			
			room_locator = None

			for xpath in xpath_variants:
				try:
					locator = self.page.locator(f'xpath={xpath}').first
					locator.wait_for(state='visible', timeout=2000)
					room_locator = locator

					break
				except PlaywrightTimeoutError:
					continue
			
			if not room_locator:
				self.log_message('error', 'Could not find room to join')
				
				return False
			
			room_locator.click(timeout=5000)
			
			time.sleep(1)

			join_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[3]/div[2]/div/div')
			join_button.click(timeout=5000)
			
			time.sleep(1)

			try:
				ok_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')
				
				if ok_button.is_visible(timeout=3000):
					self.log_message('warning', 'Game already started, retrying...')
					
					ok_button.click()

					time.sleep(1)
					
					return False
			except:
				pass
			
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
			refresh_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div/div/div/div/div/div[2]/div[2]/div[2]/div[2]/div/div/div')
			refresh_button.click(timeout=5000)
			
			time.sleep(1)
			
			self.log_message('cyan', 'Refreshed room list')
		except Exception as e:
			self.log_message('error', f'Failed to refresh: {str(e)[:100]}')

	def auto_find_and_join(self):
		while True:
			if self.check_stop_flag():
				return False
			
			room_index = self.find_suitable_room()
			
			if room_index:
				if self.join_room(room_index):
					return True

				else:
					self.refresh_rooms()
			else:
				self.log_message('warning', 'No suitable rooms found, waiting 5 seconds...')
				
				time.sleep(5)
				
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

	def get_players_info_villager(self):
		players = []
		self_number = None
		role = None
		role_name = None

		for i in range(1, 5):
			for j in range(1, 5):
				try:
					time.sleep(0.1)

					player_base_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[{i}]/div[{j}]/div')
					player_img_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[{i}]/div[{j}]/div')

					name = player_base_locator.text_content(timeout=1000).split(' ')[1]
					icons = player_img_locator.evaluate('''
						(player) => {
							let sources = [];

							const images = player.getElementsByTagName("img");

							for (image of images) sources.push(image.src);

							return sources;
						}
					''')

					player_number = 4 * (i - 1) + j

					player = {
						'locator': player_base_locator,			
						'name': name,
						'self': False,
						'number': player_number
					}

					if not self.player_name:
						is_self = player_base_locator.evaluate('''
							(player) => {
								let sources = [];

								const images = player.getElementsByTagName("img");

								for (image of images) sources.push(image.src);

								return sources;
							}
						''', timeout=1000)
						
						if is_self:
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

									self.log_message('success', f'You are {article} {role_name}!')

					players.append(player)
				except (PlaywrightTimeoutError, IndexError):
					continue

		return players, self_number, role

	def get_players_info_werewolf(self):
		players = []
		couples = []
		self_number = None
		role = None
		role_name = None
		has_jww = False
		vote = False
		tag = False
		werewolf_numbers = []

		for i in range(1, 5):
			for j in range(1, 5):
				try:
					time.sleep(0.1)

					player_base_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[{i}]/div[{j}]/div')
					player_img_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[{i}]/div[{j}]/div')

					name = player_base_locator.text_content(timeout=1000).split(' ')[1]
					icons = player_img_locator.evaluate('''
						(player) => {
							let sources = [];

							const images = player.getElementsByTagName("img");

							for (image of images) sources.push(image.src);

							return sources;
						}
					''')

					player_number = 4 * (i - 1) + j

					player = {
						'locator': player_base_locator,			
						'name': name,
						'self': False,
						'couple': False,
						'number': player_number
					}

					is_werewolf = False

					if not self.player_name:
						is_self = player_base_locator.evaluate('''
							(player) => {
								const allDivs = player.querySelectorAll('div');
								
								for (let div of allDivs) {
									const style = div.getAttribute('style');

									if (style && style.includes('rgb(236, 64, 122)')) return true;
								}

								return false;
							}
						''', timeout=1000)
						
						if is_self:
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

						if 'junior' in icon:
							if player['self']:
								tag = True
								role = 'junior_werewolf'
							
						elif 'wolf_seer' in icon or 'wolfseer' in icon:
							if player['self']:
								role = 'wolf_seer'

							else:
								has_jww = True

						elif 'lovers' in icon:
							player['couple'] = True

							if not is_werewolf and player_number not in couples:
								couples.append(player_number)

						if player['self'] and 'icon_' in icon and role_name is None:
							extracted_role = self.get_role_name_from_icon(icon)

							if extracted_role:
								role_name = extracted_role
								article = self.get_article(role_name)

								self.log_message('warning', f'You are {article} {role_name}!')

					players.append(player)
				except (PlaywrightTimeoutError, IndexError):
					continue
		
		couples = [c for c in couples if c not in werewolf_numbers]

		if has_jww or (couples and not has_jww and role != 'wolf_seer'):
			vote = True

		return players, couples, self_number, role, vote, tag

	def act_werewolf(self):
		self.log_message('info', 'Finding players...')

		start_time = time.monotonic()

		players, couples, self_number, role, vote, tag = self.get_players_info_werewolf()

		self.log_message('success', 'Players found!')

		if couples:
			self.send_couples_message(couples)

		if vote and couples:
			self.vote_for_couple(players, couples)

		if tag:
			self.tag_target(players, self_number, couples, start_time)

	def analyze_day_chat(self, self_number):
		try:
			chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div[1]/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div/div/div[1]/div/div/div').first

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

				player_info, message_text = message.split(': ', 1)
				
				try:
					number, player_name = player_info.split(' ', 1)
					number = int(number)
				except (ValueError, IndexError):
					continue

				if number == self_number:
					continue

				message_lower = message_text.lower().strip()

				if message_lower in ['m', 'me', 'wc']:
					self.log_message('warning', f'Suspicious message from player {number}: "{message_text}"')
					
					return number

				words = message_text.split()

				for word in words:
					if word.isdigit():
						word_num = int(word)

						if 1 <= word_num <= 16:
							self.log_message('warning', f'Player {number} mentioned number {word_num}')
							
							return number
		except Exception as e:
			self.log_message('error', f'Error analyzing chat: {str(e)[:100]}')

	def analyze_night_chat(self, self_number, couples):
		try:
			chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[1]/div/div/div').first

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

		for _ in range(30):
			if self.check_stop_flag():
				return False

			try:
				phase_locator = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div[1]/div/div/div[1]/div[1]/div/div[2]/div[1]/div[1]/div/div/div[1]/div')
				phase_text = phase_locator.text_content(timeout=1000)

				if phase_text.startswith('Голосование'):
					self.log_message('success', 'Voting phase started!')
					
					return True
			except:
				pass

			time.sleep(1)

		self.log_message('warning', 'Voting phase not detected')

		return False

	def use_ability_on_target(self, players, target_number, ability_name):
		self.log_message('info', f'Using {ability_name} on player {target_number}...')

		try:
			ability_icon = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div[1]/img')
			ability_icon.click(timeout=5000)

			time.sleep(1)

			target_player = next((p for p in players if p['number'] == target_number), None)
			
			if target_player:
				target_player['locator'].click(timeout=5000)
				
				self.log_message('info', f'Using {ability_name} on player {target_number}...')
			
			else:
				self.log_message('success', f'{ability_name.capitalize()} used on player {target_number}!')
		except Exception as e:
			self.log_message('error', f'Failed to use {ability_name}: {str(e)[:50]}')

	def act_villager(self):
		players, self_number, role = self.get_players_info_villager()

		if not self.wait_for_voting_phase():
			return

		self.log_message('info', 'Analyzing day chat...')
		
		target_number = self.analyze_day_chat(self_number)

		if not target_number:
			self.log_message('error', 'Target player not found')
			
			return

		if role == 'priest':
			self.use_ability_on_target(players, target_number, 'holy water')

		elif role == 'vigilante':
			self.use_ability_on_target(players, target_number, 'bullet')

		elif role == 'gunner':
			self.use_ability_on_target(players, target_number, 'bullet')

	def act_werewolf(self):
		self.log_message('info', 'Finding players...')

		start_time = time.monotonic()

		players, couples, self_number, wolf_role, vote, tag = self.get_players_info_werewolf()

		self.log_message('success', 'Players found!')

		if couples:
			self.send_couples_message(couples)

		if vote and couples:
			self.vote_for_couple(players, couples)

		if tag:
			self.tag_target(players, self_number, couples, start_time)

	def send_couples_message(self, couples):
		textarea = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[2]/div/textarea')

		self.log_message('info', 'Sending message...')

		if len(couples) > 1:
			message = 'My couples are '

		elif len(couples) == 1:
			message = 'My couple is '

		else:
			return

		message += ' '.join([str(couple) for couple in couples])

		textarea.fill(message)
		textarea.press('Enter')

		self.log_message('success', 'Message sent!')

	def vote_for_couple(self, players, couples):
		self.log_message('info', 'Voting couple...')

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

	def tag_target(self, players, self_number, couples, start_time):
		self.log_message('info', 'Finding target...')

		remaining_time = 30 - (time.monotonic() - start_time)

		if remaining_time >= 10:
			time.sleep(remaining_time - 10)

		target = self.analyze_night_chat(self_number, couples)

		if not target:
			self.log_message('warning', 'Target not found!')

			return

		self.log_message('success', 'Target found!')
		self.log_message('info', 'Tagging player...')

		try:
			self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div/img').click(timeout=10000)

			time.sleep(1)

			players[target - 1]['locator'].click(timeout=10000)

			self.log_message('success', 'Player tagged!')
		except Exception as e:
			self.log_message('error', f'Tag failed: {str(e)[:50]}')

	def check_stop_flag(self):
		if hasattr(self, '_stop_event'):
			return self._stop_event.is_set()

		try:
			from mentalist_gui import stop_flags

			return stop_flags.get('booster', threading.Event()).is_set()
		except:
			return self.should_stop

	def play(self):
		rejoined = False

		while True:
			banner(self.__class__.__name__)

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')	

				return

			if not rejoined:
				if not self.auto_find_and_join():
					return

			else:
				rejoined = False

			self.log_message('info', 'Waiting for game start...')

			start = False
			werewolf = False

			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Booster stop requested')
					
					return

				try:
					game_started_ok_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')
					
					if game_started_ok_button.is_visible(timeout=500):
						try:
							button_text = game_started_ok_button.text_content(timeout=500)
						except UnicodeDecodeError:
							button_text = ''
						
						if button_text == 'Окей' or button_text == '':
							self.log_message('warning', 'Game already started, returning to lobby...')
							
							game_started_ok_button.click()
							
							time.sleep(1)

							break
				except PlaywrightTimeoutError:
					pass

				try:
					host_left_ok_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[3]/div/div/div')
					
					if host_left_ok_button.is_visible(timeout=500):
						try:
							button_text = host_left_ok_button.text_content(timeout=500)
						except UnicodeDecodeError:
							button_text = ''
							
						if button_text == 'Окей' or button_text == '':
							self.log_message('warning', 'Host left the room, returning to lobby...')

							host_left_ok_button.click()
							
							time.sleep(1)
							
							break
				except PlaywrightTimeoutError:
					pass

				try:
					night_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[3]/div/div[1]')

					try:
						chat_text = night_chat.text_content(timeout=1000)
					except UnicodeDecodeError:
						chat_text = ''

					if chat_text == 'Чат оборотней' or 'оборот' in chat_text.lower():
						werewolf = True

					start = True

					break
				except PlaywrightTimeoutError:
					try:
						create_game_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div[3]/div/div/div/div/div[2]/div[2]/div[2]/div[1]/div/div/div')

						try:
							button_text = create_game_button.text_content(timeout=1000)
						except UnicodeDecodeError:
							button_text = ''
							
						if 'СОЗДАТЬ' in button_text or 'CREATE' in button_text.upper():
							try:
								close_popup_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')
	
								try:
									close_text = close_popup_button.text_content(timeout=1000)
								except UnicodeDecodeError:
									close_text = ''
									
								if close_text == 'Окей' or close_text == '':
									close_popup_button.click()
							except PlaywrightTimeoutError:
								pass

							break
					except PlaywrightTimeoutError:
						try:
							start_game_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div[1]/div[2]/div[4]/div[2]/div/div/div')

							try:
								button_text = start_game_button.text_content(timeout=1000)
							except UnicodeDecodeError:
								button_text = ''
								
							if 'НАЧАТЬ' in button_text or 'START' in button_text.upper():
								start_game_button.click()
						except PlaywrightTimeoutError:
							pass
				except:
					continue

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')

				return

			if not start:
				continue

			if werewolf:
				self.act_werewolf()

			else:
				self.act_villager()

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')
				
				return

			self.log_message('info', 'Waiting for game end...')

			while True:
				if self.check_stop_flag():
					self.log_message('info', 'Booster stop requested')
					
					return

				try:
					continue_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[23]/div/div/div[4]/div/div').get_by_text('Продолжить')
					continue_button.click(timeout=30000)

					time.sleep(1)

					self.log_message('success', 'End!')

					break
				except PlaywrightTimeoutError:
					continue

			if self.check_stop_flag():
				self.log_message('info', 'Booster stop requested')
					
				return

			self.log_message('info', 'Exiting...')

			try:
				play_again_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div[2]/div/div/div/div/div/div[1]/div[1]/div[2]/div[2]/div[3]/div[5]/div[2]/div/div[2]').get_by_text('Играть снова')
				play_again_button.click(timeout=30000)

				time.sleep(1)

				try:
					modal_ok_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')

					try:
						button_text = modal_ok_button.text_content(timeout=3000)
					except UnicodeDecodeError:
						button_text = ''
						
					if button_text == 'Окей' or button_text == '':
						self.log_message('warning', 'Game already started, closing...')
						
						modal_ok_button.click()

						time.sleep(1)

						continue
				except PlaywrightTimeoutError:
					pass

				try:
					host_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[3]/div[2]/div/div')
		
					try:
						button_text = host_button.text_content(timeout=1000)
					except UnicodeDecodeError:
						button_text = ''
						
					if button_text == 'Окей' or button_text == '':
						host_button.click()
				except PlaywrightTimeoutError:
					pass

				rejoined = True
			except PlaywrightTimeoutError:
				self.log_message('warning', 'Play again button timeout - returning to lobby')

				sound_path = get_resource_path(os.path.join('audio', 'glitch.mp3'))
				playsound(sound_path, block=False)

				try:
					close_popup_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')

					try:
						button_text = close_popup_button.text_content(timeout=1000)
					except UnicodeDecodeError:
						button_text = ''
						
					if button_text == 'Окей' or button_text == '':
						close_popup_button.click()
				except PlaywrightTimeoutError:
					pass

				return

	def run(self):
		_integrity_checker.verify_silent()

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

				self.context = playwright.chromium.launch_persistent_context(
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
						'--mute-audio',
						'--disable-blink-features=AutomationControlled'
					],
					ignore_default_args=['--enable-automation'],
					chromium_sandbox=True
				)

				self.page = self.context.pages[0]
				
				while True:
					if self.check_stop_flag():
						self.log_message('info', 'Booster stop requested')

						break
						
					try:
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=120000)

						break
					except PlaywrightTimeoutError:
						self.log_message('error', 'Timeout error!')

						continue

				if self.check_stop_flag():
					self.log_message('info', 'Booster stopping - closing browser')

					self.context.close()

					return

				try:
					decline_notifications_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div[1]/div/div/div/div/div/div/div[1]/div[1]/div/div/div/div/div/div/div[2]/div[2]/div')
				
					if decline_notifications_button.text_content(timeout=10000) == '\uf00d':
						decline_notifications_button.click()
				except PlaywrightTimeoutError:
					pass

				self.log_message('success', 'Website opened!')

				time.sleep(1)

				cancel_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div[1]/div')
				
				try:
					if cancel_button.is_visible(timeout=5000):
						self.log_message('warning', 'Found startup "Existing game" modal, closing...')
						
						cancel_button.click()
						time.sleep(1)
				except:
					pass

				while True:
					if self.check_stop_flag():
						self.log_message('info', 'Booster stopping - exiting main loop')

						break
						
					self.log_message('info', 'Opening custom games menu...')

					while True:
						if self.check_stop_flag():
							break
							
						try:
							play_button = self.page.get_by_text('ИГРАТЬ', exact=True)
							play_button.wait_for(state='visible', timeout=10000)
							is_disabled = play_button.is_disabled(timeout=5000)
							
							if not is_disabled:
								time.sleep(0.5)

								play_button.click(timeout=5000)

								try:
									self.page.get_by_text('ПЕРСОНАЛИЗИРОВАННЫЕ ИГРЫ').wait_for(state='visible', timeout=3000)
									
									self.log_message('success', 'Play button clicked!')
									
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
							self.page.get_by_text('ПЕРСОНАЛИЗИРОВАННЫЕ ИГРЫ').click(timeout=10000)

							break
						except PlaywrightTimeoutError:
							continue

					if self.check_stop_flag():
						break

					try:
						join_new_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[5]/div/div/div[3]/div[3]/div/div')
						
						if join_new_button.is_visible(timeout=3000):
							self.log_message('cyan', 'Found "Join New" prompt, clicking...')

							join_new_button.click()
							time.sleep(1)
					except:
						pass

					self.log_message('success', 'Menu opened!')

					self.play()

					if self.check_stop_flag():
						break

				self.log_message('info', 'Booster closing browser context')

				self.context.close()
				
		except KeyboardInterrupt:
			if self.context:
				self.context.close()

			return
		except Exception as e:
			if self.context:
				self.context.close()

			self.log_message('error', f'Critical error: {str(e)}')

			return


class Stalker:
	@require_module_auth('stalker')
	def __init__(self):
		self.config = dotenv_values('config.txt')
		self.is_valid = True

		try:
			self.API_KEYS = self.config['STALKER_API_KEYS'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = find_chrome_executable()

		if not self.CHROME_EXECUTABLE:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_USER_DATA = USER_DATA_DIR / 'Mentalist'

		os.makedirs(self.CHROME_USER_DATA, exist_ok=True)

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Stalker Error: Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			input(f'{Style.BRIGHT}{Back.RED}Stalker Error: Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.TIMEZONE = self.get_system_timezone()

		self.ntp = ntplib.NTPClient()
		self.NTP_SERVER = 'time.google.com'

		self.API_KEY = self.switch_api_key()

		self.BEARER_TOKEN = None
		self.CF_JWT = None

		self.BOT_BASE_URL = 'https://api.wolvesville.com/'
		self.BEARER_BASE_URL = 'https://core.api-wolvesville.com/'

		self.BEARER_HEADERS = {}

		self.USER_AGENT = generate_random_user_agent(device_type='windows', browser_type='chrome')

		self.TARGETS = OrderedDict()
		self.CLAN_CHANGES = {}
		self.INFO_CHANGES = {}

		self.updating = False
		self.page = None
		self.monitor_page = 1

		self.load_targets()

		threading.Thread(target=self.auto_update, daemon=True).start()

	def _check_phantom_mode(self):
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
			input(f'\n{Style.BRIGHT}{Back.RED}Could not detect local timezone. Defaulting to UTC.')

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

		input() if error else print()

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

	def get_bearer(self):
		self.BEARER_TOKEN = self.page.evaluate('() => JSON.parse(localStorage.getItem("authtokens"))["idToken"]')
		self.CF_JWT = self.page.evaluate('() => localStorage.getItem("cloudflare-turnstile-jwt")')

		self.BEARER_HEADERS = {
			'Authorization': f'Bearer {self.BEARER_TOKEN}',
			'Cf-Jwt': f'{self.CF_JWT}',
			'Ids': '1'
		}

		if hasattr(self, 'auth_client'):
			try:
				self.auth_client.update_tokens(
					bearer_token=self.BEARER_TOKEN,
					stalker_keys=self.API_KEYS
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

			if not os.path.isdir(MENTALIST_DATA_DIR / targets):
				os.mkdir(MENTALIST_DATA_DIR / targets)

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
		if self._check_phantom_mode():
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
		if self._check_phantom_mode():
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
			playsound(sound_path, block=False)

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
						'--mute-audio',
						'--disable-blink-features=AutomationControlled'
					],
					ignore_default_args=['--enable-automation'],
					chromium_sandbox=True,
				)

				self.page = context.pages[0]
				
				while True:
					try:
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=120000)

						break
					except PlaywrightTimeoutError:
						print(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')

						continue

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


class Spinner:
	@require_module_auth('spinner')
	def __init__(self):
		self.config = dotenv_values('config.txt')
		self.is_valid = True
		self.app = None
		self.should_stop = False

		try:
			self.BLUESTACKS5_EXECUTABLE = self.config['BLUESTACKS5_EXECUTABLE']
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Spinner Error: Path to BlueStacks 5 not found!{Back.RESET}')

			self.is_valid = False

			return

		if not os.path.isfile(self.BLUESTACKS5_EXECUTABLE):
			print(f'{Style.BRIGHT}{Back.RED}Spinner Error: Path to BlueStacks 5 is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.BLUESTACKS5_NAME = self.config['BLUESTACKS5_NAME']
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Spinner Error: Name of BlueStacks 5 not found!{Back.RESET}')

			self.is_valid = False

			return

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
			coords = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
			
			if coords:
				if click:
					try:
						x, y = coords

						engine = _integrity_checker.get_entanglement_engine()

						x, y = engine.apply_coordinate_distortion(x, y)
						
						if _integrity_checker.get_corruption_handler().is_phantom_mode():
							if random.random() < 0.2:
								time.sleep(random.uniform(0.1, 0.5))

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
				self.log_state('Checking rewards', 'Scanning for ad button')

				self.app.Dialog.click_input(coords=(0, 0))

				result = self.wait('done.png', confidence=0.8, check_fail=True, check_count=3, stop_check_callback=self.check_stop_flag)
				
				if result == -1:
					return -1

				elif result == 0:
					self.log_message('success', 'DONE!')
					self.log_state('Complete', 'All spins finished')

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
					[self.BLUESTACKS5_EXECUTABLE, '--cmd', 'launchApp', '--package', 'com.werewolfapps.online'],
					stdout=subprocess.PIPE
				)

				try:
					self.app = pywinauto.Application(backend='uia').connect(title=self.BLUESTACKS5_NAME, timeout=30)

					window = pygetwindow.getWindowsWithTitle(self.BLUESTACKS5_NAME)[0]
					window.size = (540, 934)
				except IndexError:
					input(f'{Style.BRIGHT}{Back.RED}Name of BlueStacks 5 window is invalid!{Back.RESET}')

					os.abort()

				self.log_message('info', 'Waiting for the game to load...')

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

	def check_stop_flag(self):
		if hasattr(self, '_stop_event'):
			return self._stop_event.is_set()

		try:
			from mentalist_gui import stop_flags
			
			return stop_flags.get('booster', threading.Event()).is_set()
		except:
			return self.should_stop

	def run(self):
		try:
			while True:
				banner(self.__class__.__name__)

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


def check_updates_on_startup():
	try:
		config = dotenv_values('config.txt')

		if config.get('SERVER_SYNC_ENABLED') != 'true':
			return
		
		updater = MentalistUpdater(
			server_url=config.get('MENTALIST_SERVER_URL'),
			api_key=config.get('MENTALIST_SERVER_API_KEY'),
			current_version=VERSION
		)
		
		update_available, info = updater.check_for_updates(silent=False)

		if update_available:
			print(f'Version {info.get("version")} available!')
	except:
		pass

def banner(module=None):
	os.system('cls' if os.name == 'nt' else 'clear')

	message = f'{Style.BRIGHT}{Fore.RED}{"=" * 60}{Fore.RESET}\n'
	message += f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist {Fore.CYAN}CLI{Fore.RESET}'

	if module:
		message += f'{Fore.RED} | {module}'

	message += f'\n{Style.BRIGHT}{Fore.MAGENTA}by Corruptor{Fore.RESET}\n'
	message += f'\n{Style.DIM}{Fore.CYAN}Press Ctrl+C to quit{Fore.RESET}\n'
	message += f'{Style.BRIGHT}{Fore.RED}{"=" * 60}{Fore.RESET}\n'

	print(message)


if getattr(sys, 'frozen', False):
	base_path = sys._MEIPASS

	ms_playwright_path = os.path.join(base_path, 'ms-playwright')

	if os.path.exists(ms_playwright_path):
		os.environ['PLAYWRIGHT_BROWSERS_PATH'] = ms_playwright_path

	possible_node_paths = [
		os.path.join(base_path, 'playwright', 'driver', 'node.exe'),
		os.path.join(base_path, 'ms-playwright', 'node.exe'),
		os.path.join(base_path, 'node', 'node.exe')
	]
	
	for node_path in possible_node_paths:
		if os.path.exists(node_path):
			os.environ['PLAYWRIGHT_NODEJS_PATH'] = node_path

			break
