import io
import os
import yaml
import json
import pathlib
import argparse
import itertools
import traceback
from parse_morphosynt import *


def error1(msg):
	print('ERROR: {}'.format(msg))
	exit(1)


class TokenMatching:
	def __init__(self):
		self.token_index = None
		self.token = None
		self.constituent = None
		self.slot_name = None
		self.rule_elem = None

	def __repr__(self):
		return self.token['token']


class SlotValue:
	def __init__(self):
		self.text = None
		self.key_index = None
		self.key_word = None
		self.key_lemma = None

	def __repr__(self):
		return self.text


class ExtractedFact:
	def __init__(self):
		self.fact_name = None
		self.matched_rule = None
		self.fact_text = None
		self.slot2value = None

	def __repr__(self):
		s = self.fact_name if self.fact_name else ''
		if self.matched_rule:
			s += ', ' + self.matched_rule.get_name()
		s += ' -> '
		if self.fact_text:
			s += self.fact_text

		return s

	def get_fact_name(self):
		return self.fact_name

	def get_subfact_name(self):
		return self.matched_rule.get_name()

	def get_text(self):
		return self.fact_text

	def get_slots(self):
		return list(self.slot2value.items())


class SubfactItem:
	"""Загруженная секция в разделе Items подфакта"""
	def __init__(self):
		self.participant = None
		self.slot_name = None
		self.Lex = None
		self.LexNonHead = None
		self.ConstituentType = None
		self.Morph = None
		self.Orth = None
		self.optional = False
		self.value = 'token'
		self.Show = None

	def __repr__(self):
		s = '{}: {}'.format(self.participant, self.slot_name)
		return s

	def load_yaml(self, yaml_data, dirname):
		self.participant = list(yaml_data.keys())[0]  # !!! завязались на порядок, нехорошо
		self.slot_name = yaml_data[self.participant]
		if self.slot_name is None:
			raise RuntimeError('Для участника "{}" не задано имя слота'.format(self.participant))

		if 'Lex' in yaml_data:
			self.Lex = [lex.strip() for lex in yaml_data['Lex'].split('|')]
		elif 'List' in yaml_data:
			fname = os.path.join(dirname, yaml_data['List'] + '.txt')
			with io.open(fname, 'r', encoding='utf-8') as rdr:
				self.Lex = [line.strip() for line in rdr]

		if 'LexNonHead' in yaml_data:
			self.LexNonHead = [lex.strip() for lex in yaml_data['LexNonHead'].split('|')]
		elif 'ListNonHead' in yaml_data:
			fname = os.path.join(dirname, yaml_data['ListNonHead'] + '.txt')
			with io.open(fname, 'r', encoding='utf-8') as rdr:
				self.LexNonHead = [line.strip() for line in rdr]

		if 'ConstituentType' in yaml_data:
			self.ConstituentType = [s.strip() for s in yaml_data['ConstituentType'].split('|')]

		if 'Morph' in yaml_data:
			self.Morph = [s.strip() for s in yaml_data['Morph'].split(',')]

		if 'Orth' in yaml_data:
			self.Orth = yaml_data['Orth']
			if self.Orth not in ['FirstCapital', 'AllSmall', 'AllCapital', 'CamelCase']:
				error1('Неверный предикат Ortho: {}'.format(self.Orth))

		if 'Value' in yaml_data:
			self.value = yaml_data['Value']

		if 'Show' in yaml_data:
			self.Show = yaml_data['Show']


class OrderConstraints:
	def __init__(self):
		self.var1 = None
		self.var2 = None

	def load_yaml(self, data_yaml):
		vars = [v.strip() for v in data_yaml.strip().split(',')]
		self.var1 = vars[0]
		self.var2 = vars[1]

	def __repr__(self):
		return '{}, {}'.format(self.var1, self.var2)


class SubFactRule:
	def __init__(self, priority):
		self.name = None
		self.priority = priority
		self.obligatory_participants = None
		self.optional_participants = None
		self.items = None
		self.links = None
		self.var2slot = None
		self.order_constraints = []

	def __repr__(self):
		return self.name

	def load_yaml(self, yaml_data, dirname):
		self.name = yaml_data['Name']

		self.optional_participants = []

		participants = yaml_data['Participants']
		for ppp in participants:
			for participant_type, participant_list in ppp.items():
				if participant_type == 'Obligatory':
					self.obligatory_participants = [s.strip() for s in participant_list.split(',')]
				elif participant_type == 'Optional':
					self.optional_participants = [s.strip() for s in participant_list.split(',')]
				else:
					error1('Неизвестный тип участника: {}'.format(participant_type))

		self.links = yaml_data.get('Links')  # считали связи из правила
		self.items = []
		for item_data in yaml_data['Items']:
			item = SubfactItem()
			item.load_yaml(item_data, dirname)
			if item.slot_name in self.optional_participants:
				item.optional = True
			self.items.append(item)

		if 'Constraints' in yaml_data:
			for constraint_yaml in yaml_data['Constraints']:
				if 'Order' in constraint_yaml:
					d = constraint_yaml['Order']
					ord = OrderConstraints()
					ord.load_yaml(d)
					self.order_constraints.append(ord)
				else:
					raise NotImplementedError()

		self.var2slot = dict((item.participant, item) for item in self.items)

	def get_name(self):
		return self.name

	def match(self, parser_data):
		matched_pairs = dict()

		#index2token = dict((t['itoken'], t) for t in parser_data['tokens'])
		for arg in itertools.chain(self.obligatory_participants, self.optional_participants):
			for elem in self.items:
				# не анализируем опциональных участников!
				if elem.slot_name in arg or elem.slot_name in ('Dummy', 'Dummy1', 'Dummy2', 'Dummy3', 'Dummy4', 'Dummy5', 'Key'):
					if elem.participant not in matched_pairs:
						#if elem.Lex or elem.LexNonHead or elem.ConstituentType or elem.Orth or elem.Morph:
						compareTags(elem, parser_data, elem.participant, elem.slot_name, matched_pairs)

		# 05.08.2020 если не извлечен какой-то из обязательных участников, то
		# считаем, что правило вообще не сработало.
		all_oblig_matched = True
		for elem in self.items:
			if not elem.optional and elem.participant not in matched_pairs:
				all_oblig_matched = False
				break

			#if elem.slot_name in self.obligatory_participants or elem.slot_name in ('Dummy', 'Key'):

		extracted_facts = []

		if all_oblig_matched and len(matched_pairs) > 0:
			# Теперь для каждой переменной известны сопоставленные токены.
			# Перебираем все сочетания сопоставлений токенов и переменных.
			# Каждое сочетание проверяем по ограничениям Links
			matched_tokens = [matched_pairs[var] for var in matched_pairs.keys()]
			for matched_tokens1 in itertools.product(*matched_tokens):
				matched_pairs1 = dict(zip(matched_pairs.keys(), matched_tokens1))

				# Теперь в matched_pairs1 для каждой переменной есть единственный сопоставленный токен.

				constraints_ok = True

				if self.order_constraints:
					for ord in self.order_constraints:
						first_var = ord.var1
						second_var = ord.var2

						if first_var not in matched_pairs1:
							if self.var2slot[first_var].optional:
								continue

							constraints_ok = False
							continue

						if second_var not in matched_pairs1:
							if self.var2slot[second_var].optional:
								continue

							constraints_ok = False
							continue

						first_itoken = matched_pairs1[first_var].token_index
						sec_itoken = matched_pairs1[second_var].token_index
						if first_itoken >= sec_itoken:
							constraints_ok = False

				# Проверяем ограничения - связи.
				if self.links and constraints_ok:
					for link_constraint in self.links:
						assert(len(link_constraint) == 1)
						key = list(link_constraint.keys())[0]
						cur_link = list(link_constraint.values())[0]

						letters = [l.strip() for l in key.split(',')]   # элементы из правила
						first_var = letters[0]
						second_var = letters[1]

						if first_var not in matched_pairs1:
							if self.var2slot[first_var].optional:
								continue

							constraints_ok = False
							continue

						if second_var not in matched_pairs1:
							if self.var2slot[second_var].optional:
								continue

							constraints_ok = False
							continue

						first_itoken = matched_pairs1[letters[0]].token_index
						sec_itoken = matched_pairs1[letters[1]].token_index

						#print(sec_itoken, 'sec_itoken')  # второй элемент из пары связей из правила
						#print(first_itoken, 'first_itoken')  # первый элемент из пары связей из правила

						link_matched = False

						for token in parser_data['tokens']:
							if token['itoken'] == sec_itoken:  # находим второй элемент в json
								if ('edge_type' in token) and (token['edge_type'] == cur_link) and (token['parent_token_index'] == first_itoken):
									#print('тип связи совпал')  # если задан конкретный тип связи, пытаемся его найти
									link_matched = True
									break
								elif cur_link == 'one':  # если конкретный тип связи не задан
									if 'parent_token_index' in token and token['parent_token_index'] == first_itoken:
										#print('тип связи one или any совпал', token['parent_token_index'])
										link_matched = True
										break
								elif cur_link == 'any':
									# только для типа связи any. вызываем функцию, которая будет пытаться установить
									f = ifLinkExists(data[0]['tokens'], token['parent_token_index'], first_itoken)
									#print(f)
									if f:
										link_matched = True
										break
								#else:
									# ???
									#if first_itoken == token:  # дошли до root и связь не нашли, значит связи нет
									#	print('обязательная связь не найдена!')
									#	break
									#pass

						if not link_matched:
							constraints_ok = False
							break

				# ограничения проверены, осталось сформировать описание факта
				if constraints_ok:
					constituents = parser_data['constituents']
					matched_tokens = matched_pairs1.values()
					matched_tokens = sorted(matched_tokens, key=lambda z: z.token_index)
					fact_tokens = dict()
					for matched_token in matched_tokens:
						fact_tokens[matched_token.token_index] = matched_token.token['token']

						if True:
							# Для токена попробуем найти NP-составляющую минимального размера. Выведем
							# все токены этой составляющей в текст факта.
							if matched_token.constituent and matched_token.constituent['is_head'] is True:
								for c in constituents:
									if c['id'] == matched_token.constituent['id']:
										if c['name'] == 'NP' or (matched_token.rule_elem is not None and matched_token.rule_elem.Show == 'Constituent'):
											#if c['head_id'] == matched_token.token_index and c['name'] == 'NP':
											#    cx.append(c['tokens'])
											for t in c['tokens']:
												token_index = t[0]
												word = t[1]  #index2token[token_index]['token']
												fact_tokens[token_index] = word


					fact_tokens = sorted(fact_tokens.items(), key=lambda z: z[0])
					fact_tokens = [t[1] for t in fact_tokens]

					extracted_fact = ExtractedFact()
					extracted_fact.fact_name = fact.get_name()
					extracted_fact.matched_rule = subfact
					extracted_fact.fact_text = ' '.join(fact_tokens)

					extracted_fact.slot2value = dict()
					for matched_token in matched_tokens:
						if not matched_token.slot_name.startswith('Dummy'):
							slot_tokens = dict()
							slot_tokens[matched_token.token_index] = matched_token.token['token']

							slot_value = SlotValue()
							slot_value.key_word = matched_token.token['token']
							slot_value.key_lemma = matched_token.token['lemma']
							slot_value.key_index = matched_token.token['itoken']

							slot_filling = 'token'
							if matched_token.constituent:
								if matched_token.constituent['is_head'] is True and matched_token.constituent['name'] == 'NP':
									slot_filling = 'constituent'
								elif matched_token.constituent['is_head'] is True and matched_token.rule_elem is not None and matched_token.rule_elem.Show == 'Constituent':
									slot_filling = 'constituent'
								else:
									#slot_name = matched_token.slot_name
									for item in self.items:
										if item.slot_name == matched_token.slot_name:
											slot_filling = item.value
											break

							# если слот сопоставлен с NP и токен - главный, то значением слота будет вся NP.
							if slot_filling == 'constituent':
								for c in constituents:
									if c['id'] == matched_token.constituent['id']:
										# if c['head_id'] == matched_token.token_index and c['name'] == 'NP':
										#    cx.append(c['tokens'])
										for t in c['tokens']:
											token_index = t[0]
											word = t[1]  # index2token[token_index]['token']
											slot_tokens[token_index] = word
										break

							slot_tokens = sorted(slot_tokens.items(), key=lambda z: z[0])
							slot_tokens = [t[1] for t in slot_tokens]
							slot_value.text = ' '.join(slot_tokens)

							extracted_fact.slot2value[matched_token.slot_name] = slot_value

					extracted_facts.append(extracted_fact)

		return extracted_facts


class Fact:
	def __init__(self, name):
		self.name = name
		self.subfacts = []

	def __repr__(self):
		return self.name

	def get_name(self):
		return self.name

	def load_yaml(self, filepath):
		"""Загружаем новую порцию правил для подфактов, добавляя их в общий список факта."""
		with io.open(filepath, 'r', encoding='utf-8') as f:
			try:
				data = yaml.safe_load(f)
				dirname = os.path.dirname(filepath)

				if 'Priority' in data:
					priority = data['Priority']
				else:
					priority = 1

				for irule, d in enumerate(data['SubFacts']):
					subfact = SubFactRule((priority, irule))
					subfact.load_yaml(d['SubFact'], dirname)
					self.subfacts.append(subfact)
			except Exception as ex:
				error1('При загрузке правил из файла "{}" произошла ошибка: {}'.format(filepath, ex))

	def enum_subfacts(self):
		# Считаем, что первое правило по умолчанию более приоритетно, чем последующие.
		return sorted(self.subfacts, key=lambda z: z.priority[0] - z.priority[1]*1e-10, reverse=True)


#функция проверяет есть ли синтаксическая связь между элементами
def ifLinkExists(tokens, sec_itoken, first_itoken):
	if sec_itoken == first_itoken:   # <-- доработка от 27.07.2020
		return True

	for token in tokens:
		if token['itoken'] == sec_itoken: 
			#print(sec_itoken, 'второй элемен из связи')
			#print(first_itoken, 'первый элемен из связи')
			if token['parent_token_index'] == first_itoken: # нашли связь
				return True
			elif token['parent_token_index'] == -1: #дошли до root, т е не нашли связи
				return False
			else:
				return ifLinkExists(data[0]['tokens'], token['parent_token_index'], first_itoken)


def compareMorphTags(rule_elem, data_elem):
	""" функция возвращает true, если все морфологические теги совпали """
	if rule_elem.Morph:
		tagset = data_elem['tagsets'][0]  # теги ищем в первом тегсете разметки

		for tag in rule_elem.Morph:
			if '|' in tag: #дробим альтернативные теги
				tag_matched = False
				for tag1 in tag.split('|'):
					tag1 = tag1.strip()
					if tag1 in tagset:
						tag_matched = True
						break

				if not tag_matched:
					#print('морф тег из правила не найден', tag)
					return False

			elif 'NOT' in tag:
				tag = tag.split(':')[1].strip()
				if tag not in tagset: #если тег с пометкой NOT не найден, продолжаем проверку
					continue
				else:
					#print('неправильный морф тег найден в json')
					return False
			else:
				if tag not in tagset:
					#print('морф тег из правила не найден', tag)
					return False

	return True


def checkOrth(rule_elem, token):
	if rule_elem.Orth:
		if rule_elem.Orth == 'FirstCapital':
			return token[0].isupper() and all(c.islower() for c in token[1:])
		elif rule_elem.Orth == 'AllSmall':
			return all(c.islower() for c in token)
		elif rule_elem.Orth == 'AllCapital':
			return all(c.isupper() for c in token)
		elif rule_elem.Orth == 'CamelCase':
			raise NotImplementedError()
		else:
			raise NotImplementedError()

		return False
	else:
		return True


# функция сравнивает леммы
def compareTags(rule_elem, data_elem, participant, slot_name, matched_pairs):
	flag = False  #в качестве метки для найденой леммы из правили
	if rule_elem.Lex:
		for elem in data_elem['tokens']:
			if elem['lemma'] in rule_elem.Lex:  # находим нужную лемму
				if 'constituent' in elem and elem['constituent']['is_head'] is True:  # and ('Lex' in rule_elem): #проверяем, is_head == True в json и в правиле стоит Lex
					flag = True
					if compareConstitTypes(rule_elem, elem):  # вызываем функцию проверки типа состовляющей
						#print("лемма и тип сост совпали")
						if compareMorphTags(rule_elem, elem):  # вызываем функцию проверки морфологии
							if checkOrth(rule_elem, elem):
								#print("морф теги совпали", elem, rule_elem)
								#на этом этапе идет добавление в словарь matched_pairs пар (элемент из правила: itoken сопоставленного ему элеменрта из json)
								#но! для элемента из правила может быть найдено >1 претендента из json. Поэтому здесь мы проверяем, был ли добавлен элемент из
								# правила. Если был - то бы в его значение добавляем еще один элемент. Если не был - то бы создаем добавляем itoken в новый список,
								# и кладем этот список в значение словаря
								tm = TokenMatching()
								tm.slot_name = slot_name
								tm.token_index = elem['itoken']
								tm.token = elem
								tm.constituent = elem['constituent']

								if participant in matched_pairs:
									matched_pairs[participant].append(tm)
								else:
									matched_pairs[participant] = [tm]

			if (elem == data_elem['tokens'][-1]) and not flag:
				#print('лемма из правила не найдена или условие is_head не совпало с тегом Lex/LexNonHead')
				pass

	#аналогичная ситуация для LexNonHead (is_head == false)
	elif rule_elem.LexNonHead:
		for elem in data_elem['tokens']:
			if elem['itoken'] not in [t.token_index for t in itertools.chain(*matched_pairs.values())]:
				#print(elem['lemma'])
				if elem['lemma'] in rule_elem.LexNonHead:
					if 'constituent' in elem and elem['constituent']['is_head'] is False:  # and ('LexNonHead' in rule_elem):
						flag = True
						if compareConstitTypes(rule_elem, elem):
							#print("лемма и тип сост совпали",)
							if compareMorphTags(rule_elem, elem):
								#print("морф теги совпали")
								if checkOrth(rule_elem, elem):
									tm = TokenMatching()
									tm.slot_name = slot_name
									tm.token_index = elem['itoken']
									tm.token = elem
									tm.constituent = elem['constituent']

									if participant in matched_pairs:
										matched_pairs[participant].append(tm)
									else:
										matched_pairs[participant] = [tm]

			if (elem == data_elem['tokens'][-1]) and not flag:
				#print('лемма из правила не найдена или is_head не совпало с тегом Lex/LexNonHead')
				pass
	else:
		# аналогичная ситуация, когда леммы нет в правиле
		for elem in data_elem['tokens']:
			if True:  #elem['itoken'] not in [t.token_index for t in itertools.chain(*matched_pairs.values())]:
				if compareConstitTypes(rule_elem, elem):
					#print("леммы нет тип сост совпал")
					if compareMorphTags(rule_elem, elem):
						#print("морф теги совпали")
						if checkOrth(rule_elem, elem['token']):
							tm = TokenMatching()
							tm.slot_name = slot_name
							tm.rule_elem = rule_elem
							tm.token_index = elem['itoken']
							tm.token = elem
							tm.constituent = elem.get('constituent')

							if participant in matched_pairs:
								matched_pairs[participant].append(tm)
							else:
								matched_pairs[participant] = [tm]


def compareConstitTypes(rule_elem, data_elem):
	""" функция сравнивает типы составляющих """
	if rule_elem.ConstituentType:
		for const_type in rule_elem.ConstituentType:
			if 'constituent' in data_elem and data_elem['constituent']['name'] == const_type:
				return True
		return False
	else:
		return True


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Fact extractor')
	parser.add_argument('--rules', type=str, default='./Rules_23', help='directory with rules')
	parser.add_argument('--output', type=str, default='tmp/extracted_facts.json', help='fact extraction results')
	parser.add_argument('--verbosity', type=int, default=1, help='print messages to screen')

	args = parser.parse_args()
	rules_dir = args.rules
	output_path = args.output
	verbosity = args.verbosity

	# Загружаем правила из указанного каталога, просматривая рекурсивно все вложенные
	# подкаталоги в поисках файлов *.yaml
	facts = dict()

	if verbosity:
		print('Loading rules from "{}"'.format(rules_dir))

	for fpath in pathlib.Path(rules_dir).rglob('*.yaml'):
		try:
			with open(fpath, 'r', encoding='utf-8') as f:
				data = yaml.safe_load(f)
				fact_name = data['FactName']

			if fact_name not in facts:
				facts[fact_name] = Fact(fact_name)

			facts[fact_name].load_yaml(fpath)
		except Exception as ex:
			print('Error occured when loading facts from "{}":\n{}'.format(fpath, ex))
			exit(0)

	#записываем json с результатами парсинга инпута
	param = set_params(True, False, True, True, ['NOUN', 'PRON', 'PROPN', 'ADV'], ['NP', 'VP', 'AP', 'PP', 'AdvP', 'CCONJP', 'SCONJP', 'NumP', 'PartP'], ['NP', 'VP'])
	fin = open('input.txt', 'r', encoding="utf-8")
	data = write_json.write_parsing(param, fin, verbosity)

	result_json = []
	for isent, sent_data in enumerate(data):
		# Ищем вхождение правил подфактов в результаты парсинга
		extracted_facts = []
		for fact in facts.values():
			for subfact in fact.enum_subfacts():
				#try:
					matchings = subfact.match(sent_data)
					if matchings:
						extracted_facts.extend(matchings)
						#for matching in matchings:
							#print('Извлечен факт "{}" с текстом: {}'.format(fact.get_name(), matching.get_text()))
						break
				#except Exception as ex:
				#	print('Error occured when processing sentence #{} "{}" with fact "{}" rule "{}"'.format(isent, sent_data['text'], fact.get_name(), subfact.get_name()))
				#	print(ex)
				#	for line in traceback.format_stack():
				#		print(line.strip())
				#	exit(0)


		odata = dict()
		result_json.append(odata)
		odata['text'] = sent_data['text']

		fact_jsons = []
		for efact in extracted_facts:
			if verbosity:
				print('Извлечен факт "{}" с текстом "{}" из предложения #{} "{}"'.format(efact.get_fact_name(), efact.get_text(), isent, sent_data['text']))

			slots = efact.get_slots()

			fact_json = dict()
			fact_jsons.append(fact_json)
			fact_json['fact_name'] = efact.get_fact_name()
			fact_json['subfact_name'] = efact.get_subfact_name()
			fact_json['fact_text'] = efact.get_text()

			slots_json = []
			fact_json['slots'] = slots_json

			if slots:
				if verbosity:
					print('Слоты:')
				for slot_name, slot_value in slots:
					if verbosity:
						print('{} = {}'.format(slot_name, slot_value.text))

					slots_json.append({'name': slot_name,
										'text': slot_value.text,
										#'key_word': slot_value.key_word,
										'key_lemma': slot_value.key_lemma,
										'key_index': slot_value.key_index})

			if verbosity:
				print('')

		odata['facts'] = fact_jsons

	with io.open(output_path, 'w', encoding='utf-8') as f:
		json.dump(result_json, f, indent=4)
