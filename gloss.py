#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3
import argparse

parser = argparse.ArgumentParser(prog='gloss.py', description='Applies foreign language glosses from Katersat to a stream of CG-formatted text')
parser.add_argument('-t', '--trace', action='store_true')
parser.add_argument('-l', '--lang', action='store_true', default='eng')
parser.add_argument('lang', nargs='?', default='eng')
args = parser.parse_args()

# Some word classes are different in Katersat
wc_map_s = {
	'N': 'T',
	'V': 'V',
	'Pali': 'Pali',
	'Conj': 'Conj',
	'Adv': 'Adv',
	'Interj': 'Intj',
	'Pron': 'Pron',
	'Prop': 'Prop',
	'Num': 'Num',
	'Symbol': 'Symbol',
	'Adj': 'Adj',
	'Part': 'Part',
	'Prep': 'Prep',
}
wc_map_k = {v: k for k, v in wc_map_s.items()}

dir = os.path.dirname(__file__)
con = sqlite3.connect('file:' + dir + '/katersat.sqlite?mode=ro', uri=True, isolation_level=None, check_same_thread=False)
db = con.cursor()


# Fetch map of semantic classes, mapping verbal semantic codes from their English equivalent
sem_map_k = {}
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code != 'UNK' AND sem_code NOT LIKE 'V.%'")
while row := db.fetchone():
	sem_map_k[row[0]] = row[0]
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code LIKE 'V.%'")
while row := db.fetchone():
	m = re.match(r'^:([^\s,]+)', row[1])
	if m[1] in sem_map_k:
		sem_map_k[row[0]] = 'v'+m[1]
	else:
		sem_map_k[row[0]] = m[1]
sem_map_s = {v: k for k, v in sem_map_k.items()}


stats = {
	'hit': 0,
	'miss': 0,
	'clear': 0,
}
cache = {}

for line in sys.stdin:
	line = line.rstrip()

	if not line.startswith('\t"') or (' <tr-done> ' in line) or not re.search(r' (?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)', line):
		print(line)
		sys.stdout.flush()
		if len(cache) >= 20000:
			stats['clear'] += 1
			cache = {}
		continue

	line = line.strip()

	if dep := re.search(r'( #\d+->\d+)( |$)', line):
		dep = dep[1]
		line = line.replace(dep, '')
	else:
		dep = ''

	if func := re.search(r'((?: @\S+)+)( |$)', line):
		func = func[1]
		line = line.replace(func, '')
	else:
		func = ''

	if rnum := re.search(r'( ¤\S+)( |$)', line):
		rnum = rnum[1]
		line = line.replace(rnum, '')
	else:
		rnum = ''

	if line in cache:
		stats['hit'] += 1
		print('\t' + cache[line] + rnum + func + dep)
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
		orig = re.sub(r' i?Sem/(\S+)', r'', orig)
		orig = orig.replace(' gram/', ' Gram/')
		cleans.append(orig)

	# Python doesn't have a real for() loop, so...
	i = 0
	e = len(origs)-1
	while i < e:
		for j in range(len(origs)-1, i, -1):
			cur = ' '.join(cleans[i:j])

			m = None
			if (m := re.match(r'^i?(N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)(.*)$', cleans[j])) or (m := re.search(r' Der/([nv])[nv]( |$)', cleans[j])):
				pass
			if not m:
				m = ['', '', '']
			wc = m[1][0:1].upper() + m[1][1:]
			flex = m[2].strip()
			ana = (cur + ' ' + wc).strip()
			#print(f'{i} {j-1}: {cur} | {wc} | {flex}')

			anas = []
			# Raw match for morpheme sequences
			anas.append(ana)
			# First try actual case/flexion
			if (m := re.match(r'^((?:i?\d?\p{Lu}\p{Ll}[^/\s]* *)+)', flex)) or (m := re.match(r'^(LU)(?: |$)', flex)):
				flex = re.sub(r'\bi(\p{Lu})', r'\1', m[1])
				ana2 = f'{ana} {flex}'.strip()
				anas.append(ana2)
				if re.search(r' \dPl(O?)$', ana2):
					anas.append(re.sub(r' (\d)Pl(O?)$', r' \1Sg\2', ana2))
				anas.append((ana + ' ' + re.sub(r'\b(Rel|Trm|Abl|Lok|Aeq|Ins|Via|Nom|Akk)\b', r'Abs', flex)).strip())
				if re.search(r'\b\d(Sg|Pl)Poss\b', flex):
					anas.append((ana + ' ' + re.sub(r'\b\d(Sg|Pl)Poss\b', '', flex)).strip())
					anas.append((ana + ' ' + re.sub(r'\b(?:Rel|Trm|Abl|Lok|Aeq|Ins|Via|Nom|Akk) (Sg|Pl) \d(Sg|Pl)Poss\b', r'Abs \1', flex)).strip())
			# Then fall back to baseforms
			if wc != 'V':
				anas.append(ana + ' Abs Sg')
				anas.append(ana + ' Ins Sg')
				anas.append(ana + ' Abs Pl')
				anas.append(ana + ' Ins Pl')
			else:
				if re.search(r'^.* Gram/[HI]V', ana) or re.search(r'^.* Gram/Refl', ana) or not re.search(r'^.* Gram/TV', ana):
					anas.append(ana + ' Ind 3Sg')
					anas.append(ana + ' Ind 3Pl')
				if re.search(r'^.* Gram/[HT]V', ana) or not re.search(r'^.* Gram/IV', ana):
					anas.append(ana + ' Ind 3Sg 3SgO')
					anas.append(ana + ' Ind 3Pl 3PlO')
					anas.append(ana + ' Ind 3Sg 3PlO')
					anas.append(ana + ' Ind 3Pl 3SgO')

			if hyb:
				anas.extend([re.sub(r'^"(\p{Lu}+)" ', r'\1 ', x) for x in anas])

			pfx = re.search(r' (Prefix/[TA]A) ', ana)
			prefix = ''

			s1 = 'UNK'
			s2 = 'UNK'
			if (m := re.search(r'\bi?Sem/(\S+) i?Sem/(\S+)\b', origs[j-1])) and (m[1] in sem_map_s) and (m[2] in sem_map_s):
				s1, s2 = sem_map_s[m[1]], sem_map_s[m[2]]
			elif (m := re.search(r'\bi?Sem/(\S+)\b', origs[j-1])) and (m[1] in sem_map_s):
				s1 = sem_map_s[m[1]]

			#print(f'{i} {j-1}: {cur} | {anas} | {s1} {s2}')

			did = False
			for ana in anas:
				ids = []
				db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
				while r := db.fetchone():
					if r[0] == ana:
						ids.append(str(r[1]))

				# Allow looking up morphemes without Gram/[HIT]V
				if not ids and not ana.startswith('"'):
					ana = re.sub(r' Gram/[HIT]V ', r' ', ana)
					db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
					while r := db.fetchone():
						if r[0] == ana:
							ids.append(str(r[1]))

				# If there is a prefix, try without it
				if not ids and pfx:
					ana = ana.replace(pfx[0], ' ')
					db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
					while r := db.fetchone():
						if r[0] == ana:
							ids.append(str(r[1]))
							prefix = pfx[1]

				# N may also be Pron
				if not ids and ' N ' in ana and not ' Pron ' in ana:
					ana = ana.replace(' N ', ' Pron ')
					anas2 = [ana]
					for sgpl in ['Sg', 'Pl']:
						for num in ['', '1', '2', '3', '4']:
							anas2.append(ana.replace(' Sg', f' {num}{sgpl}'))
							anas2.append(ana.replace(' Pl', f' {num}{sgpl}'))
							anas2.append(ana.replace(f' {num}Sg', f' {num}{sgpl}'))
							anas2.append(ana.replace(f' {num}Pl', f' {num}{sgpl}'))
					for ana in anas2:
						db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
						while r := db.fetchone():
							if r[0] == ana:
								ids.append(str(r[1]))
						if ids:
							break

				if ids:
					db.execute("SELECT DISTINCT tr.lex_lexeme, tr.lex_semclass as sem, tr.lex_sem2 as sem2, tr.lex_wordclass as wc, kl.lex_id as k_id, tr.lex_id as t_id FROM kat_lexemes as kl NATURAL JOIN glue_lexeme_synonyms AS gls INNER JOIN kat_lexemes as tr ON (gls.lex_syn = tr.lex_id) WHERE kl.lex_id IN (" + ','.join(ids) + ") AND kl.lex_semclass = ? AND kl.lex_sem2 = ? AND tr.lex_language = ? ORDER BY kl.lex_id ASC, gls.syn_order ASC, tr.lex_id ASC LIMIT 1", [s1, s2, args.lang])
					tr = db.fetchone()

					# If there were no semantics and we did not find a match, try any semantics
					if not tr and s1 == 'UNK':
						db.execute("SELECT DISTINCT tr.lex_lexeme, tr.lex_semclass as sem, tr.lex_sem2 as sem2, tr.lex_wordclass as wc, kl.lex_id as k_id, tr.lex_id as t_id FROM kat_lexemes as kl NATURAL JOIN glue_lexeme_synonyms AS gls INNER JOIN kat_lexemes as tr ON (gls.lex_syn = tr.lex_id) WHERE kl.lex_id IN (" + ','.join(ids) + ") AND tr.lex_language = ? ORDER BY kl.lex_id ASC, gls.syn_order ASC, tr.lex_id ASC LIMIT 1", [args.lang])
						tr = db.fetchone()

					if tr:
						wc = wc_map_k[tr[3].capitalize()]

						sem = ''
						if prefix:
							sem = ' ' + prefix
						if tr[1] in sem_map_k:
							sem += ' Sem/'  + sem_map_k[tr[1]]
						if tr[2] in sem_map_k:
							sem += ' Sem/'  + sem_map_k[tr[2]]

						#print(f'{i} {j-1}: {tr}')
						out = f'"{tr[0]}"{sem} {wc}'
						if args.trace:
							out += f' TR-LEX:{tr[4]}:{tr[5]}'
						origs[i] = f'{out} <tr>'
						k = i+1
						while k < j:
							origs[k] = ''
							k += 1
						i = j-1

						did = True
						break

			if did:
				break

		i += 1

	orig = re.sub(r'  +', r' ', ' '.join(origs))

	# Mark semantics before derivation as internal
	while (o := re.sub(r' (Sem/\S+.*? (?:U|\p{Lu}[_\p{Lu}]+) )', r' i\1', orig)) != orig:
		orig = o

	# Mark word classes before derivation or other word classes as internal
	while (o := re.sub(r' ((?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol) .*? (?:(?:U|\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) )', r' i\1', orig)) != orig:
		orig = o

	cache[line] = orig
	print(f'\t{orig}{rnum}{func}{dep}')
	sys.stdout.flush()

#print(stats, file=sys.stderr)
