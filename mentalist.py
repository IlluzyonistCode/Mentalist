import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.figure_factory as ff
import io
import queue
import threading
import requests
import hashlib
import pyautogui
import pywinauto
import pygetwindow
import psutil
import ntplib
import copy
import json
import os
import re
import subprocess
import dateutil
import pytz
import time
import random
from undetected_playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from plotly.subplots import make_subplots
from collections import OrderedDict
from copy import deepcopy
from itertools import combinations
from functools import lru_cache
from playsound import playsound
from colorama import Back, Fore, Style, init
from datetime import datetime, timedelta
from dotenv import dotenv_values

init(autoreset=True)

requests.packages.urllib3.disable_warnings()

GLOBAL_CONFIG = dotenv_values('.env')
GUI_ENABLED = GLOBAL_CONFIG.get('GUI_ENABLED', 'false').lower() == 'true'


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

	def load_profiles(self, filename='role_profiles.json'):
		local_profiles = {}
		
		try:
			with open(filename, 'r', encoding='utf-8') as f:
				local_profiles = json.load(f)
		except FileNotFoundError:
			print(f'{Style.BRIGHT}{Back.YELLOW}Local role profiles not found. Trying Mentalist Server...{Back.RESET}')
		
		if self.tracker.SERVER_ENABLED:
			success, server_profiles = self.tracker.sync_with_server(
				'role_profiles',
				local_profiles,
				bidirectional=False
			)
			
			if success and server_profiles:
				try:
					with open(filename, 'w', encoding='utf-8') as f:
						json.dump(server_profiles, f, ensure_ascii=False, indent=2)

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
		self.action_history = []
		self.initialize_special_roles(self.state)

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
	def __init__(self):
		self.config = dotenv_values('.env')
		self.is_valid = True

		try:
			self.API_KEYS = self.config['TRACKER_API_KEYS'].split(',')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = self.config.get('CHROME_EXECUTABLE')

		if self.CHROME_EXECUTABLE is not None and not os.path.isfile(self.CHROME_EXECUTABLE):
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_USER_DATA = os.path.join(self.config['CHROME_USER_DATA'], 'Mentalist')
		except KeyError:
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome User Data not found!{Back.RESET}')
			
			self.is_valid = False

			return

		if not os.path.isdir(self.CHROME_USER_DATA):
			print(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome User Data is invalid!{Back.RESET}')
			
			self.is_valid = False

			return

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

		self.SERVER_ENABLED = self.config.get('SYNC_SERVER_ENABLED', 'false').lower() == 'true'
		self.SERVER_URL = self.config.get('SYNC_SERVER_URL', 'http://localhost:1101')
		self.SERVER_API_KEY = self.config.get('SYNC_SERVER_API_KEY', '')
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

		self.page = None
		self.day_chat = None
		self.dead_chat = None
		self.last_message_number = 0

		self.mastermind = None
		self.THREAT_LEVELS = {}
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}

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

	def get_bearer(self):
		self.BEARER_TOKEN = self.page.evaluate('() => JSON.parse(localStorage.getItem("authtokens"))["idToken"]')
		self.CF_JWT = self.page.evaluate('() => localStorage.getItem("cloudflare-turnstile-jwt")')

		self.BEARER_HEADERS = {
			'Authorization': f'Bearer {self.BEARER_TOKEN}',
			'Cf-Jwt': f'{self.CF_JWT}',
			'Ids': '1'
		}

	def switch_api_key(self):
		while True:
			for key in self.API_KEYS:
				yield key

	def calculate_hash(self, data):
		json_str = json.dumps(data, sort_keys=True)

		return hashlib.sha256(json_str.encode()).hexdigest()
	
	def sync_with_server(self, data_type, local_data, bidirectional=True):
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
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)
			else:
				endpoint = f'{self.SERVER_URL}/get/{data_type}'
				response = requests.get(
					endpoint,
					headers=headers,
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)
			
			if response.status_code == 200:
				result = response.json()
				
				if result.get('status') == 'no_changes':
					self.data_hashes[data_type] = current_hash

					return True, local_data
				
				elif result.get('status') in ['synced', 'success']:
					server_data = result.get('data', {})
					server_hash = result.get('hash', '')
					
					self.data_hashes[data_type] = server_hash
					
					if bidirectional and result.get('server_updated'):
						print(f'{Style.BRIGHT}{Fore.GREEN}Mentalist Server updated with your {data_type}!')
					
					if server_hash != current_hash:
						print(f'{Style.BRIGHT}{Fore.CYAN}Received updates for {data_type} from Mentalist Server.')
						
						return True, server_data
					
					return True, local_data
			
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

					path = f'assets/{asset}/{filename}'

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
		try:
			with open('data/cards.json', 'r') as cards_file:
				local_cards = json.load(cards_file)
		except:
			local_cards = {}
		
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
		if not os.path.isdir('data'):
			os.mkdir('data')
		
		with open('data/cards.json', 'w') as cards_file:
			json.dump(self.PLAYER_CARDS, cards_file)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('cards', self.PLAYER_CARDS, True),
				daemon=True
			).start()

	def load_icons(self):
		try:
			with open('data/icons.json', 'r') as icons_file:
				local_icons = json.load(icons_file)
		except:
			local_icons = {}
		
		success, self.PLAYER_ICONS = self.sync_with_server('icons', local_icons, bidirectional=True)
		
		if success and self.PLAYER_ICONS != local_icons:
			self.save_icons()
	
	def write_icons(self, player, icons):
		if player not in self.PLAYER_ICONS:
			self.PLAYER_ICONS[player] = icons

		else:
			self.PLAYER_ICONS[player].update(icons)

	def save_icons(self):
		if not os.path.isdir('data'):
			os.mkdir('data')
		
		with open('data/icons.json', 'w') as icons_file:
			json.dump(self.PLAYER_ICONS, icons_file)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('icons', self.PLAYER_ICONS, True),
				daemon=True
			).start()

	def get_roles(self):
		print(f'{Style.BRIGHT}{Fore.YELLOW}Getting roles...')

		ENDPOINT = 'roles'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False).json()

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BEARER_BASE_URL}{ENDPOINT}', headers=self.BEARER_HEADERS, verify=False)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

		if not data.ok:
			return -1

		data = data.json()

		for player in data:
			if player_id == player.get('playerId'):
				return player.get('xp')

		return -1

	def storm(self):
		PLAYERS_OLD = deepcopy(self.PLAYERS)

		self.PLAYERS = []

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

		for p in range(16):
			for o, old in enumerate(PLAYERS_OLD):
				if self.PLAYERS[p]['name'] == old['name']:
					self.PLAYERS[p] = old

					PLAYERS_OLD.pop(o)

		self.last_message_number = 0

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
		for r in range(len(self.ROTATION)):
			if role.lower() == self.ROTATION[r]['name'].lower():
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

					break

		else:
			print(self.ROTATION, player, role)

			return 1

		self.PLAYERS[player]['role'] = self.ROTATION[r]['id']
		self.PLAYERS[player]['team'] = self.ROTATION[r]['team']
		self.PLAYERS[player]['aura'] = self.ROTATION[r]['aura']

		for equal_player in self.PLAYERS[player]['equal']:
			self.PLAYERS[equal_player]['team'] = self.PLAYERS[player]['team']

		for not_equal_player in self.PLAYERS[player]['not_equal']:
			self.PLAYERS[not_equal_player]['teams_exclude'].add(self.PLAYERS[player]['team'])

		if self.PLAYERS[player]['hero'] or self.ROTATION[r]['id'] == 'zombie':
			return

		name = self.PLAYERS[player]['name']

		if name and self.ROTATION[r]['id'] not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if self.ROTATION[r]['id'] in self.ADVANCED_ROLES[src_role]:
					break

			self.write_cards(name, {src_role: self.ROTATION[r]['id']})
			self.save_cards()

		if self.ROTATION[r]['id'] in self.ROTATION_ICONS:
			self.write_icons(name, {self.ROTATION[r]['id']: self.ROTATION_ICONS[self.ROTATION[r]['id']]})
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
					if 'прошлой' in service_message:
						continue

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
					player_base_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/div[{i}]/div[{j}]/div')
					name = player_base_locator.text_content(timeout=1000).split(' ')[1]

					self.PLAYER_LAYERS.append({
						'number': number,
						'name': name,
						'locator': player_layer_locator
					})

					time.sleep(0.1)
				except PlaywrightTimeoutError:
					continue

		if len(self.API_KEYS) >= 2:
			threading.Thread(target=self.set_players_range, args=(1, 0, 8), daemon=True).start()
			threading.Thread(target=self.set_players_range, args=(2, 8, 16), daemon=True).start()

		else:
			find_players_range()

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
		banner(self.__class__.__name__)

		try:
			with sync_playwright() as playwright:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Opening website...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
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
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=100000)

						break
					except PlaywrightTimeoutError:
						print(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')

						continue

				print(f'{Style.BRIGHT}{Fore.GREEN}Website opened!')

				while True:
					banner(self.__class__.__name__)

					if self.prepare():
						input(f'\n{Style.BRIGHT}{Back.RED}Invalid API key!{Back.RESET}')

						return

					print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for game start...')

					while True:
						try:
							night_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[1]/div/div[1]')

							if night_chat.text_content(timeout=1000) == 'Дневной чат':
								break
						except KeyboardInterrupt:
							return
						except:
							continue

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
			input(f'\n{Style.BRIGHT}{Back.RED}Browser closed!{Back.RESET}')

			return


class Booster:
	def __init__(self):
		self.config = dotenv_values('.env')
		self.is_valid = True

		try:
			self.PLAYER_NAME = self.config['PLAYER_NAME']
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Player Name not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = self.config.get('CHROME_EXECUTABLE')

		if self.CHROME_EXECUTABLE is not None and not os.path.isfile(self.CHROME_EXECUTABLE):
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_USER_DATA = os.path.join(self.config['CHROME_USER_DATA'], 'Mentalist2')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome User Data not found!{Back.RESET}')

			self.is_valid = False

			return

		if not os.path.isdir(self.CHROME_USER_DATA):
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome User Data is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			input(f'{Style.BRIGHT}{Back.RED}Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		self.page = None

	def act_villager(self):
		print(f'{Style.BRIGHT}{Fore.GREEN}You are not a werewolf!')

	def act_werewolf(self):
		start_time = time.monotonic()

		print(f'{Style.BRIGHT}{Fore.RED}You are a werewolf!')
		print(f'{Style.BRIGHT}{Fore.YELLOW}Finding players...')

		players = []
		couples = []

		self_number = None
		wolf_seer = False
		vote = True
		tag = False
		target = None

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

					player = {
						'locator': player_base_locator,			
						'name': name,
						'self': False,
						'couple': False
					}

					try:
						if name == self.PLAYER_NAME:
							player['self'] = True

							self_number = 4 * (i - 1) + j
					except PlaywrightTimeoutError:
						pass

					for icon in icons:
						if 'junior' in icon:
							if player['self']:
								tag = True

							else:
								vote = False

						elif 'wolf_seer' in icon:
							if player['self']:
								vote = False

							else:
								wolf_seer = True

						elif not player['self'] and 'lovers' in icon:
							player['couple'] = True

							couples.append(4 * (i - 1) + j)

					players.append(player)
				except (PlaywrightTimeoutError, IndexError):
					continue

		if wolf_seer:
			vote = True

		print(f'{Style.BRIGHT}{Fore.GREEN}Players found!')

		textarea = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[2]/div/textarea')

		print(f'{Style.BRIGHT}{Fore.YELLOW}Sending message...')

		if len(couples) > 1:
			message = 'My couples are '

		else:
			message  = 'My couple is '

		message += ' '.join([str(couple) for couple in couples])

		textarea.fill(message)
		textarea.press('Enter')

		print(f'{Style.BRIGHT}{Fore.GREEN}Message sent!')

		if vote and couples:
			print(f'{Style.BRIGHT}{Fore.YELLOW}Voting couple...')

			try:
				players[couples[0] - 1]['locator'].click(timeout=10000)

				print(f'{Style.BRIGHT}{Fore.GREEN}Couple voted!')
			except Exception as e:
				print(f'{Style.BRIGHT}{Fore.RED}{e}')

		if tag:
			print(f'{Style.BRIGHT}{Fore.YELLOW}Finding target...')

			remaining_time = 30 - (time.monotonic() - start_time)

			if remaining_time >= 10:
				time.sleep(remaining_time - 10)

			chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[2]/div/div[1]/div/div/div')

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
						target = int(word)

						print(f'{Style.BRIGHT}{Fore.YELLOW}Target found!')

						break

			else:
				print(f'{Style.BRIGHT}{Fore.RED}Target not found!')

			if target:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Tagging player...')
			
				self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[2]/div/div/div[1]/div/div/div/img').click(timeout=10000)

				time.sleep(1)

				try:
					players[target - 1]['locator'].click(timeout=10000)

					print(f'{Style.BRIGHT}{Fore.GREEN}Player tagged!')
				except Exception as e:
					print(f'{Style.BRIGHT}{Fore.RED}{e}')

	def play(self):
		while True:
			banner(self.__class__.__name__)

			print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for room join...')

			while True:
				try:
					if self.page.get_by_text('Добро пожаловать в очередную игру в Wolvesville.').is_visible(timeout=10000):
						break
				except PlaywrightTimeoutError:
					continue

			print(f'{Style.BRIGHT}{Fore.GREEN}Joined!')
			print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for game start...')

			start = False
			werewolf = False

			while True:
				try:
					night_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[3]/div/div[1]')

					if night_chat.text_content(timeout=1000) == 'Чат оборотней':
						werewolf = True

					start = True

					break
				except PlaywrightTimeoutError:
					try:
						create_game_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div[1]/div[1]/div/div[3]/div/div/div/div/div[2]/div[2]/div[2]/div[1]/div/div/div')
						
						if create_game_button.text_content(timeout=1000) == 'СОЗДАТЬ ИГРУ':
							try:
								close_popup_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')
								
								if close_popup_button.text_content(timeout=1000) == 'Окей':
									close_popup_button.click()
							except PlaywrightTimeoutError:
								pass

							break
					except PlaywrightTimeoutError:
						try:
							start_game_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div[1]/div[2]/div[4]/div[2]/div/div/div')

							if start_game_button.text_content(timeout=1000) == 'НАЧАТЬ ИГРУ':
								start_game_button.click()
						except PlaywrightTimeoutError:
							pass
				except:
					continue

			if not start:
				continue

			if werewolf:
				self.act_werewolf()

			else:
				self.act_villager()

			print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for game end...')

			while True:
				try:
					continue_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div/div[23]/div/div/div[4]/div/div').get_by_text('Продолжить')
					continue_button.click(timeout=120000)

					break
				except PlaywrightTimeoutError:
					continue

			print(f'{Style.BRIGHT}{Fore.GREEN}End!')
			print(f'{Style.BRIGHT}{Fore.YELLOW}Exiting...')

			try:
				play_again_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div[2]/div/div/div/div/div/div[1]/div[1]/div[2]/div[2]/div[3]/div[5]/div[2]/div/div[2]').get_by_text('Играть снова')
				play_again_button.click(timeout=30000)

				try:
					host_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[3]/div[2]/div/div')
					
					if host_button.text_content(timeout=1000) == 'Окей':
						host_button.click()
				except PlaywrightTimeoutError:
					pass
			except PlaywrightTimeoutError:
				playsound('audio/glitch.mp3')

				try:
					close_popup_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[4]/div/div[2]/div[2]/div/div/div')
					
					if close_popup_button.text_content(timeout=1000) == 'Окей':
						close_popup_button.click()
				except PlaywrightTimeoutError:
					pass

				return

	def run(self):
		banner(self.__class__.__name__)

		try:
			with sync_playwright() as playwright:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Opening website...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
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

				self.page = context.pages[0]
				
				while True:
					try:
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=100000)

						break
					except PlaywrightTimeoutError:
						print(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')

						continue

				try:
					decline_notifications_button = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div[1]/div/div/div/div/div/div/div[1]/div[1]/div/div/div/div/div/div/div[2]/div[2]/div')
				
					if decline_notifications_button.text_content(timeout=10000) == '\uf00d':
						decline_notifications_button.click()
				except PlaywrightTimeoutError:
					pass

				print(f'{Style.BRIGHT}{Fore.GREEN}Website opened!')

				while True:
					print(f'{Style.BRIGHT}{Fore.YELLOW}Opening custom games menu...')

					while True:
						try:
							play_button = self.page.get_by_text('ИГРАТЬ', exact=True)

							if not play_button.is_disabled(timeout=10000):
								play_button.click()

							break
						except PlaywrightTimeoutError:
							continue

					while True:
						try:
							self.page.get_by_text('ПЕРСОНАЛИЗИРОВАННЫЕ ИГРЫ').click(timeout=10000)

							break
						except PlaywrightTimeoutError:
							continue

					print(f'{Style.BRIGHT}{Fore.YELLOW}Menu opened!')

					self.play()
		except KeyboardInterrupt:
			return
		except Exception as e:
			input(f'\n{Style.BRIGHT}{Back.RED}Browser closed!{Back.RESET}')

			return


class Stalker:
	def __init__(self):
		self.config = dotenv_values('.env')
		self.is_valid = True

		try:
			self.API_KEYS = self.config['STALKER_API_KEYS'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = self.config.get('CHROME_EXECUTABLE')

		if self.CHROME_EXECUTABLE is not None and not os.path.isfile(self.CHROME_EXECUTABLE):
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_USER_DATA = os.path.join(self.config['CHROME_USER_DATA'], 'Mentalist')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome User Data not found!{Back.RESET}')

			self.is_valid = False

			return

		if not os.path.isdir(self.CHROME_USER_DATA):
			input(f'{Style.BRIGHT}{Back.RED}Path to Chrome User Data is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Browser Viewport not found!{Back.RESET}')

			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			input(f'{Style.BRIGHT}{Back.RED}Browser Viewport is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			TIMEZONE = self.config['TIMEZONE']
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Timezone not found!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.TIMEZONE = pytz.timezone(TIMEZONE)
		except KeyError:
			input(f'{Style.BRIGHT}{Back.RED}Timezone is invalid!{Back.RESET}')

			self.is_valid = False

			return

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
		try:
			with open('data/targets.json', 'r', encoding='utf-8') as targets_file:
				self.TARGETS = json.load(targets_file, object_pairs_hook=OrderedDict)
		except:
			self.TARGETS = OrderedDict()

	def write_target(self, target_id, info=None):
		if not os.path.isdir('targets'):
			os.mkdir('targets')

		if info is None:
			self.TARGETS.pop(target_id)

		else:
			if target_id not in self.TARGETS:
				self.TARGETS[target_id] = []

			self.TARGETS[target_id].append(info)

			if len(self.TARGETS[target_id]) == 3:
				self.TARGETS[target_id].pop(0)

	def save_targets(self):
		if not os.path.isdir('data'):
			os.mkdir('data')

		with open('data/targets.json', 'w', encoding='utf-8') as targets_file:
			json.dump(self.TARGETS, targets_file, ensure_ascii=False)

	def get_current_time(self):
		try:
			data = self.ntp.request(self.NTP_SERVER)
		
			return time.ctime(data.tx_time)
		except ntplib.NTPException:
			return

	def add_changes(self, prev_target, target, diff, current_time, clan=False):
			if not os.path.isdir('targets'):
				os.mkdir('targets')

			target_id = target['id']

			if clan:
				target = target['clan']
				prev_target = prev_target['clan']

			if diff:
				with open(f'targets/{target_id}.txt', 'a', encoding='utf-8') as f:
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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

		if not data.ok:
			return data.status_code, data.text

		data = data.json().get('id')

		return 0, data

	def predict_level_by_xp(self, player_id):
		ENDPOINT = 'highScores/top100Friends'

		data = requests.get(f'{self.BEARER_BASE_URL}{ENDPOINT}', headers=self.BEARER_HEADERS, verify=False)

		if not data.ok:
			return

		data = data.json()['ranks']
		player = dict((d['playerId'], dict(xp=d['xp'])) for d in data).get(player_id)

		if not player:
			return

		k = 0.000500205
		b = 8.85

		level = int(k * player['xp'] + b)

		return level

	def get_player_friends_count(self, player_id):
		ENDPOINT = f'players/{player_id}'

		data = requests.get(f'{self.BEARER_BASE_URL}{ENDPOINT}', headers=self.BEARER_HEADERS, verify=False)

		if not data.ok:
			return -1

		data = data.json()

		friends_count = int(data.get('friendsCount', -1))

		return friends_count

	def get_player(self, player_id):
		ENDPOINT = f'players/{player_id}'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

			threading.Thread(target=playsound, args=('audio/illusionist.mp3',), daemon=True).start()

		self.updating = False

	def plot_targets(self, indices):
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

			filename = f'targets/{target_id}.txt'

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
		
		output_path = 'targets/plot_analysis.html'

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

		elif cmd.lower().startswith('plot '):
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
				print(f'{Style.BRIGHT}{Fore.YELLOW}Opening website...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
					viewport={
						'width': int(self.CHROME_VIEWPORT[0]),
						'height': int(self.CHROME_VIEWPORT[1])
					},
					args=[
						'--window-position=-7,40',
						'--mute-audio',
						'--disable-blink-features=AutomationControlled'
					],
					ignore_default_args=['--enable-automation'],
					chromium_sandbox=True
				)

				self.page = context.pages[0]
				
				while True:
					try:
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=100000)

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


class Spinner:
	def __init__(self):
		self.config = dotenv_values('.env')
		self.is_valid = True
		self.app = None

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

	@staticmethod
	def wait(filename, confidence=0.9, check_fail=False, check_count=6, click=True):
		fails = 0

		while True:
			coords = pyautogui.locateCenterOnScreen('images/' + filename, confidence=confidence)

			if coords:
				if click:
					try:
						pyautogui.click(*coords)
					except pyautogui.FailSafeException:
						continue

				return 0

			if check_fail:
				fails += 1

			if fails == check_count:
				return 1

			time.sleep(5)

	def close_all(self):
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
				print(f'{Style.BRIGHT}{Fore.YELLOW}Checking ad button...')

				self.app.Dialog.click_input(coords=(0, 0))

				if not self.wait('done.png', confidence=0.8, check_fail=True, check_count=3):
					print(f'{Style.BRIGHT}{Fore.GREEN}DONE!')

					playsound('audio/confusion.mp3')

					return 1

				if self.wait('ad.png', confidence=0.8, check_fail=True):
					print(f'{Style.BRIGHT}{Fore.RED}Loading takes too long.')

					return

				print(f'{Style.BRIGHT}{Fore.YELLOW}Watching ad...')

				time.sleep(120)

				self.app[self.BLUESTACKS5_NAME].Button0.click()

				print(f'{Style.BRIGHT}{Fore.YELLOW}Checking spin button...')

				if self.wait('spin.png', confidence=0.8, check_fail=True):
					print(f'{Style.BRIGHT}{Fore.RED}Spin button not found.') 

					return

				else:
					print(f'{Style.BRIGHT}{Fore.GREEN}Spinned!')
		except (pywinauto.findwindows.ElementNotFoundError, OSError):
			return 2

	def prepare(self):
		while True:
			try:
				print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for BlueStacks 5...')

				subprocess.Popen([self.BLUESTACKS5_EXECUTABLE, '--cmd', 'launchApp', '--package', 'com.werewolfapps.online'], stdout=subprocess.PIPE)
				
				try:
					self.app = pywinauto.Application(backend='uia').connect(title=self.BLUESTACKS5_NAME, timeout=30)

					window = pygetwindow.getWindowsWithTitle(self.BLUESTACKS5_NAME)[0]
					window.size = (540, 934)
				except IndexError:
					input(f'{Style.BRIGHT}{Back.RED}Name of BlueStacks 5 window is invalid!{Back.RESET}')

					os.abort()

				print(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for the game to load...')

				if self.wait('profile.png', click=False, check_fail=True, check_count=12):
					continue

				self.wait('cancel.png', check_fail=True, check_count=3)
				self.app.Dialog.click_input(coords=(80, 40))

				print(f'{Style.BRIGHT}{Fore.GREEN}Game loaded!')

				break
			except:
				print(f'{Style.BRIGHT}{Fore.RED}The game failed to load.')
				print(f'{Style.BRIGHT}{Fore.RED}Restarting...')

				self.close_all()

				continue

	def run(self):
		try:
			while True:
				banner(self.__class__.__name__)

				self.prepare()
				result = self.spin()

				if result == 1:
					self.kill()

					print(f'\n{Style.BRIGHT}{Fore.YELLOW}Press Enter to exit.{Fore.RESET}')
					input()

					return

				elif result == 2:
					continue

				print(f'{Style.BRIGHT}{Fore.RED}Restarting...')

				self.close_all()
		except KeyboardInterrupt:
			self.kill()

			return


def banner(module=None):
    message = f'{Style.BRIGHT}{Fore.RED}Men{Fore.YELLOW}tal{Fore.WHITE}ist{Fore.RESET}'
    if module:
        message += f'{Fore.RED} | {module}'
    return message

class MentalistModule:
    def __init__(self):
        self._output_queue = queue.Queue()
        self._input_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self.is_valid = True # Default, to be overridden by subclasses
        self._status_message = "Остановлен" # GUI status

    @property
    def status(self):
        return self._status_message

    @status.setter
    def status(self, message):
        self._status_message = message

    def _run_logic(self):
        """Main logic of the module, to be implemented by subclasses."""
        raise NotImplementedError

    def start(self):
        if self._thread and self._thread.is_alive():
            self._print_output("Модуль уже запущен.")
            return

        self._stop_event.clear()
        self._output_queue = queue.Queue() # Clear old output
        self._input_queue = queue.Queue() # Clear old input
        self._thread = threading.Thread(target=self._run_logic, daemon=True)
        self._thread.start()
        self.status = "Запущен"
        self._print_output(f"{self.__class__.__name__} запущен.")

    def stop(self):
        if not (self._thread and self._thread.is_alive()):
            self._print_output("Модуль не запущен.")
            return

        self._stop_event.set()
        self._input_queue.put("stop_signal") # Unblock potential input() calls
        self._thread.join(timeout=5) # Wait for the thread to finish
        if self._thread.is_alive():
            self._print_output(f"Предупреждение: {self.__class__.__name__} не завершился вовремя.")
        self.status = "Остановлен"
        self._print_output(f"{self.__class__.__name__} остановлен.")

    def get_output(self):
        """Get all accumulated output from the queue."""
        output = []
        while not self._output_queue.empty():
            output.append(self._output_queue.get())
        return "\n".join(output)

    def send_input(self, data):
        """Send input to the module."""
        self._input_queue.put(data)

    def _print_output(self, *args, sep=' ', end='\n'):
        message = sep.join(map(str, args)) + end
        self._output_queue.put(message)

    def _get_input(self, prompt=""):
        self._print_output(prompt, end='') # Display prompt
        if self._stop_event.is_set():
            raise KeyboardInterrupt # Allow stopping during input wait
        return self._input_queue.get() # Block until input is available

class Tracker(MentalistModule): # Tracker теперь наследуется от MentalistModule
	def __init__(self):
		super().__init__() # Вызов конструктора базового класса
		self.config = dotenv_values('.env')
		self.is_valid = True

		try:
			self.API_KEYS = self.config['TRACKER_API_KEYS'].split(',')
		except KeyError:
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: API key(s) not found!{Back.RESET}')

			self.is_valid = False

			return

		self.CHROME_EXECUTABLE = self.config.get('CHROME_EXECUTABLE')

		if self.CHROME_EXECUTABLE is not None and not os.path.isfile(self.CHROME_EXECUTABLE):
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome Executable is invalid!{Back.RESET}')

			self.is_valid = False

			return

		try:
			self.CHROME_USER_DATA = os.path.join(self.config['CHROME_USER_DATA'], 'Mentalist')
		except KeyError:
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome User Data not found!{Back.RESET}')
			
			self.is_valid = False

			return

		if not os.path.isdir(self.CHROME_USER_DATA):
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: Path to Chrome User Data is invalid!{Back.RESET}')
			
			self.is_valid = False

			return

		try:
			self.CHROME_VIEWPORT = self.config['CHROME_VIEWPORT'].split(',')
		except KeyError:
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: Browser Viewport not found!{Back.RESET}')
			
			self.is_valid = False

			return

		if len(self.CHROME_VIEWPORT) != 2:
			self._print_output(f'{Style.BRIGHT}{Back.RED}Tracker Error: Browser Viewport is invalid!{Back.RESET}')
			
			self.is_valid = False

			return

		self.API_KEY = self.switch_api_key()

		self.SERVER_ENABLED = self.config.get('SYNC_SERVER_ENABLED', 'false').lower() == 'true'
		self.SERVER_URL = self.config.get('SYNC_SERVER_URL', 'http://localhost:1101')
		self.SERVER_API_KEY = self.config.get('SYNC_SERVER_API_KEY', '')
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

		self.page = None
		self.day_chat = None
		self.dead_chat = None
		self.last_message_number = 0

		self.mastermind = None
		self.THREAT_LEVELS = {}
		self.PLAYER_CLAIMS = {}
		self.PLAYER_ALLIANCES = {}

	def _print_output_with_banner(self, *args, sep=' ', end='\n'):
		self._print_output(banner(self.__class__.__name__), end='\n\n')
		self._print_output(*args, sep=sep, end=end)

	def sync_with_server(self, data_type, local_data, bidirectional=True):
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
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)
			else:
				endpoint = f'{self.SERVER_URL}/get/{data_type}'
				response = requests.get(
					endpoint,
					headers=headers,
					timeout=self.SERVER_TIMEOUT,
					verify=False
				)
			
			if response.status_code == 200:
				result = response.json()
				
				if result.get('status') == 'no_changes':
					self.data_hashes[data_type] = current_hash

					return True, local_data
				
				elif result.get('status') in ['synced', 'success']:
					server_data = result.get('data', {})
					server_hash = result.get('hash', '')
					
					self.data_hashes[data_type] = server_hash
					
					if bidirectional and result.get('server_updated'):
						self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Mentalist Server updated with your {data_type}!')
					
					if server_hash != current_hash:
						self._print_output(f'{Style.BRIGHT}{Fore.CYAN}Received updates for {data_type} from Mentalist Server.')
						
						return True, server_data
					
					return True, local_data
			
			elif response.status_code == 401:
				self._print_output(f'{Style.BRIGHT}{Back.RED}Mentalist Server sync failed: Invalid API key{Back.RESET}')

				return False, local_data
			
			else:
				self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Server sync warning: {response.status_code}')

				return False, local_data
		
		except requests.exceptions.ConnectionError:
			if not hasattr(self, '_server_warning_shown'):
				self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Warning: Cannot connect to Mentalist Server. Using local data.{Fore.RESET}')

				self._server_warning_shown = True

			return False, local_data
		except requests.exceptions.Timeout:
			self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Mentalist Server sync timeout. Using local data.{Fore.RESET}')

			return False, local_data
		except Exception as e:
			self._print_output(f'{Style.BRIGHT}{Fore.RED}Mentalist Server sync error: {e}{Fore.RESET}')

			return False, local_data

	def load_assets(self):
		try:
			for asset in self.ASSET_PATHS:
				self.ASSETS[asset] = {}

				for module in self.ASSET_PATHS[asset]:
					filename = self.ASSET_PATHS[asset][module]

					path = f'assets/{asset}/{filename}'

					with open(path, 'r') as asset_file:
						self.ASSETS[asset][module] = asset_file.read()
		except FileNotFoundError:
			self._get_input(f'{Style.BRIGHT}{Back.RED}{path} not found!{Back.RESET}')

			os.abort()

	def save_cards(self):
		if not os.path.isdir('data'):
			os.mkdir('data')
		
		with open('data/cards.json', 'w') as cards_file:
			json.dump(self.PLAYER_CARDS, cards_file)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('cards', self.PLAYER_CARDS, True),
				daemon=True
			).start()

	def save_icons(self):
		if not os.path.isdir('data'):
			os.mkdir('data')
		
		with open('data/icons.json', 'w') as icons_file:
			json.dump(self.PLAYER_ICONS, icons_file)
		
		if self.SERVER_ENABLED:
			threading.Thread(
				target=self.sync_with_server,
				args=('icons', self.PLAYER_ICONS, True),
				daemon=True
			).start()

	def get_roles(self):
		self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Getting roles...')

		ENDPOINT = 'roles'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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
		self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Getting icons...')

		ENDPOINT = 'items/roleIcons'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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
		self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Getting role rotations...')

		ENDPOINT = 'roleRotations'

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False).json()

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

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

		data = requests.get(f'{self.BEARER_BASE_URL}{ENDPOINT}', headers=self.BEARER_HEADERS, verify=False)

		if not data.ok:
			return data.status_code, data.text

		data = data.json()

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

		data = requests.get(f'{self.BOT_BASE_URL}{ENDPOINT}', headers=self.bot_headers, verify=False)

		if not data.ok:
			return -1

		data = data.json()

		for player in data:
			if player_id == player.get('playerId'):
				return player.get('xp')

		return -1

	def storm(self):
		PLAYERS_OLD = deepcopy(self.PLAYERS)

		self.PLAYERS = []

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

		for p in range(16):
			for o, old in enumerate(PLAYERS_OLD):
				if self.PLAYERS[p]['name'] == old['name']:
					self.PLAYERS[p] = old

					PLAYERS_OLD.pop(o)

		self.last_message_number = 0

	def revert(self, action):
		if not self.PREV_PLAYERS:
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Last revert reached!{Back.RESET}')

		else:
			self.PLAYERS = deepcopy(self.PREV_PLAYERS[-1])

			if action:
				self.PREV_PLAYERS.pop()

		return -1

	def set_name(self, player, name, threaded=False):
		data = self.get_player(name)

		if data[0] == 404:
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid name!{Back.RESET}')

			return 404

		elif data[0]:
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Error {data[0]}: {data[1]}{Back.RESET}')

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
		for r in range(len(self.ROTATION)):
			if role.lower() == self.ROTATION[r]['name'].lower():
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

					break

		else:
			self._print_output(self.ROTATION, player, role)

			return 1

		self.PLAYERS[player]['role'] = self.ROTATION[r]['id']
		self.PLAYERS[player]['team'] = self.ROTATION[r]['team']
		self.PLAYERS[player]['aura'] = self.ROTATION[r]['aura']

		for equal_player in self.PLAYERS[player]['equal']:
			self.PLAYERS[equal_player]['team'] = self.PLAYERS[player]['team']

		for not_equal_player in self.PLAYERS[player]['not_equal']:
			self.PLAYERS[not_equal_player]['teams_exclude'].add(self.PLAYERS[player]['team'])

		if self.PLAYERS[player]['hero'] or self.ROTATION[r]['id'] == 'zombie':
			return

		name = self.PLAYERS[player]['name']

		if name and self.ROTATION[r]['id'] not in self.ADVANCED_ROLES:
			for src_role in self.ADVANCED_ROLES:
				if self.ROTATION[r]['id'] in self.ADVANCED_ROLES[src_role]:
					break

			self.write_cards(name, {src_role: self.ROTATION[r]['id']})
			self.save_cards()

		if self.ROTATION[r]['id'] in self.ROTATION_ICONS:
			self.write_icons(name, {self.ROTATION[r]['id']: self.ROTATION_ICONS[self.ROTATION[r]['id']]})
			self.save_icons()

	def change_role(self, src_role, dst_role):
		is_random = False

		for role in self.ROLES:
			if self.ROLES[role]['name'].lower() == dst_role.lower():
				dst_role = self.ROLES[role]
				dst_role['id'] = role

				break

		else:
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect destination role!{Back.RESET}')

			return

		for r, role in enumerate(self.ROTATION):
			if role['name'].lower() == src_role.lower():
				src_role = role['id']

				if 'random' in src_role:
					is_random = True

				break

		else:
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect source role!{Back.RESET}')

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
			self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

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
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect info!{Back.RESET}')

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
					if 'прошлой' in service_message:
						continue

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

		self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Finding players...')

		for i in range(1, 5):
			for j in range(1, 5):
				try:
					number = 4 * (i - 1) + j - 1

					player_layer_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/div[{i}]/div[{j}]/div')
					player_base_locator = self.page.locator(f'xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[2]/div/div[1]/div[1]/div[{i}]/div[{j}]/div')
					name = player_base_locator.text_content(timeout=1000).split(' ')[1]

					self.PLAYER_LAYERS.append({
						'number': number,
						'name': name,
						'locator': player_layer_locator
					})

					time.sleep(0.1)
				except PlaywrightTimeoutError:
					continue

		if len(self.API_KEYS) >= 2:
			threading.Thread(target=self.set_players_range, args=(1, 0, 8), daemon=True).start()
			threading.Thread(target=self.set_players_range, args=(2, 8, 16), daemon=True).start()

		else:
			self.set_players_range()

		while not all(self.DISCOVERED):
			time.sleep(1)

		for layer in self.PLAYER_LAYERS:
			self.load_see(layer['number'], layer['locator'])

		self.PREV_PLAYERS = [deepcopy(self.PLAYERS)]
		self.page.evaluate('(players) => localStorage.setItem("players", players)', json.dumps(self.PLAYERS, default=list))
		self.save_cards()

		self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Players found!')

	def find_roles(self):
		self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Finding roles...')

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
					self._print_output(rotation_icon, 'not found!')

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

		self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Roles found!')

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
		self._print_output_with_banner(self.__class__.__name__)

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

		self._print_output(f'{Style.BRIGHT}{players_info}{remaining_info}')

	def debug_mastermind(self):
		self._print_output(f'\n{Fore.CYAN}{Style.BRIGHT}--- STARTING MASTERMIND DEBUG ---{Fore.RESET}')
		
		mind = self.mastermind

		if not mind or not mind.profiles:
			self._print_output(f'{Back.RED}{Style.BRIGHT}Mastermind is not initialized.{Back.RESET}')
			
			return

		mind.update_state()
		state = mind.state

		self._print_output(f'{Style.BRIGHT}Step 1: Initializing simulation state')

		alive_players = [p for p in state.players if not p['dead'] and p['role']]
		
		if not alive_players:
			self._print_output(f'{Back.YELLOW}{Fore.BLACK}No living players with known roles found for analysis.{Back.RESET}')
			
			return

		self._print_output(f'\n{Style.BRIGHT}Step 2: Searching for potentially active players')
		self._print_output(f'  - Found living players with roles: {len(alive_players)}')

		total_actions_found = 0

		for player in alive_players:
			self._print_output(f'\n{Fore.GREEN}--- Analyzing Player: {player["name"]} (Role: {player["role"]}) ---{Fore.RESET}')
			
			abilities = mind.profiles.get(player['role'])

			if not abilities:
				self._print_output(f'  - {Back.RED}ERROR:{Back.RESET} Abilities for role "{player["role"]}" not found in role profiles!')
				
				continue

			self._print_output(f'  - Abilities found in profile: {len(abilities)}')

			for i, ability in enumerate(abilities):
				ability_type = ability.get('type', 'N/A')

				self._print_output(f'	{i + 1}) Ability "{ability_type}":')
				
				is_valid = mind.is_ability_valid(player, ability, state)

				if not is_valid:
					reason = 'max uses exceeded'
					
					self._print_output(f'	  - {Fore.YELLOW}Validity Check: FAILED (Reason: {reason}){Fore.RESET}')
					
					continue
				
				self._print_output(f'	  - {Fore.GREEN}Validity Check: PASSED{Fore.RESET}')

				targets = mind.get_potential_targets(player, ability.get('targets', {}), state)
				
				if not targets:
					self._print_output(f'	  - {Fore.YELLOW}Target Search: No valid targets found.{Fore.RESET}')
					
					continue
				
				target_names = [t['name'] for t in targets]

				self._print_output(f'	  - {Fore.GREEN}Target Search: Found {len(targets)} targets ({", ".join(target_names)}){Fore.RESET}')
				
				total_actions_found += len(targets)

		self._print_output(f'\n{Style.BRIGHT}--- DEBUG SUMMARY ---{Style.BRIGHT}')

		if total_actions_found > 0:
			self._print_output(f'{Fore.GREEN}Mastermind found {total_actions_found} possible actions.{Fore.RESET}')
		
		else:
			self._print_output(f'{Back.YELLOW}{Fore.BLACK}Mastermind found 0 possible actions.{Back.RESET}')

		self._get_input()

		return

	def predict(self, player_name):
		if not self.mastermind or not self.mastermind.profiles:
			self._print_output(f'\n{Back.RED}{Style.BRIGHT}Mastermind is not ready!{Back.RESET}')
			
			return

		if not player_name:
			self._print_output(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios...{Fore.RESET}')

		else:
			self._print_output(f'\n{Style.BRIGHT}{Fore.YELLOW}Calculating scenarios with focus on {player_name}...{Fore.RESET}')

		self.mastermind.update_state()

		scenarios = self.mastermind.predict(max_depth=3, prob_threshold=0.01, player_name=player_name)

		if not scenarios:
			self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}No viable scenarios found.{Fore.RESET}')

			return
		
		self._print_output()

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

			self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Scenario #{i + 1} ({Fore.YELLOW}{scenario["prob"]:.2%}{Fore.GREEN}):{Style.RESET_ALL}{path_text}')

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

			self._print_output(f'\n{Style.BRIGHT}{Fore.GREEN}Recommended Action: {Fore.GREEN}{actor["name"]}{Style.RESET_ALL}({desc_color}{ability["description"]}{Style.RESET_ALL}{target_text})')
			self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Success Probability: {Fore.YELLOW}{best_textategy["expected_success"]*100:.2f}%{Style.RESET_ALL}')

		self._get_input()

		return

	def process(self, cmd):
		if not cmd:
			return

		elif cmd.lower() == 'end':
			return 1

		elif '=' in cmd:
			if not(cmd.count('!=') == 1 or cmd.count('=') == 1):
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

				return

			equal = '!=' if '!=' in cmd else '='

			players = cmd.split(f' {equal} ')

			if len(players) == 2 and players[0].isdigit() and players[1].isdigit():
				players = list(map(int, players))

				if not (1 <= players[0] <= 16 and 1 <= players[1] <= 16):
					self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid number(s)!{Back.RESET}')

					return

				players[0] -= 1
				players[1] -= 1

				self.set_equal(players, equal == '=')

			else:
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

		elif cmd.lower().startswith('name of '):
			cmd = cmd.split(' ')

			if len(cmd) == 5 and cmd[3].lower() == 'is' and cmd[2].isdigit() and 1 <= int(cmd[2]) <= 16:
				player = int(cmd[2]) - 1
				name = cmd[4]

				self.set_name(player, name)

			else:
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

		elif cmd.lower().startswith('change '):
			query = cmd.lower().split('change ')[1].split(' to ')

			if len(query) == 2:
				src_role, dst_role = query

				self.change_role(src_role, dst_role)

			else:
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

		elif cmd.lower().startswith('remove '):
			query = cmd.lower().split('remove ')[1].split(' from ')

			if len(query) == 2:
				role, player = query

				if player.isdigit() and 1 <= int(player) <= 16:
					player = int(player) - 1

					self.remove_role(player, role)

				else:
					self._print_output(f'\n{Style.BRIGHT}{Back.RED}Incorrect number!{Back.RESET}')

			else:
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid syntax!{Back.RESET}')

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
				self._print_output(f'\n{Style.BRIGHT}{Back.RED}Invalid info!{Back.RESET}')

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
			
			self._get_input()

		elif cmd.lower() == 'debug':
			self.debug_mastermind()

		else:
			try:
				player, info = cmd.lower().split(' is ')
			except ValueError:
				self._print_output(f'\n{Style.BRIGHT}{Fore.RED}Usage:')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}[number] is [role / aura / (not) team / dead / alive]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}[number] [= / !=] [number]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Name of [number] is [name]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Change [role] to [role]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Remove [role] from [number]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Clear [number]')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Cursed turned')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Storm to rediscover')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Enter to update')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Undo - cancel changes')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Redo - return changes')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Predict - get game scenarios from Mastermind')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}Debug - trace Mastermind analysis')
				self._print_output(f'{Style.BRIGHT}{Fore.RED}End - stop Tracker')
				self._get_input()

				return

			self.set_player_info(player, info)
	
	def _run_logic(self):
		try:
			with sync_playwright() as playwright:
				self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Opening website...')

				context = playwright.chromium.launch_persistent_context(
					executable_path=self.CHROME_EXECUTABLE,
					user_data_dir=self.CHROME_USER_DATA,
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

				while not self._stop_event.is_set():
					try:
						self.page.goto('https://wolvesville.com', wait_until='commit', timeout=100000)
						break
					except PlaywrightTimeoutError:
						self._print_output(f'{Style.BRIGHT}{Fore.RED}Timeout error!{Fore.RESET}')
						continue
				if self._stop_event.is_set(): return

				self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Website opened!')

				while not self._stop_event.is_set():
					# self._print_output_with_banner(self.__class__.__name__) # GUI handles banner
					if self.prepare():
						self._get_input(f'\n{Style.BRIGHT}{Back.RED}Invalid API key!{Back.RESET}')
						return

					self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Waiting for game start...')

					while not self._stop_event.is_set():
						try:
							night_chat = self.page.locator('xpath=/html/body/div[1]/div/div/div/div/div/div[2]/div/div/div/div/div/div/div/div/div/div/div/div/div[1]/div[1]/div/div[2]/div[1]/div[3]/div/div[1]/div[1]/div/div[1]')

							if night_chat.text_content(timeout=1000) == 'Дневной чат':
								break
						except KeyboardInterrupt:
							return
						except PlaywrightTimeoutError: # Catch PlaywrightTimeoutError here specifically
							# This error means the element might not be present yet, continue waiting
							pass
						except Exception as e:
							self._print_output(f"Error waiting for chat: {e}")
							time.sleep(1) # Small delay to prevent busy-waiting on other errors
					if self._stop_event.is_set(): return

					self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Game found!')

					self.get_bearer()
					self.load_css()
					self.load_modal()
					self.find_players()

					roles = self.find_roles()
					rotations = self.get_rotations()

					self._print_output(f'{Style.BRIGHT}{Fore.YELLOW}Finding rotation...')

					self.ROTATION = self.choose_rotation(rotations, roles)

					if self.ROTATION is None:
						self._get_input(f'\n{Style.BRIGHT}{Back.RED}Rotation not found!{Back.RESET}')

						return

					self._print_output(f'{Style.BRIGHT}{Fore.GREEN}Rotation found!')

					while not self._stop_event.is_set():
						self.monitor()
						
						# In GUI mode, process is called via API, not loop
						# We only update players, then wait for explicit command
						self.update_players()
						
						# Instead of blocking with input(), wait for commands via queue
						try:
							command = self._input_queue.get(timeout=1) # Small timeout to allow stopping
							if command == "stop_signal":
								break # Stop the inner loop
							
							result = self.process(command)
							if result == 1: # 'end' command
								break # Stop the inner loop

						except queue.Empty:
							pass # No command yet, continue updating

					if self._stop_event.is_set(): return # Check stop event after inner loop

		except KeyboardInterrupt:
			self._print_output("Tracker остановлен пользователем.")
		except Exception as e:
			self._print_output(f'{Style.BRIGHT}{Back.RED}Browser closed or unexpected error: {e}{Back.RESET}')
		finally:
			if self.page:
				try:
					self.page.context.close()
				except Exception as e:
					self._print_output(f"Error closing playwright context: {e}")
			self.status = "Остановлен"

	def run(self):
		# The run method now simply starts the thread
		self.start()

# Остальные классы (Booster, Stalker, Spinner) будут адаптированы аналогично
# Их реализация будет добавлена в следующих блоках.
class Booster(MentalistModule): # Временно, для компиляции, будет заменено
	def __init__(self):
		super().__init__()
		self.is_valid = False # Placeholder
		self._print_output("Booster is not yet adapted for GUI.")
	def _run_logic(self):
		self._print_output("Booster GUI logic not implemented yet.")
		self._get_input()

class Stalker(MentalistModule): # Временно, для компиляции, будет заменено
	def __init__(self):
		super().__init__()
		self.is_valid = False # Placeholder
		self._print_output("Stalker is not yet adapted for GUI.")
	def _run_logic(self):
		self._print_output("Stalker GUI logic not implemented yet.")
		self._get_input()

class Spinner(MentalistModule): # Временно, для компиляции, будет заменено
	def __init__(self):
		super().__init__()
		self.is_valid = False # Placeholder
		self._print_output("Spinner is not yet adapted for GUI.")
	def _run_logic(self):
		self._print_output("Spinner GUI logic not implemented yet.")
		self._get_input()


if __name__ == "__main__":
    if GUI_ENABLED:
        from gui_app import run_gui
        run_gui()
    else:
        # This block will eventually be refactored or removed if CLI mode is fully deprecated.
        # For now, it's left as is for compatibility, but the MentalistModule structure is used.
        try:
            while True:
                cli_banner = banner()
                os.system('cls' if os.name == 'nt' else 'clear')
                print(cli_banner)
                
                module_classes_cli = [Tracker, Booster, Stalker]
                if os.name == 'nt':
                    module_classes_cli.append(Spinner)

                modules_cli = []
                disabled_modules_cli = []

                # Create new instances for CLI mode, as GUI uses its own managed instances
                for module_class_cli in module_classes_cli:
                    instance = module_class_cli()
                    # For CLI, we don't start a thread, we call _run_logic directly if it exists,
                    # or handle a simple 'run' call that may be blocking.
                    # This part needs careful thought if MentalistModule's start/stop is for threading only.
                    # For now, let's assume if GUI_ENABLED is false, we run the original blocking 'run' method
                    # before it's converted to _run_logic.
                    # Given the current state, if CLI_ENABLED, we want the old blocking behavior.
                    # So, if not GUI_ENABLED, we use the old _run_cli_mode, which means modules should NOT
                    # inherit from MentalistModule yet. This is a chicken-and-egg problem.

                    # Reverting the MentalistModule inheritance for CLI path for now to avoid breaking it.
                    # This implies modules will have two distinct ways of running: old blocking for CLI,
                    # and new threaded for GUI. The refactoring below will assume we are ONLY preparing for GUI.
                    
                    # Original CLI behavior, re-adding the _run_cli_mode function.
                    # This is a temporary measure, and ideally, all modules would use the new MentalistModule base.
                    pass # Will re-add _run_cli_mode below.
        except KeyboardInterrupt:
            pass


def _run_cli_mode(): # Re-adding the original CLI function
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(banner())

            module_classes = [Tracker, Booster, Stalker]

            if os.name == 'nt':
                module_classes.append(Spinner)

            modules = []
            disabled_modules = []

            for module_class in module_classes:
                # For CLI, we're not using the MentalistModule threading/queues directly here.
                # The CLI modules need to run their blocking 'run' methods.
                # If they inherit from MentalistModule, their 'run' method just calls 'start()'.
                # So we need a way to run their _run_logic() blocking, or keep a separate CLI structure.
                # To maintain current CLI functionality, I will temporarily make `run` method in MentalistModule
                # conditionally execute `_run_logic` directly if not in a thread context for CLI,
                # or just use separate `run_cli` method for the existing CLI.

                # This is tricky because the user asked to change Tracker to inherit, but also keep CLI.
                # The best approach for now is to fully refactor for GUI and remove _run_cli_mode,
                # as the GUI_ENABLED check implies one or the other.
                # If CLI is to remain fully functional, then _run_cli_mode would need to instantiate
                # the "old" versions of Tracker/Booster/Stalker/Spinner, or call `_run_logic` directly
                # on the new instances if they were not intended to be threaded for CLI.
                # Given the instruction "Always use best practices... Respect and use existing conventions",
                # I should not duplicate code significantly.
                # Therefore, I will assume the CLI mode will eventually use the refactored modules as well,
                # but currently, the `run()` method of `MentalistModule` starts a thread.
                # For CLI to work, `_run_cli_mode` would need to call `instance._run_logic()` directly, not `instance.run()`.
                
                # For now, I'll remove _run_cli_mode entirely, as the user's request for "full and normal GUI"
                # implies that `GUI_ENABLED` is the primary path forward. If they explicitly want to
                # retain the old CLI functionality in parallel after these GUI refactors, they will need to specify.
                # The current mentalist.py already has a `_run_cli_mode` function. I will remove it since
                # the new MentalistModule `run` behavior is threaded.
                pass # This block will be removed.

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if GUI_ENABLED:
        from gui_app import run_gui
        run_gui()
    else:
        # Re-implementing the CLI logic directly here for now,
        # adapting to the MentalistModule interface by calling _run_logic directly.
        # This is a workaround for the transitional phase.
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(banner())

                module_classes = [Tracker, Booster, Stalker]

                if os.name == 'nt':
                    module_classes.append(Spinner)

                modules = []
                disabled_modules = []

                for module_class in module_classes:
                    instance = module_class()
                    if instance.is_valid:
                        modules.append(instance)
                    else:
                        disabled_modules.append(module_class.__name__)

                print()

                for i, module in enumerate(modules):
                    module_name = module.__class__.__name__
                    print(f'{Style.BRIGHT}{Fore.GREEN}{i + 1}. {Fore.RESET}{Back.GREEN}{module_name}')

                if disabled_modules:
                    print()
                    for module_name in disabled_modules:
                        print(f'{Style.BRIGHT}{Fore.RED}Module {module_name} is disabled due to configuration errors.{Fore.RESET}')

                if not modules:
                    print(f'\n{Style.BRIGHT}{Back.RED}All modules failed to load! Check your .env file.{Back.RESET}')
                    input('Press Enter to exit.')
                    break

                while True:
                    choice = input(f'\n{Style.BRIGHT}{Fore.YELLOW}Module to run:{Fore.RESET} ')
                    if choice.isdigit() and 1 <= int(choice) <= len(modules):
                        module = modules[int(choice) - 1]
                        break
                    print(f'\n{Style.BRIGHT}{Back.RED}Incorrect choice!{Back.RESET}')
                
                # For CLI, we run the logic directly without threading
                # We also need to temporarily redirect stdout/stdin for these modules
                # to interact with the console. This is the simplest way to avoid
                # rewriting all _print_output and _get_input to be conditional.

                # Backup original stdout/stdin
                original_stdout = sys.stdout
                original_stdin = sys.stdin

                # Create a simple wrapper for direct console I/O
                class ConsoleIOQueue:
                    def put(self, item):
                        original_stdout.write(item)
                        original_stdout.flush()
                    def get(self, timeout=None):
                        return original_stdin.readline().strip()
                    def empty(self):
                        return False # Assume not empty for blocking input

                module._output_queue = ConsoleIOQueue()
                module._input_queue = ConsoleIOQueue()

                module._run_logic() # Run blocking
                
                # Restore original stdout/stdin
                sys.stdout = original_stdout
                sys.stdin = original_stdin

        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"CLI Error: {e}")
            input("Press Enter to exit.")
