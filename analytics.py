import re
import math
from copy import deepcopy
from collections import Counter
from colorama import Back, Fore, Style
from translations import parse_player_token


_STOP = {
	'a', 'an', 'the', 'is', 'it', 'in', 'on', 'at', 'to', 'of', 'and', 'or', 'but',
	'i', 'my', 'me', 'we', 'you', 'he', 'she', 'they', 'that', 'this', 'are', 'was',
	'were', 'be', 'been', 'not', 'no', 'yes', 'ok', 'okay', 'lol', 'haha', 'yeah',
	'yep', 'nope', 'just', 'so', 'do', 'did', 'have', 'has', 'had', 'will', 'can',
	'get', 'got', 'let', 'like', 'know', 'think', 'see', 'go', 'going', 'come'
}

def _tokenise(text):
	tokens = re.findall(r"[a-z']+", text.lower())

	return [t for t in tokens if len(t) > 2 and t not in _STOP]

def _cosine(a, b):
	if not a or not b:
		return 0.0

	dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in b)
	norm_a = math.sqrt(sum(v * v for v in a.values()))
	norm_b = math.sqrt(sum(v * v for v in b.values()))

	if norm_a == 0 or norm_b == 0:
		return 0.0

	return dot / (norm_a * norm_b)

def _tf(tokens):
	if not tokens:
		return {}

	counts = Counter(tokens)
	total = len(tokens)

	return {t: c / total for t, c in counts.items()}


class _PlayerStats:
	def __init__(self, name):
		self.name = name
		self.messages = []
		self.global_tokens = Counter()
		self.lengths = []
		self.slot_mentions = Counter()
		self.vote_count = 0

	def ingest(self, message):
		self.messages.append(message)
		tokens = _tokenise(message)
		self.global_tokens.update(tokens)
		self.lengths.append(len(message))

		for m in re.finditer(r'\b(\d{1,2})\b', message):
			n = int(m.group(1))

			if 1 <= n <= 16:
				self.slot_mentions[n] += 1

		vote_kw = {'vote', 'lynch', 'skip', 'elect', 'nominate'}

		self.vote_count += sum(1 for t in tokens if t in vote_kw)

	def count(self):
		return len(self.lengths)


class NLPAnalyzer:
	def __init__(self):
		self._stats = {}
		self._doc_count = 0
		self._doc_freq = Counter()
		self._idf = {}

	def reset(self):
		self.__init__()

	def ingest(self, player_messages):
		for raw in player_messages:
			parts = raw.split(': ', 1)

			if len(parts) != 2:
				continue

			prefix, message = parts
			p_parts = prefix.strip().split(' ', 1)

			if len(p_parts) != 2:
				continue

			name = p_parts[1].strip()

			if not name:
				continue

			if name not in self._stats:
				self._stats[name] = _PlayerStats(name)

			self._stats[name].ingest(message)

			tokens_set = set(_tokenise(message))

			self._doc_count += 1

			for t in tokens_set:
				self._doc_freq[t] += 1

		self.rebuild_idf()

	def rebuild_idf(self):
		n = max(self._doc_count, 1)

		self._idf = {
			t: math.log((n + 1) / (df + 1)) + 1.0
			for t, df in self._doc_freq.items()
		}

	def get_anomalies(self):
		if len(self._stats) < 2:
			return {}

		all_lengths = []

		for ps in self._stats.values():
			all_lengths.extend(ps.lengths)

		if not all_lengths:
			return {}

		game_mean = sum(all_lengths) / len(all_lengths)
		game_std = math.sqrt(
			sum((l - game_mean) ** 2 for l in all_lengths) / len(all_lengths)
		) if len(all_lengths) > 1 else 1.0
		game_std = max(game_std, 1.0)

		total_vote_tokens = sum(ps.vote_count for ps in self._stats.values())
		total_msgs = sum(ps.count() for ps in self._stats.values())
		avg_vote_density = total_vote_tokens / total_msgs if total_msgs else 0.0

		result = {}

		for name, ps in self._stats.items():
			if ps.count() < 2:
				result[name] = {
					'anomaly_score': 0,
					'length_z': 0.0,
					'style_drift': 0.0,
					'vote_density': 0.0,
					'message_count': ps.count(),
					'flags': ['insufficient_data']
				}
				continue

			player_mean = sum(ps.lengths) / len(ps.lengths)
			length_z = (player_mean - game_mean) / game_std

			if ps.count() >= 6:
				mid = ps.count() // 2
				msgs = ps.messages
				early_tokens = []
				late_tokens = []

				for m in msgs[:mid]:
					early_tokens.extend(_tokenise(m))

				for m in msgs[mid:]:
					late_tokens.extend(_tokenise(m))

				vec_early = {t: v * self._idf.get(t, 1.0) for t, v in _tf(early_tokens).items()}
				vec_late = {t: v * self._idf.get(t, 1.0) for t, v in _tf(late_tokens).items()}
				style_drift = 1.0 - _cosine(vec_early, vec_late)

			else:
				style_drift = 0.0

			player_vote_density = ps.vote_count / ps.count() if ps.count() > 0 else 0.0

			if avg_vote_density >= 0.02:
				vote_ratio = player_vote_density / avg_vote_density
				vote_component = min((vote_ratio - 1.0) / 3.0, 1.0) if vote_ratio > 1.0 else 0.0

			else:
				vote_ratio = 1.0
				vote_component = 0.0

			len_component = min(abs(length_z) / 3.0, 1.0)
			drift_component = min(style_drift, 1.0)

			raw_score = (0.30 * len_component + 0.40 * drift_component + 0.30 * vote_component) * 100
			anomaly_score = int(min(100, max(0, raw_score)))

			flags = []

			if abs(length_z) > 2.0:
				flags.append(f'length outlier z={length_z:.1f}')

			if style_drift > 0.5:
				flags.append(f'style shift {style_drift:.2f}')

			if vote_ratio > 3.0:
				flags.append(f'vote density x{vote_ratio:.1f}')

			result[name] = {
				'anomaly_score': anomaly_score,
				'length_z': round(length_z, 3),
				'style_drift': round(style_drift, 3),
				'vote_density': round(player_vote_density, 3),
				'message_count': ps.count(),
				'flags': flags
			}

		return result

	def get_mention_graph(self):
		return {
			name: {str(k): v for k, v in ps.slot_mentions.items()}
			for name, ps in self._stats.items()
			if ps.slot_mentions
		}

	def get_state(self):
		return {
			'anomalies': self.get_anomalies(),
			'mention_graph': self.get_mention_graph()
		}

	def render_cli(self):
		anomalies = self.get_anomalies()

		if not anomalies:
			return ''

		rows = []

		for name, anom in sorted(anomalies.items(), key=lambda x: x[1]['anomaly_score'], reverse=True):
			if anom['flags'] == ['insufficient_data']:
				continue

			score = anom['anomaly_score']

			if score >= 60:
				score_color = Fore.RED

			elif score >= 30:
				score_color = Fore.YELLOW

			else:
				score_color = Fore.GREEN

			flags_str = '  '.join(anom['flags']) if anom['flags'] else 'normal'

			rows.append(
				f'{Style.BRIGHT}{name[:12]:<12}{Style.RESET_ALL} '
				f'{score_color}[{score:3}]{Fore.RESET} '
				f'{Fore.CYAN}{flags_str}{Fore.RESET}'
			)

		if not rows:
			return ''

		half = (len(rows) + 1) // 2
		col_width = 42

		lines = [f'\n{Style.BRIGHT}{Back.BLUE} NLP {Back.RESET}{Fore.CYAN} Style Anomalies{Fore.RESET}']

		for i in range(half):
			left = rows[i]
			right = rows[i + half] if i + half < len(rows) else ''
			left_plain = re.sub(r'\x1b\[[0-9;]*m', '', left)
			pad = max(0, col_width - len(left_plain))

			lines.append(f'{left}{" " * pad}{right}')

		return '\n'.join(lines)


LIKELIHOODS = {
	'chat_werewolves_killed': {'target': 'p0', 'team_weights': {'WEREWOLF': 0.05, 'VILLAGER': 1.2, 'SOLO': 1.1}},
	'chat_werewolves_killed_toxic': {'target': 'p0', 'team_weights': {'WEREWOLF': 0.05, 'VILLAGER': 1.2, 'SOLO': 1.1}},
	'chat_werewolf_frenzy_kill': {'target': 'p0', 'team_weights': {'WEREWOLF': 0.05, 'VILLAGER': 1.2, 'SOLO': 1.1}},
	'role_junior_werewolf_target_killed': {'target': 'p0', 'team_weights': {'WEREWOLF': 0.05, 'VILLAGER': 1.2, 'SOLO': 1.1}},
	'chat_the_village_killed': {'target': 'p0', 'team_weights': {'WEREWOLF': 1.6, 'VILLAGER': 0.7, 'SOLO': 1.2}},
	'chat_judge_has_rightfully_convicted': {'target': 'p0', 'team_weights': {'WEREWOLF': 1.8, 'VILLAGER': 0.5, 'SOLO': 1.3}},
	'chat_serial_killer_killed': {'target': 'p0', 'team_weights': {'SOLO': 0.05, 'VILLAGER': 1.1, 'WEREWOLF': 1.0}},
	'chat_cannibal_ate': {'target': 'p0', 'team_weights': {'SOLO': 0.05, 'VILLAGER': 1.1, 'WEREWOLF': 0.9}},
	'role_mayor_reveal_msg': {'target': 'p0', 'role_weights': {'mayor': 10.0}},
	'role_preacher_reveal_msg': {'target': 'p0', 'role_weights': {'preacher': 10.0}},
	'fortune_teller_card_used_chat_message': {'target': 'p0', 'role_weights': {'fortune-teller': 8.0}},
	'chat_vigilante_reveal': {'target': 'p0', 'role_weights': {'vigilante': 9.0}},
	'chat_gunner_shot': {'target': 'p0', 'role_weights': {'gunner': 8.0}},
	'chat_vigilante_shot': {'target': 'p0', 'role_weights': {'vigilante': 8.0}},
	'chat_jailer_killed_target': {'target': 'p0', 'role_weights': {'jailer': 7.0}},
	'chat_warden_kill': {'target': 'p0', 'role_weights': {'warden': 7.0}},
	'chat_marksman_shot': {'target': 'p0', 'role_weights': {'marksman': 8.0}},
	'chat_jelly_werewolf_protected': {'target': 'p0', 'role_weights': {'jelly-wolf': 9.0}},
	'chat_zombie_bitten_converted_zombie': {'target': 'p0', 'role_weights': {'zombie': 10.0}},
	'chat_player_not_killed': {'target': 'p0', 'team_weights': {'VILLAGER': 1.3, 'WEREWOLF': 0.6}}
}

VOTE_AGAINST_MULTIPLIER = 1.08
VOTE_FOR_MULTIPLIER = 0.96


class BayesEngine:
	def __init__(self, tracker):
		self.tracker = tracker
		self._priors = {}
		self._initialised = False
		self._dead_players = set()
		self._vote_counts = {}

	def reset(self):
		self._priors = {}
		self._initialised = False
		self._dead_players = set()
		self._vote_counts = {}

	def ensure_initialised(self):
		if self._initialised:
			return

		rotation = getattr(self.tracker, 'ROTATION', None)
		players = getattr(self.tracker, 'PLAYERS', None) or []

		if not rotation or not any(p.get('name') for p in players):
			return

		rotation_weights = self.build_rotation_weights(rotation)

		if not rotation_weights:
			return

		total_weight = sum(rotation_weights.values())
		normalised_weights = {rid: w / total_weight for rid, w in rotation_weights.items()}

		for player in players:
			name = player.get('name')

			if not name:
				continue

			self._priors[name] = deepcopy(normalised_weights)

		self._initialised = True

		self.sync_known_roles()

	def build_rotation_weights(self, rotation):
		weights = {}
		random_types = getattr(self.tracker, 'RANDOM_ROLE_TYPES', {})

		for slot in rotation:
			role_id = slot.get('id') if isinstance(slot, dict) else slot

			if not role_id:
				continue

			if 'random' in role_id:
				candidates = random_types.get(role_id, [])

				if isinstance(candidates, list) and candidates:
					share = 1.0 / len(candidates)

					for rid in candidates:
						weights[rid] = weights.get(rid, 0.0) + share

			else:
				weights[role_id] = weights.get(role_id, 0.0) + 1.0

		return weights

	def sync_known_roles(self):
		players = getattr(self.tracker, 'PLAYERS', None) or []
		rotation = getattr(self.tracker, 'ROTATION', None)

		if not rotation:
			return

		for player in players:
			name = player.get('name')
			role_id = player.get('role')

			if not name or not role_id or name not in self._priors:
				continue

			if role_id in self._priors[name]:
				self.on_known_role(name, role_id, confidence=1.0)

		full_weights = self.build_rotation_weights(rotation)
		assigned_counts = {}

		for player in players:
			role_id = player.get('role')

			if role_id:
				assigned_counts[role_id] = assigned_counts.get(role_id, 0) + 1

		remaining_weights = {}

		for role_id, total in full_weights.items():
			remaining = total - assigned_counts.get(role_id, 0)

			if remaining > 0:
				remaining_weights[role_id] = remaining

		if not remaining_weights:
			return

		remaining_total = sum(remaining_weights.values())
		remainingnormalised = {rid: w / remaining_total for rid, w in remaining_weights.items()}

		for player in players:
			name = player.get('name')
			role_id = player.get('role')
			dead = player.get('dead', False)

			if not name or role_id or dead:
				continue

			if name not in self._priors:
				continue

			dist = self._priors[name]
			new_dist = {}

			for rid in remainingnormalised:
				existing = dist.get(rid, 0.0)
				new_dist[rid] = existing if existing > 1e-8 else remainingnormalised[rid]

			self._priors[name] = new_dist
			self.normalise(name)

	def on_event(self, event):
		self.ensure_initialised()

		if not self._priors:
			return

		key = event.get('event', '')
		spec = LIKELIHOODS.get(key)

		if spec is None:
			return

		token_key = spec.get('target')

		if token_key is None:
			return

		token = event.get(token_key)

		if token is None:
			return

		_, name = parse_player_token(token)

		if not name or name not in self._priors:
			return

		self.apply_multipliers(
			name,
			role_weights=spec.get('role_weights', {}),
			team_weights=spec.get('team_weights', {})
		)

	def on_vote(self, voter_name, target_name, vote_type='against'):
		self.ensure_initialised()

		if target_name not in self._priors:
			return

		if target_name in self._dead_players:
			return

		count = self._vote_counts.get(target_name, 0) + 1
		self._vote_counts[target_name] = count

		decay = 1.0 / math.log1p(count)
		base = VOTE_AGAINST_MULTIPLIER if vote_type == 'against' else VOTE_FOR_MULTIPLIER
		multiplier = 1.0 + (base - 1.0) * decay

		dist = self._priors[target_name]
		roles = getattr(self.tracker, 'ROLES', {})

		for role_id in dist:
			role_data = roles.get(role_id, {}) if isinstance(roles, dict) else {}
			team = role_data.get('team', '')

			if vote_type == 'against':
				if team == 'WEREWOLF':
					dist[role_id] *= multiplier * 1.05

				elif team == 'SOLO':
					dist[role_id] *= multiplier

				else:
					dist[role_id] *= multiplier * 0.97

			else:
				dist[role_id] *= multiplier

		self.normalise(target_name)

	def on_known_role(self, player_name, role_id, confidence=1.0):
		self.ensure_initialised()

		if player_name not in self._priors:
			return

		dist = self._priors[player_name]

		for rid in dist:
			dist[rid] = 1.0 if rid == role_id else (1.0 - confidence)

		self.normalise(player_name)

	def on_player_died(self, player_name):
		self.ensure_initialised()

		if not player_name:
			return

		self._dead_players.add(player_name)

	def get_probabilities(self):
		self.ensure_initialised()

		result = {}

		for name, dist in self._priors.items():
			total = sum(dist.values())

			if total <= 0:
				continue

			normalised = {rid: w / total for rid, w in dist.items() if w / total > 0.005}
			result[name] = dict(sorted(normalised.items(), key=lambda x: x[1], reverse=True))

		return result

	def get_top_suspect_roles(self, player_name, n=3):
		probs = self.get_probabilities().get(player_name, {})

		return sorted(probs.items(), key=lambda x: x[1], reverse=True)[:n]

	def get_team_probabilities(self, player_name):
		probs = self.get_probabilities().get(player_name, {})
		teams = {'VILLAGER': 0.0, 'WEREWOLF': 0.0, 'SOLO': 0.0}
		roles = getattr(self.tracker, 'ROLES', {})

		for role_id, prob in probs.items():
			role_data = roles.get(role_id, {}) if isinstance(roles, dict) else {}
			team = role_data.get('team', 'VILLAGER')

			if team in teams:
				teams[team] += prob

		total = sum(teams.values())

		if total > 0:
			teams = {k: v / total for k, v in teams.items()}

		return teams

	def get_state(self):
		probs = self.get_probabilities()
		players = getattr(self.tracker, 'PLAYERS', None) or []
		roles = getattr(self.tracker, 'ROLES', {})
		output = []

		for player in players:
			name = player.get('name')

			if not name or player.get('dead', False):
				continue

			role_probs = probs.get(name, {})
			team_probs = self.get_team_probabilities(name)

			top_roles = [
				{
					'role_id': rid,
					'role_name': roles.get(rid, {}).get('name', rid) if isinstance(roles, dict) else rid,
					'prob': round(p, 4),
				}
				for rid, p in list(role_probs.items())[:5]
			]

			output.append({
				'name': name,
				'slot': players.index(player) + 1,
				'dead': False,
				'known_role': player.get('role'),
				'top_roles': top_roles,
				'team_probs': {k: round(v, 4) for k, v in team_probs.items()}
			})

		return {'players': output}

	def render_cli(self):
		probs = self.get_probabilities()

		if not probs:
			return ''

		players = getattr(self.tracker, 'PLAYERS', None) or []
		roles = getattr(self.tracker, 'ROLES', {})
		rows = []

		for i, player in enumerate(players):
			name = player.get('name')

			if not name or player.get('dead'):
				continue

			known = player.get('role')

			if known:
				role_name = roles.get(known, {}).get('name', known) if isinstance(roles, dict) else known
				team = player.get('team', '')

				if team == 'WEREWOLF':
					color = Fore.RED

				elif team == 'SOLO':
					color = Fore.MAGENTA

				else:
					color = Fore.GREEN

				right = f'{color}{role_name}{Fore.RESET}'

			else:
				team_p = self.get_team_probabilities(name)
				top = self.get_top_suspect_roles(name, n=2)
				ww = int(team_p.get('WEREWOLF', 0) * 100)
				vv = int(team_p.get('VILLAGER', 0) * 100)
				ss = int(team_p.get('SOLO', 0) * 100)

				if ww >= 50:
					color = Fore.RED

				elif ss >= 30:
					color = Fore.MAGENTA

				else:
					color = Fore.GREEN

				top_str = ' '.join(
					f'{(roles.get(rid, {}).get("name", rid) if isinstance(roles, dict) else rid)[:8]} {int(p * 100)}%'
					for rid, p in top
				)
				right = f'{color}W{ww:2}%V{vv:2}%S{ss:2}%{Fore.RESET} {Fore.CYAN}{top_str}{Fore.RESET}'

			rows.append(
				f'{Style.BRIGHT}{Fore.YELLOW}{i + 1:2}.{Fore.RESET}'
				f'{name[:12]:<12} {right}'
			)

		if not rows:
			return ''

		half = (len(rows) + 1) // 2
		col_width = 46

		lines = [f'\n{Style.BRIGHT}{Back.CYAN} BAYES {Back.RESET}{Fore.CYAN} Role Probabilities{Fore.RESET}']

		for i in range(half):
			left = rows[i]
			right = rows[i + half] if i < len(rows[half:]) else ''
			left_plain = re.sub(r'\x1b\[[0-9;]*m', '', left)
			pad = max(0, col_width - len(left_plain))

			lines.append(f'{left}{" " * pad}{right}')

		return '\n'.join(lines)

	def apply_multipliers(self, player_name, role_weights, team_weights):
		if player_name in self._dead_players:
			return

		dist = self._priors.get(player_name)

		if dist is None:
			return

		roles = getattr(self.tracker, 'ROLES', {})

		for role_id in list(dist.keys()):
			role_data = roles.get(role_id, {}) if isinstance(roles, dict) else {}
			team = role_data.get('team', 'VILLAGER')
			multiplier = 1.0

			if role_id in role_weights:
				multiplier *= role_weights[role_id]

			if team in team_weights:
				multiplier *= team_weights[team]

			dist[role_id] = max(dist[role_id] * multiplier, 1e-9)

		self.normalise(player_name)

	def normalise(self, player_name):
		dist = self._priors.get(player_name)

		if not dist:
			return

		total = sum(dist.values())

		if total > 0:
			for rid in dist:
				dist[rid] /= total
