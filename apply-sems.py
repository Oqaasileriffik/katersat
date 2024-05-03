#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3
import argparse

parser = argparse.ArgumentParser(prog='apply-sems.py', description='Applies semantic tags from Katersat to a stream of CG-formatted text')
parser.add_argument('-l', '--last', action='store_true')
parser.add_argument('-t', '--trace', action='store_true')
args = parser.parse_args()

dir = os.path.dirname(__file__)
con = sqlite3.connect('file:' + dir + '/katersat.sqlite?mode=ro', uri=True, isolation_level=None, check_same_thread=False)
db = con.cursor()


# Fetch map of semantic classes, turning verbal semantic codes into their English equivalent
sem_map = {}
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code != 'UNK' AND sem_code NOT LIKE 'V.%'")
while row := db.fetchone():
	sem_map[row[0]] = row[0]
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code LIKE 'V.%'")
while row := db.fetchone():
	m = re.match(r'^:([^\s,]+)', row[1])
	if m[1] in sem_map:
		sem_map[row[0]] = 'v'+m[1]
	else:
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

	hyb = (' Hyb/' in line and not ' Hyb/1-' in line)

	origs = re.split(r' (?=(?:(?:i?(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol))|(?:\p{Lu}[_\p{Lu}]+)|U)(?: |$))', line)
	cleans = []
	for orig in origs:
		orig = re.sub(r' Gram/((?:[HIT]V)|(?:Refl))\b', r' gram/\1', orig)
		orig = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur|Hyb|Err)/(\S+)', r'', orig)
		orig = re.sub(r' (ADV|CONJ)-L', r' L', orig)
		orig = orig.replace(' gram/', ' Gram/')
		cleans.append(orig)

	sems = {}
	for i in range(len(origs)-1):
		sems[i] = set()

	longest = False
	max_j = 0

	for i in range(len(origs)-1):
		cur = ''

		for j in range(i, len(origs)-1):
			cur += cleans[j] + ' '

			# If we are at the last morpheme and there already is a longest match, stop
			if j == len(origs)-2 and longest:
				break

			m = None
			if (m := re.match(r'^i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)(.*)$', cleans[j+1])) or (m := re.search(r' Der/([nv])[nv]( |$)', cleans[j+1])):
				pass
			if not m:
				m = ['', '', '']
			wc = m[1][0:1].upper() + m[1][1:]
			flex = m[2]
			ana = cur.strip() + ' ' + wc

			anas = []
			# Raw match for morpheme sequences
			anas.append(ana)
			if (m := re.match(r'^((?:i?\d?\p{Lu}\p{Ll}[^/\s]*(?: |$))+)', flex)):
				flex = re.sub(r'\bi(\p{Lu})', r'\1', m[1]).split(' ')
				for fi in range(len(flex), 0, -1):
					ana2 = (f'{ana} %s' % ' '.join(flex[0:fi])).strip()
					anas.append(ana2)
					if re.search(r' \dPl(O)?$', ana2):
						anas.append(re.sub(r' (\d)Pl(O)?$', r' \1Sg\2', ana2))
					anas.append((ana + ' ' + re.sub(r'\b(Rel|Trm|Abl|Lok|Aeq|Ins|Via|Nom|Akk)\b', r'Abs', ' '.join(flex[0:fi]))).strip())
			if wc != 'V':
				anas.append(ana + ' Abs Sg')
				anas.append(ana + ' Ins Sg')
				anas.append(ana + ' Abs Pl')
				anas.append(ana + ' Ins Pl')
			else:
				if re.search(r'^.* Gram/IV', ana) or re.search(r'^.* Gram/Refl', ana) or not re.search(r'^.* Gram/TV', ana):
					anas.append(ana + ' Ind 3Sg')
					anas.append(ana + ' Ind 3Pl')
				if re.search(r'^.* Gram/TV', ana) or not re.search(r'^.* Gram/IV', ana):
					anas.append(ana + ' Ind 3Sg 3SgO')
					anas.append(ana + ' Ind 3Pl 3PlO')
					anas.append(ana + ' Ind 3Sg 3PlO')
					anas.append(ana + ' Ind 3Pl 3SgO')

			if hyb:
				anas.extend([re.sub(r'^"(\p{Lu}+)" ', r'\1 ', x) for x in anas])
			#print(f'{i} {j}: {cur} | {anas}')

			# Finding matching analyses as its own step is 3 orders of magnitude faster
			ids = []
			for ana in anas:
				did = False
				db.execute("SELECT fst_ana, kl.lex_id, COALESCE(let_attrs, 0) FROM kat_long_raw NATURAL JOIN kat_lexemes as kl LEFT JOIN kat_lexeme_attrs as kla ON (kl.lex_id = kla.lex_id) WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib' AND lex_semclass != 'UNK'", [ana[0:16]])
				while r := db.fetchone():
					if r[0] == ana:
						ids.append(str(r[1]))
						did = ((r[2] & 32) == 0)
				if did:
					break

				# Allow looking up morphemes without Gram/[HIT]V
				if not ana.startswith('"'):
					ana = re.sub(r' Gram/[HIT]V ', r' ', ana)
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
					max_j = max(j, max_j)

					if i == 0 and j == len(origs)-2:
						longest = True

				# If we are looking for long matches from baseform, only keep the longest match
				if i == 0:
					# But, roots should keep their own semantics, as morphemes do, so start at 1
					for k in range(1, max_j):
						sems[k] = set()


	if args.last:
		for i in range(max_j):
			sems[i] = set()

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
		while (o := re.sub(r' (Sem/\S+.*? \p{Lu}[_\p{Lu}]+ )', r' i\1', out)) != out:
			out = o
		news.append(out)

	cache[line] = news
	for out in news:
		print('\t' + out)
	sys.stdout.flush()

#print(stats, file=sys.stderr)
