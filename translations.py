import re

_STRINGS = {
	'chat_werewolves_killed': {
		'en': 'The werewolves killed {0}.',
		'ru': 'Оборотни убили {0}.',
		'tr': "Kurt adamlar {0}'ı öldürdü."
	},
	'chat_werewolves_killed_toxic': {
		'en': '{0} has been poisoned by the toxic wolf during the day and killed by the werewolves this night.',
		'ru': '{0} был отравлен токсичным оборотнем в прошлый день и убит оборотнями этой ночью.',
		'tr': '{0}, gün içerisinde zehirli kurt tarafından zehirlenmişti ve bu gece kurt adamlar tarafından öldürüldü.'
	},
	'chat_werewolf_frenzy_kill': {
		'en': 'The werewolf frenzy killed {0}.',
		'ru': 'Неистовый оборотень убил {0}.',
		'tr': "Çılgın kurt adam {0}'ı öldürdü."
	},
	'chat_serial_killer_killed': {
		'en': 'The serial killer stabbed {0}.',
		'ru': 'Серийный убийца зарезал {0}.',
		'tr': "Seri katil {0}'ı bıçakladı."
	},
	'chat_cannibal_ate': {
		'en': 'The hungry cannibal ate {0}.',
		'ru': 'Голодный каннибал съел {0}.',
		'tr': "Aç yamyam {0}'ı yedi."
	},
	'chat_corruptor_killed': {
		'en': 'The corruptor killed {0}.',
		'ru': 'Хакер убил {0}.',
		'tr': "Hipnoterapist {0} 'ı öldürdü."
	},
	'chat_evil_detective_killed': {
		'en': 'The evil detective has killed {0}.',
		'ru': 'Злой детектив убил {0}.',
		'tr': "Kötü dedektif {0}'ı öldürdü."
	},
	'chat_instigator_killed': {
		'en': 'The instigator killed {0}.',
		'ru': 'Провокатор убил {0}.',
		'tr': "Elebaşı {0}'ı öldürdü."
	},
	'chat_ghost_lady_bound_killed': {
		'en': '{0} was killed because they were bound to another player they previously protected that now died.',
		'ru': '{0} был убит, потому что он был привязан к другому игроку, которого он спас ранее и который теперь умер.',
		'tr': '{0}, daha önce koruduğu ve şimdi ölen başka bir oyuncuya bağlı olduğu için öldü.'
	},
	'chat_evil_cupid_bound_killed': {
		'en': '{0} died because their bound partner was killed.',
		'ru': '{0} умер, потому что их связанный партнёр был убит.',
		'tr': '{0} bağlı partneri öldüğü için öldürüldü.'
	},
	'chat_evil_cupid_killed': {
		'en': '{0} was killed by the evil cupid.',
		'ru': '{0} был убит Злым Купидоном',
		'tr': '{0} kötü çöpçatan tarafından öldürüldü.'
	},
	'chat_jelly_werewolf_protected': {
		'en': 'The jelly wolf has saved {0}.',
		'ru': 'Желейный оборотень спас {0}.',
		'tr': "Jelibon kurt {0}'ı kurtardı."
	},
	'chat_player_not_killed': {
		'en': 'Player {0} could not be killed!',
		'ru': 'Игрок {0} не может быть убит!',
		'tr': 'Oyuncu {0} öldürülemez!'
	},
	'chat_the_village_killed': {
		'en': 'The village killed {0}.',
		'ru': 'Жители убили {0}.',
		'tr': "Köy {0}'ı idam etti."
	},
	'chat_judge_has_rightfully_convicted': {
		'en': 'The judge has rightfully convicted and executed {0}.',
		'ru': 'Судья справедливо осудил и казнил {0}.',
		'tr': "Yargıç haklı bir hüküm verdi ve {0}'ı idam etti."
	},
	'chat_judge_has_wrongfully_convicted': {
		'en': 'The judge {0} has wrongfully convicted {1}. They are a villager! The village rioted and killed {0}!',
		'ru': 'Судья {0} неправомерно осудил {1}. Он мирный житель! Деревня взбунтовалась и убила {0}!',
		'tr': "Yargıç {0} haksız yere {1}'e idam hükmü verdi. O bir köylü! Köylüler isyan ederek {0}'ı öldürdü!"
	},
	'chat_jailer_killed_target': {
		'en': 'The jailer executed their prisoner last night. {0} is dead.',
		'ru': 'Тюремщик казнил своего заключённого прошлой ночью. {0} умер.',
		'tr': 'Dün gece gardiyan tutsağını öldürdü. {0} öldü.'
	},
	'chat_gunner_shot': {
		'en': '{0} shot {1}.',
		'ru': '{0} застрелил {1}.',
		'tr': "{0}, {1}'ı vurdu."
	},
	'chat_marksman_shot': {
		'en': 'The marksman has shot {0}.',
		'ru': 'Меткий стрелок сделал выстрел в {0}.',
		'tr': "Nişancı {0} 'ı vurdu."
	},
	'chat_marksman_backfire': {
		'en': '{0} tried to shoot {1} but killed themself! {2} is a villager!',
		'ru': '{0} попытался выстрелить в {1}, но убил сам себя! {2} житель!',
		'tr': "{0}, {1}'ı vurmayı denedi ama kendini öldürdü. {2} bir köylü!"
	},
	'chat_warden_kill': {
		'en': 'The warden gave a weapon to an inmate who used it to kill {0}!',
		'ru': 'Надзиратель дал оружие своему подопечному, который застрелил {0}!',
		'tr': "Koğuş bekçisi, bir mahkuma {0}'ı öldürmek için kullandığı bir silah verdi!"
	},
	'chat_warden_backfire': {
		'en': '{0} tried to kill {1} with a weapon from the warden but the weapon backfired! {1} is a villager!',
		'ru': '{0} попытался убить {1} оружием надзирателя, но пуля отрикошетила обратно! {1} - житель!',
		'tr': "{0}, {1}'i koğuş liderinden aldığı silahla öldürmeye çalıştı ancak silah geri tepti! {1} bir köylü."
	},
	'chat_warden_werewolves_killed': {
		'en': '{0} jailed two werewolves. The werewolves broke out of their prison and killed the warden!',
		'ru': '{0} посадил в карцер двух оборотней. Они, не долго думая, сбежали из заточения и застрелили надзирателя!',
		'tr': '{0}, 2 tane kurt adamı hapse attı. Kurt adamlar hapishaneden kaçtılar ve koğuş bekçisini öldürdüler!'
	},
	'chat_vigilante_shot': {
		'en': '{0} shot {1}.',
		'ru': '{0} выстрелил в {1}.',
		'tr': "{0}, {1}'i vurdu."
	},
	'chat_vigilante_reveal': {
		'en': 'The vigilante has revealed {0}.',
		'ru': 'Линчеватель раскрыл роль {0}.',
		'tr': "Kanunsuz, {0}'ın rolünü açığa çıkardı."
	},
	'chat_priest_use_holy_water_killed': {
		'en': '{0} has thrown holy water at and killed {1}.',
		'ru': '{0} кинул святую воду и убил {1}.',
		'tr': "{0} zemzem suyunu kullandı ve {1}'ı öldürdü."
	},
	'chat_priest_use_holy_water_commit_suicide': {
		'en': '{0} has thrown holy water at {1} and killed themself. {2} is not a werewolf!',
		'ru': '{0} кинул святую воду в {1} и убил сам себя. {2} не оборотень!',
		'tr': '{0} zemzem suyunu {1} üzerinde kullandı ve kendisini öldürdü. {2} kurt adam değil!'
	},
	'chat_bully_killed': {
		'en': '{0} threw a rock at {1} who was already concussed, killing them.',
		'ru': '{0} бросил камень в {1} и убил его, так как он был уже без сознания.',
		'tr': "{0} zaten beyin sarsıntısı geçiren {1}'e taş attı ve onu öldürdü."
	},
	'chat_zombie_bitten_converted_zombie': {
		'en': '{0} is now a zombie.',
		'ru': '{0} теперь зомби.',
		'tr': '{0} artık bir zombi.'
	},
	'chat_player_surrendered': {
		'en': '{0} has fled from the village.',
		'ru': '{0} сбежал из деревни.',
		'tr': '{0} köyden kaçtı.'
	},
	'chat_message_winner_village': {
		'en': 'The village wins!',
		'ru': 'Жители победили!',
		'tr': 'Köy kazandı!'
	},
	'chat_message_winner_werewolves': {
		'en': 'The werewolves win!',
		'ru': 'Оборотни победили!',
		'tr': 'Kurt adamlar kazandı!'
	},
	'chat_message_winner_solo': {
		'en': '{0} wins. They are the {1}!',
		'ru': '{0} победил. Он {1}!',
		'tr': '{0} kazandı. O {1}!',
		'_word_slots': {1}
	},
	'chat_message_winner_sect': {
		'en': 'The sect wins!',
		'ru': 'Секта победила!',
		'tr': 'Tarikat kazandı!'
	},
	'chat_message_winner_zombie': {
		'en': 'The zombies win!',
		'ru': 'Зомби победили!',
		'tr': 'Zombiler kazandı!'
	},
	'chat_message_winner_lovers': {
		'en': 'The lovers win!',
		'ru': 'Любовники победили!',
		'tr': 'Aşıklar kazandı!'
	},
	'chat_message_winner_bandit': {
		'en': 'The bandit and their accomplice(s) win!',
		'ru': 'Бандит и его сообщник(и) победили!',
		'tr': 'Haydut ve suç ortakları kazandı!'
	},
	'chat_message_winner_tie': {
		'en': 'Game ended in a tie. There are no winners.',
		'ru': 'Игра закончилась ничьей. Здесь нет победителей.',
		'tr': 'Oyun berabere bitti. Kazanan yok.'
	},
	'role_shapeshifter_killed': {
		'en': 'The shapeshifter killed {0} and shapeshifted into their role!',
		'ru': 'Лицемер убил {0} и вжился в его роль!',
		'tr': "Taklitçi {0}'ı öldürdü ve onun kılığına girdi!"
	},
	'role_arsonist_player_ignited': {
		'en': 'The arsonist set {0} on fire!',
		'ru': 'Поджигатель поджёг {0}!',
		'tr': "Kundakçı {0}'ı yaktı!"
	},
	'role_bomber_player_exploded': {
		'en': '{0} was killed by an explosion!',
		'ru': '{0} был убит взрывом!',
		'tr': '{0} patlamada öldü!'
	},
	'role_astronomer_meteor_shower': {
		'en': 'The astronomer summoned a meteor shower on {0} and killed them.',
		'ru': 'Астроном вызвал метеоритный дождь на {0} и убил его.',
		'tr': 'Gök bilimci {0} oyuncusunun üzerine bir meteor yağmuru çağırdı ve onu öldürdü.'
	},
	'role_harlot_visit_die': {
		'en': '{0} visited an evil player and died.',
		'ru': '{0} посетил злого игрока и умер.',
		'tr': '{0} kötü bir oyuncuyu ziyaret etti ve öldü.'
	},
	'role_harlot_visit_target_die': {
		'en': '{0} visited a player who was attacked and got killed.',
		'ru': '{0} посетил игрока, который был атакован и убит.',
		'tr': '{0} saldırılmış bir oyuncuyu ziyaret etti ve öldü.'
	},
	'role_tough_guy_died': {
		'en': 'Player {0} was wounded last night and has died now.',
		'ru': 'Силач {0} был ранен прошлой ночью и теперь погиб.',
		'tr': 'Sert adam {0} dün gece yaralandı ve bugün öldü.'
	},
	'role_stubborn_werewolf_died': {
		'en': 'Player {0} was wounded and has died now.',
		'ru': 'Игрок {0} был ранен и сейчас погибнет.',
		'tr': 'Oyuncu {0} yaralandı ve şimdi öldü.'
	},
	'role_junior_werewolf_target_killed': {
		'en': "The junior werewolf's death has been avenged, {0} is dead!",
		'ru': 'Смерть малыша оборотня была отомщена, {0} погиб!',
		'tr': 'Yavru kurt adamın ölümünün intikamı alındı, {0} öldü!'
	},
	'role_split_wolf_killed': {
		'en': '{0} was killed because they bounded their soul to another player that died.',
		'ru': '{0} погиб из-за смерти игрока, к душе которого он был привязан.',
		'tr': '{0} ruhunu bağladığı oyuncu öldüğü için öldürüldü.'
	},
	'role_split_wolf_target_killed': {
		'en': '{0} was killed because their soul was bound to a split wolf that died.',
		'ru': '{0} погиб из-за смерти двойственного оборотня, который был привязан к его душе.',
		'tr': '{0} ruhunu bağladığı ayrık kurt öldüğü için öldürüldü.'
	},
	'split_wolf_revealed': {
		'en': '{0} had their role revealed because they bound their themselves to a player who has died.',
		'ru': 'Роль {0} была раскрыта из-за того, что он связал себя с умершим игроком.',
		'tr': "{0}'ın ruhunu bağladığı oyuncu öldüğü için rolü açığa çıktı."
	},
	'role_medium_revived_player': {
		'en': 'The medium revived {0}.',
		'ru': 'Медиум воскресил {0}.',
		'tr': 'Medyum {0} canlandırdı.'
	},
	'role_ritualist_revived_player': {
		'en': 'The ritualist revived {0}.',
		'ru': 'Некромант воскресил {0}.',
		'tr': "Ayinci {0}'ı canlandırdı."
	},
	'role_mayor_reveal_msg': {
		'en': 'Player {0} is the mayor!',
		'ru': 'Игрок {0} - мэр!',
		'tr': 'Oyuncu {0} belediye başkanlığını açığa çıkardı!'
	},
	'role_preacher_reveal_msg': {
		'en': 'Player {0} is the preacher! They will now get extra votes.',
		'ru': 'Игрок {0} - проповедник! Теперь он может воспользоваться дополнительными голосами.',
		'tr': 'Oyuncu {0} hatip! Şimdi fazladan oya sahip olacak.'
	},
	'fortune_teller_card_used_chat_message': {
		'en': "{0} used the fortune teller's card to reveal their role.",
		'ru': '{0} использовал карту гадалки, чтобы раскрыть свою роль.',
		'tr': '{0} falcının kartını rolünü açıklamak için kullandı.'
	},
	'hero_public_announcement_short': {
		'en': 'Player {1} has heroically taken the place of {0}!',
		'ru': 'Игрок {1} героически занял место {0}!',
		'tr': "Oyuncu {1} kahramanca bir şekilde {0}'ın yerini aldı!"
	},
	'weather_rain_washes_off_disguise_chat_message': {
		'en': 'The pouring rain revealed the role of {0}!',
		'ru': 'Проливной дождь раскрыл роль {0}!',
		'tr': "Şiddetli yağmur {0}'ın rolünü açığa çıkardı!"
	}
}

DISCUSSION_PREFIXES = (
	'Discussion',
	'Обсуждение',
	'Tartışma'
)

VOTING_PREFIXES = (
	'Voting',
	'Голосование',
	'Oylama'
)

UI = {
	'werewolf_chat': ('Werewolf chat',        'Чат оборотней',            'Kurt adam sohbeti'),
	'join':          ('Join',                 'Присоединиться',           'Katıl'),
	'cancel':        ('Cancel',               'Отмена',                   'Vazgeç'),
	'ok':            ('OK',                   'Окей',                     'Tamam'),
	'continue':      ('Continue',             'Продолжить',               'Devam et'),
	'play_again':    ('Play again',           'Играть снова',             'Tekrar oyna'),
	'refresh':       ('Refresh',              'Обновить',                 'Yenile'),
	'custom_games':  ('Custom games',         'Персонализированные игры', 'Özel oyunlar'),
	'quick_game':    ('Quick game',           'Быстрая игра',             'Hızlı oyun'),
	'create_game':   ('Create game',          'Создать игру',             'Oyun oluştur'),
	'start_game':    ('Start game',           'Начать игру',              'Oyunu başlat'),
	'play':          ('Play',                 'Играть',                   'Oyna')
}

_PLAYER_RE = r'\d{1,2} \S+(?:\s+\([^)]+\))?'
_WORD_RE = r'\S+'

_PATTERNS = None
_WINNER_KEYS = frozenset(k for k in _STRINGS if k.startswith('chat_message_winner_'))
_UI_LOOKUP = {v.upper(): key for key, variants in UI.items() for v in variants}


def _template_to_regex(template, word_slots=None):
	word_slots = word_slots or set()
	placeholders = re.findall(r'\{(\d+)\}', template)
	parts = re.split(r'\{\d+\}', template)

	seen_indices = set()
	pattern_parts = []

	for i, literal in enumerate(parts):
		escaped = re.escape(literal.strip())

		if escaped:
			pattern_parts.append(escaped)

		if i < len(placeholders):
			n = placeholders[i]
			n_int = int(n)

			if n not in seen_indices:
				rx = _WORD_RE if n_int in word_slots else _PLAYER_RE
				pattern_parts.append(f'(?P<p{n}>{rx})')
				seen_indices.add(n)

			else:
				rx = _WORD_RE if n_int in word_slots else _PLAYER_RE
				pattern_parts.append(f'(?:{rx})')

	full = r'\s*'.join(filter(None, pattern_parts))

	return re.compile(full, re.IGNORECASE | re.DOTALL)

def _build_patterns():
	seen = set()
	result = []

	for key, translations in _STRINGS.items():
		word_slots = translations.get('_word_slots', set())

		for lang, template in translations.items():
			if lang.startswith('_'):
				continue

			template = template.strip()

			if template in seen:
				continue

			seen.add(template)

			try:
				result.append((key, _template_to_regex(template, word_slots)))
			except re.error:
				pass

	return result

def match_event(message):
	msg = message.strip()

	for key, pattern in _PATTERNS:
		m = pattern.fullmatch(msg)

		if m is None:
			m = pattern.search(msg)

		if m:
			result = {'event': key}

			for name, value in m.groupdict().items():
				if value is not None:
					result[name] = value.strip()

			return result

def is_winner_event(event_key):
	return event_key in _WINNER_KEYS

def is_game_phase(text):
	return text.endswith('s') or text.startswith(VOTING_PREFIXES + DISCUSSION_PREFIXES)

def is_voting_phase(text):
	return text.startswith(VOTING_PREFIXES)

def is_discussion_phase(text):
	return text.startswith(DISCUSSION_PREFIXES)

def is_ui(text, key):
	return text.upper() in {v.upper() for v in UI[key]}

def match_ui(text):
	return _UI_LOOKUP.get(text.upper())

def ui_re(key):
	pattern = '|'.join(re.escape(v) for v in UI[key])

	return re.compile(pattern, re.IGNORECASE)

def parse_player_token(token):
	token = re.sub(r'\s*\([^)]*\)', '', token).strip()
	parts = token.split(' ', 1)

	return int(parts[0]) - 1, parts[1]

def extract_role_from_token(token):
	m = re.search(r'\(([^)]+)\)', token)

	if not m:
		return

	content = m.group(1)

	if '/' in content:
		return content.split('/')[-1].strip()

	return content.strip()


_PATTERNS = _build_patterns()
