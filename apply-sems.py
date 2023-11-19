#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3

dir = os.path.dirname(__file__)
con = sqlite3.connect('file:' + dir + '/katersat.sqlite?mode=ro', uri=True, isolation_level=None, check_same_thread=False)
db = con.cursor()


# Fetch map of semantic classes, turning verbal semantic codes into their English equivalent
sem_map = {}
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code != 'UNK'")
while row := db.fetchone():
	sem_map[row[0]] = row[0]
	if row[0][0:2] == 'V.' and (m := re.match(r'^:([^\s,]+)', row[1])) != None:
		sem_map[row[0]] = m[1]


for line in sys.stdin:
	line = line.rstrip()

	if not line.startswith('\t"') or not re.search(r' (?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)', line):
		print(line)
		sys.stdout.flush()
		continue

	line = line.lstrip()
	orig = line

	outs = ['']
	cur = ''
	while line:
		line = line.lstrip()
		stop = 0
		tag = ''

		if line.startswith('"') and (stop := line.find('"', 1)) != -1:
			tag = line[0:stop+1]
			line = line[stop+1:]
		elif (stop := line.find(' ')) != -1:
			tag = line[0:stop]
			line = line[stop:]
		else:
			tag = line
			line = ''

		m = None
		if (m := re.match(r'^i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)$', tag)) or re.match(r'^\p{Lu}\p{Lu}+$', tag):
			if not m:
				m = re.search(r' Der/([nv])[nv]', line)
			if not m:
				m = re.search(r' i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)', line)
			if not m:
				m = ['', '']
			pos = m[1][0:1].upper() + m[1][1:]
			ana = cur + pos

			anas = []
			if (m := re.match(r'^((?: i?\d?\p{Lu}\p{Ll}[^/\s]*)+)', line)):
				anas.append(ana + re.sub(r' i', r' ', m[1]))
			if pos != 'V':
				anas.append(ana + ' Abs Sg')
				anas.append(ana + ' Ins Sg')
				anas.append(ana + ' Abs Pl')
				anas.append(ana + ' Ins Pl')
			if re.search(r'^.* Gram/IV', ana):
				anas.append(ana + ' Ind 3Sg')
				anas.append(ana + ' Ind 3Pl')
			if re.search(r'^.* Gram/TV', ana):
				anas.append(ana + ' Ind 3Sg 3SgO')
				anas.append(ana + ' Ind 3Pl 3PlO')

			# Finding matching analyses as its own step is 3 orders of magnitude faster
			ids = []
			for ana in anas:
				did = False
				db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
				while r := db.fetchone():
					if r[0] == ana:
						ids.append(str(r[1]))
						did = True
				if did:
					break

			if ids:
				db.execute("SELECT DISTINCT lex_semclass, lex_sem2 FROM kat_lexemes WHERE lex_id IN (" + ','.join(ids) + ") AND lex_semclass != 'UNK'")
				new_outs = []
				while sem := db.fetchone():
					for out in outs:
						code = ''
						if sem[0] != 'UNK' and sem[1] != 'UNK':
							code = f'Sem/{sem_map[sem[0]]} Sem/{sem_map[sem[1]]}'
						else:
							code = f'Sem/{sem_map[sem[0]]}'
						new_outs.append(out + code + ' ')

				if new_outs:
					outs = sorted(set(new_outs))

			cur += tag + ' ';
		elif tag.startswith('"') or re.match(r'^Der/', tag) or re.match(r'^Gram/[HIT]V$', tag) or re.match(r'^i?Sem/', tag):
			cur += tag + ' ';

		for i in range(len(outs)):
			outs[i] += tag + ' '


	# Attach semantics to morphemes that don't currently have
	sems = set()
	for out in outs:
		ms = None
		if not (ms := re.findall(r' (\p{Lu}\p{Lu}+ Der/.*?)(?= (?:(?:\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) )', out)):
			continue

		for ana in ms:
			if ' Sem/' in ana:
				continue
			pos = re.search(r' Der/[nv]([nv])', ana)[1].capitalize()
			ana = ana + ' ' + pos
			lit_ana = ana
			anas = []
			anas.append(ana)
			anas.append(re.sub(r' Gram/[HIT]V', r'', ana))

			ids = []
			for ana in anas:
				did = False
				db.execute("SELECT fst_ana, lex_id FROM kat_long_raw WHERE substr(fst_ana,1,16) = ?", [ana[0:16]])
				while r := db.fetchone():
					if r[0] == ana:
						ids.append(str(r[1]))
						did = True
				if did:
					break

			if ids:
				db.execute("SELECT DISTINCT lex_id, lex_semclass, lex_sem2 FROM kat_lexemes WHERE lex_id IN (" + ','.join(ids) + ") AND lex_semclass != 'UNK'")
				while sem := db.fetchone():
					code = ''
					if sem[1] != 'UNK' and sem[2] != 'UNK':
						code = f'Sem/{sem_map[sem[1]]} Sem/{sem_map[sem[2]]}'
					else:
						code = f'Sem/{sem_map[sem[1]]}'
					sems.add(lit_ana + '\ue001' + code)

	for sem in sems:
		sem = sem.split('\ue001')
		sem[0] = re.sub(r' (N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)$', r'', sem[0])
		sem[0] = re.escape(sem[0]).replace(r'\ ', ' ')

		new_outs = []
		for out in outs:
			new_outs.append(re.sub(r' (' + sem[0] + r')( (?:(?:\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) )', r' \1 ' + sem[1] + r'\2', out))
		outs = new_outs


	for out in outs:
		# Mark semantics before derivation as internal
		while (o := re.sub(r' (Sem/\S+.*? \p{Lu}\p{Lu}+ )', r' i\1', out)) != out:
			out = o
		print('\t' + out)
	sys.stdout.flush()
