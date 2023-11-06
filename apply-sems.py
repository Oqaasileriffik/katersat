#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3

dir = os.path.dirname(__file__)
con = sqlite3.connect(dir + '/katersat.sqlite', isolation_level=None)
db = con.cursor()


# Fetch map of semantic classes, turning verbal semantic codes into their English equivalent
sem_map = {}
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses")
while row := db.fetchone():
	sem_map[row[0]] = row[0]
	if row[0][0:2] == 'V.' and (m := re.match(r'^:([^\s,]+)', row[1])) != None:
		sem_map[row[0]] = m[1]


for line in sys.stdin:
	line = line.rstrip()

	if not line.startswith('\t') or not re.search(r' (?:N|V|Num|Adv|Interj|Pron|Prop)(?: |$)', line):
		print(line)
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
			line = None

		m = None
		if (m := re.match(r'^(N|V|Num|Adv|Interj|Pron|Prop)$', tag)) or re.match(r'^\p{Lu}+$', tag):
			if not m:
				m = re.search(r' Der/([nv])[nv]', line)
			pos = m[1][0:1].upper() + m[1][1:]
			db.execute("SELECT DISTINCT lex_semclass, lex_sem2 FROM kat_longest_match NATURAL JOIN kat_lexemes WHERE fst_ana = ? AND lex_semclass != 'UNK'", [cur + pos])
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

	for out in outs:
		# Mark semantics before derivation as internal
		while (o := re.sub(r' (Sem/\S+.*? \p{Lu}\p{Lu}+ )', r' i\1', out)) != out:
			out = o
		print('\t' + out)
