#!/usr/bin/env python3
import sys
import regex as re
import os
import sqlite3

# Default to English, but allow for other languages
lang = sys.argv[1] if len(sys.argv) >= 2 else 'eng'

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
db.execute("SELECT sem_code, sem_eng FROM kat_semclasses WHERE sem_code != 'UNK'")
while row := db.fetchone():
	sem_map_k[row[0]] = row[0]
	if row[0][0:2] == 'V.' and (m := re.match(r'^:([^\s,]+)', row[1])) != None:
		sem_map_k[row[0]] = m[1]
sem_map_s = {v: k for k, v in sem_map_k.items()}


printed = set()
for line in sys.stdin:
	line = line.rstrip()

	if not line.startswith('\t"') or (' <tr-done> ' in line) or not re.search(r' (?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)(?: |$)', line):
		printed = set()
		print(line)
		sys.stdout.flush()
		continue

	line = ' <dmtr> ' + line.strip() + ' '
	orig = line

	while ' <dmtr> ' in orig:
		line = orig
		line = re.sub(r' Gram/([HIT]V) ', r' gram/\1 ', line)
		line = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur|Hyb)/(\S+)', r'', line)
		line = line.replace(' gram/', ' Gram/')
		line = line.replace(' iSem/', ' Sem/')

		# Longest match
		while (m := re.search(r'<dmtr> (.*) (i?(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol))( .*)$', line)) or (m := re.search(r'<dmtr> (.*) ((?:U|\p{Lu}\p{Lu}+) Der/[nv][nv])( .*)$', line)):
			lm = m[1]
			wc_raw = m[2]
			wc_s = m[2]
			rest = m[3]
			if wc_s.startswith('i'):
				wc_s = wc_s[1:]
			elif (w := re.search(r' Der/([nv])[nv]', wc_raw)):
				wc_s = w[1].capitalize()
			wc_k = wc_map_s[wc_s]

			s1 = 'UNK'
			s2 = 'UNK'
			if (m := re.search(r' Sem/(\S+) Sem/(\S+)$', lm)) and (m[1] in sem_map_s) and (m[2] in sem_map_s):
				s1, s2 = sem_map_s[m[1]], sem_map_s[m[2]]
			elif (m := re.search(r' Sem/(\S+)$', lm)) and (m[1] in sem_map_s):
				s1 = sem_map_s[m[1]]

			lm = re.sub(r' Sem/\S+', '', lm)
			ana = lm + ' ' + wc_s

			anas = []
			# Raw match for morpheme sequences
			anas.append(ana)
			# First try actual case/flexion
			if (m := re.match(r'^((?: i?\d?\p{Lu}\p{Ll}[^/\s]*)+)', rest)):
				flex = re.sub(r' i', r'', m[1])
				anas.append(ana + flex)
				anas.append(ana + re.sub(r' (Rel|Trm|Abl|Lok|Aeq|Ins|Via|Nom|Akk)', r' Abs', flex))
			# Then fall back to baseforms
			if wc_raw != 'V':
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

			pfx = re.search(r' (Prefix/[TA]A) ', ana)
			prefix = ''

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

				# Allow looking up morphemes without Gram/[HIT]V
				if not ana.startswith('"'):
					ana = re.sub(r' Gram/[HIT]V ', r' ', ana)
					db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
					while r := db.fetchone():
						if r[0] == ana:
							ids.append(str(r[1]))
							did = True
					if did:
						break

				# If there is a prefix, try without it
				if pfx:
					ana = ana.replace(pfx[0], ' ')
					db.execute("SELECT fst_ana, lex_id FROM kat_long_raw NATURAL JOIN kat_lexemes WHERE substr(fst_ana,1,16) = ? AND lex_semclass != 'meta-cat-lib'", [ana[0:16]])
					while r := db.fetchone():
						if r[0] == ana:
							ids.append(str(r[1]))
							did = True
							prefix = pfx[1]
					if did:
						break

			if ids:
				lm = re.sub(r' \S+?/\S+', r'', lm)
				lm = re.escape(lm).replace(r'\ ', ' ')
				lm = lm.replace('" ', '".*? ')
				lm = re.sub(r'( (?:U|\p{Lu}\p{Lu}+))( |$)', r'.*?\1.*?\2', lm)
				lm += '.*? (' + wc_raw + ' )'

				tr = None
				db.execute("SELECT DISTINCT tr.lex_lexeme, tr.lex_semclass as sem, tr.lex_sem2 as sem2, tr.lex_wordclass as wc FROM kat_lexemes as kl NATURAL JOIN glue_lexeme_synonyms AS gls INNER JOIN kat_lexemes as tr ON (gls.lex_syn = tr.lex_id) WHERE kl.lex_id IN (" + ','.join(ids) + ") AND kl.lex_semclass = ? AND kl.lex_sem2 = ? AND tr.lex_language = ? ORDER BY kl.lex_id ASC, gls.syn_order ASC, tr.lex_id ASC LIMIT 1", [s1, s2, lang])
				tr = db.fetchone()

				# If we did not find a match with semantics, try without
				if not tr:
					db.execute("SELECT DISTINCT tr.lex_lexeme, tr.lex_semclass as sem, tr.lex_sem2 as sem2, tr.lex_wordclass as wc FROM kat_lexemes as kl NATURAL JOIN glue_lexeme_synonyms AS gls INNER JOIN kat_lexemes as tr ON (gls.lex_syn = tr.lex_id) WHERE kl.lex_id IN (" + ','.join(ids) + ") AND tr.lex_language = ? ORDER BY kl.lex_id ASC, gls.syn_order ASC, tr.lex_id ASC LIMIT 1", [lang])
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

					orig = re.sub(' <dmtr> ' + lm, f' "{tr[0]}"{sem} {wc} <tr> <dmtr> \\1', orig)
					line = orig
					line = re.sub(r' Gram/([HIT]V) ', r' gram/\1 ', line)
					line = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur)/(\S+)', r'', line)
					line = line.replace(' gram/', ' Gram/')
					line = line.replace(' iSem/', ' Sem/')
					line += ' '
					continue

			nline = re.sub(r'^(.+ (?:U|\p{Lu}\p{Lu}+) Der/[nv][nv] ).*'+wc_raw+' .*$', r'\1', line)
			if nline == line:
				break
			line = nline

		if (m := re.search(r' (<dmtr>) ("[^"]+".*?) ((?:U|\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) ', orig)) or (m:= re.search(r' (<dmtr>) ((?:U|\p{Lu}\p{Lu}+) .*?) ((?:U|\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) ', orig)):
			orig = orig.replace(f' {m[1]} {m[2]} {m[3]} ', f' {m[2]} {m[1]} {m[3]} ')
		else:
			orig = orig.replace(' <dmtr>', '')

	orig = re.sub(r'  +', r' ', orig).strip()
	if orig in printed:
		continue
	printed.add(orig)

	# Mark semantics before derivation as internal
	while (o := re.sub(r' (Sem/\S+.*? (?:U|\p{Lu}\p{Lu}+) )', r' i\1', orig)) != orig:
		orig = o
	# Mark word classes before derivation or other word classes as internal
	while (o := re.sub(r' ((?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol) .*? (?:(?:U|\p{Lu}\p{Lu}+)|(?:N|V|Pali|Conj|Adv|Interj|Pron|Prop|Num|Symbol)) )', r' i\1', orig)) != orig:
		orig = o
	print(f'\t{orig}')
	sys.stdout.flush()
