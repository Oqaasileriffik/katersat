#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3
import argparse

parser = argparse.ArgumentParser(prog='apply-sems.py', description='Applies semantic tags from Katersat to a stream of CG-formatted text')
parser.add_argument('-t', '--trace', action='store_true')
args = parser.parse_args()

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

stats = {
	'hit': 0,
	'miss': 0,
	'clear': 0,
}
cache = {}

for line in sys.stdin:
	line = line.rstrip()

	if not line.startswith('\t"') or not re.search(r' (?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)', line):
		print(line)
		sys.stdout.flush()
		if len(cache) >= 20000:
			stats['clear'] += 1
			cache = {}
		continue

	line = line.strip()
	if line in cache:
		stats['hit'] += 1
		for out in cache[line]:
			print('\t' + out)
		sys.stdout.flush()
		continue
	stats['miss'] += 1

	origs = re.split(r' (?=(?:(?:i?(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol))|(?:\p{Lu}\p{Lu}+)|U)(?: |$))', line)
	cleans = []
	for orig in origs:
		orig = re.sub(r' Gram/([HIT]V)( |$)', r' gram/\1\2', orig)
		orig = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur|Hyb|Err)/(\S+)', r'', orig)
		orig = re.sub(r' (ADV|CONJ)-L', r' L', orig)
		orig = orig.replace(' gram/', ' Gram/')
		cleans.append(orig)

	sems = {}
	for i in range(len(origs)-1):
		sems[i] = set()

	for i in range(len(origs)-1):
		cur = ''

		for j in range(i, len(origs)-1):
			cur += cleans[j] + ' '

			m = None
			if (m := re.match(r'^i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)(.*)$', cleans[j+1])) or (m := re.search(r' Der/([nv])[nv]( |$)', cleans[j+1])):
				pass
			if not m:
				m = ['', '', '']
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
				anas.append(ana + ' Ind 3Sg 3PlO')
				anas.append(ana + ' Ind 3Pl 3SgO')

			# Finding matching analyses as its own step is 3 orders of magnitude faster
			ids = []
			for ana in anas:
				did = False
				db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib' AND lex_semclass != 'UNK'", [ana[0:16]])
				while r := db.fetchone():
					if r[0] == ana:
						ids.append(str(r[1]))
						did = True
				if did:
					break

			if ids:
				db.execute("SELECT DISTINCT lex_semclass, lex_sem2, lex_id FROM kat_lexemes WHERE lex_id IN (" + ','.join(ids) + ") AND lex_semclass != 'UNK'")
				while sem := db.fetchone():
					code = ''
					if sem[0] != 'UNK' and sem[1] != 'UNK':
						code = f'Sem/{sem_map[sem[0]]} Sem/{sem_map[sem[1]]}'
					else:
						code = f'Sem/{sem_map[sem[0]]}'
					if args.trace:
						code = f'{code} SEM-LEX:{sem[2]}'.strip()
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

	news = []
	for out in sorted(set(outs)):
		out += ' ' + origs[-1]
		out = out.strip()
		# Mark semantics before derivation as internal
		while (o := re.sub(r' (Sem/\S+.*? \p{Lu}\p{Lu}+ )', r' i\1', out)) != out:
			out = o
		news.append(out)

	cache[line] = news
	for out in news:
		print('\t' + out)
	sys.stdout.flush()

#print(stats, file=sys.stderr)
