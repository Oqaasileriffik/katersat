#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import hashlib
from pathlib import Path
import sqlite3

def sha1_file(fn):
	d = Path(fn).read_bytes()
	h = hashlib.sha1(d)
	return h.hexdigest()

dir = os.path.dirname(__file__)
os.chdir(dir)

if os.path.exists('katersat.sqlite') and os.path.getmtime(__file__) > os.path.getmtime('katersat.sqlite'):
	print('Forcing Katersat update')
	subprocess.run(['rm', '-f', 'katersat.sqlite'])

if not os.path.exists('katersat.sqlite') or not os.path.getsize('katersat.sqlite'):
	subprocess.run(['rm', '-f', 'data.sql', 'etag.txt', 'headers.txt'])

sha=''
if os.path.exists('data.sql'):
	if os.path.exists('etag.txt') and os.path.getmtime('etag.txt') > os.path.getmtime('data.sql'):
		sha=Path('etag.txt').read_text(encoding='UTF-8')
	else:
		sha = sha1_file('data.sql')
		Path('etag.txt').write_text(sha)

subprocess.run(['curl', '-D', 'headers.txt', '--no-progress-meter', '--compressed', '--etag-compare', 'etag.txt', '--etag-save', 'etag-new.txt', 'https://tech.oqaasileriffik.gl/katersat/export-katersat.php', '-o', 'data.sql'])

if os.path.getsize('etag-new.txt'):
	os.rename('etag-new.txt', 'etag.txt')

new=sha
if os.path.getmtime('etag.txt') <= os.path.getmtime('data.sql'):
	new = sha1_file('data.sql')

if sha == new:
	print('Katersat is already up to date')
	sys.exit()


print('Loading new Katersat data...')
subprocess.run(['rm', '-f', 'katersat.sqlite.new'])
subprocess.run(['sqlite3', 'katersat.sqlite.new', '-init', 'schema.sql'], input='')
subprocess.run(['sqlite3', 'katersat.sqlite.new', '-init', 'data.sql'], input='')
Path('etag.txt').write_text(new)
print('Converting longest match...')

con = sqlite3.connect('katersat.sqlite.new')
db = con.cursor()

db.execute("SELECT DISTINCT * FROM (SELECT lex_id, lex_lexeme, lex_stem, lex_valence FROM kat_lexemes WHERE lex_language = 'kal' AND lex_lexeme NOT LIKE '% %' UNION SELECT lex_id, lex_lexeme, lex_stem, lex_valence FROM kat_lexemes WHERE lex_language = 'kal' AND lex_lexeme LIKE '% Der/%')")
rows = db.fetchall()
for row in rows:
	id = row[0]
	stems = row[2].strip().split('\n')
	if m := re.search(r'.* Der/[nv]([nv])', row[1]):
		db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [row[1] + ' ' + m[1].capitalize(), id])
	for stem in stems:
		if not stem:
			continue
		m = None
		if not (m := re.match(r'^(\+?[^+]*)\+(.*)$', stem)):
			print(f'Warning: Lexeme {id} invalid analysis {stem}')
			continue
		stem = f'"{m[1]}" ' + m[2].replace('+', ' ')
		stem = re.sub(r' Gram/((?:[HIT]V)|(?:Refl))\b', r' gram/\1', stem)
		stem = re.sub(r' (Gram|Dial|Orth|O[lL]ang|Heur|Hyb|Err)/(\S+)', r'', stem)
		stem = stem.replace(' gram/', ' Gram/')
		db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [stem, id])
		if ' Gram/HV Gram/IV ' in stem:
			#print(f'Reducing Gram/HV Gram/IV in {stem}')
			stem = stem.replace(' Gram/HV Gram/IV ', ' Gram/HV ')
			db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [stem, id])
		if 'Gram/' not in stem:
			if row[3] == 1:
				#print(f'Adding Gram/IV to {stem}')
				stem = stem.replace('" ', '" Gram/IV ')
				db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [stem, id])
			if row[3] == 2:
				#print(f'Adding Gram/TV to {stem}')
				stem = stem.replace('" ', '" Gram/TV ')
				db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [stem, id])

con.commit()

os.rename('katersat.sqlite.new', 'katersat.sqlite')

print('Katersat updated')
