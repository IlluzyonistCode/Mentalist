import os
import random
from copy import deepcopy
from itertools import combinations
from functools import lru_cache
from colorama import Back, Fore, Style
from data_protection import save_encrypted, load_encrypted
from auth_protection import _integrity_checker
from utils import MENTALIST_DATA_DIR

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
