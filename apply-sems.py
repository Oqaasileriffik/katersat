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

	origs = re.split(r' (?=(?:(?:i?(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol))|(?:\p{Lu}\p{Lu}+))(?: |$))', line.strip())
	cleans = []
	for orig in origs:
		orig = re.sub(r' Gram/([HIT]V)( |$)', r' gram/\1\2', orig)
		orig = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur|Hyb)/(\S+)', r'', orig)
		orig = orig.replace(' gram/', ' Gram/')
		cleans.append(orig)

	sems = {}
	for i in range(len(origs)-1):
		sems[i] = set()

	for i in range(len(origs)-1):
		cur = ''

		for j in range(i, len(origs)-1):
			cur += cleans[j] + ' '

			m = ['', '']
			if (m := re.match(r'^i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)(.*)$', cleans[j+1])) or (m := re.search(r' Der/([nv])[nv]( |$)', cleans[j+1])):
				pass
			wc = m[1][0:1].upper() + m[1][1:]
			flex = m[2]
			ana = cur + wc

			anas = []
			if (m := re.match(r'^((?:i?\d?\p{Lu}\p{Ll}[^/\s]*(?: |$))+)', flex)):
				anas.append(ana + re.sub(r' i', r' ', m[1]))
			if wc != 'V':
				anas.append(ana)
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
				while sem := db.fetchone():
					code = ''
					if sem[0] != 'UNK' and sem[1] != 'UNK':
						code = f'Sem/{sem_map[sem[0]]} Sem/{sem_map[sem[1]]}'
					else:
						code = f'Sem/{sem_map[sem[0]]}'
					sems[j].add(code)

	outs = ['']
	for i in range(len(origs)-1):
		news = []
		for out in outs:
			new = out + ' ' + origs[i]
			if not sems[i]:
				news.append(new)
			for sem in sems[i]:
				news.append(new + ' ' + sem)
		outs = news

	for out in sorted(set(outs)):
		out += ' ' + origs[-1]
		out = out.strip()
		# Mark semantics before derivation as internal
		while (o := re.sub(r' (Sem/\S+.*? \p{Lu}\p{Lu}+ )', r' i\1', out)) != out:
			out = o
		print('\t' + out)
	sys.stdout.flush()
