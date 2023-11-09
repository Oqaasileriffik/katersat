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

if not os.path.exists('katersat.sqlite') or not os.path.getsize('katersat.sqlite'):
	subprocess.run(['rm', '-f', 'data.sql', 'etag.txt', 'headers.txt'])

sha=''
if os.path.exists('data.sql'):
	if os.path.exists('etag.txt') and os.path.getmtime('etag.txt') > os.path.getmtime('data.sql'):
		sha=Path('etag.txt').read_text(encoding='UTF-8')
	else:
		sha = sha1_file('data.sql')
		Path('etag.txt').write_text(sha)

subprocess.run(['curl', '-D', 'headers.txt', '--no-progress-meter', '--compressed', '--etag-compare', 'etag.txt', '--etag-save', 'etag.txt', 'https://tech.oqaasileriffik.gl/katersat/export-katersat.php', '-o', 'data.sql'])

new=sha
if os.path.getmtime('etag.txt') <= os.path.getmtime('data.sql'):
	new = sha1_file('data.sql')

if sha == new:
	print('Katersat is already up to date')
	sys.exit()


print('Loading new Katersat data...')
subprocess.run(['rm', '-f', 'katersat.sqlite'])
subprocess.run(['sqlite3', 'katersat.sqlite', '-init', 'schema.sql'], input='')
subprocess.run(['sqlite3', 'katersat.sqlite', '-init', 'data.sql'], input='')
Path('etag.txt').write_text(new)
print('Converting longest match...')

con = sqlite3.connect('katersat.sqlite')
db = con.cursor()

db.execute("SELECT lex_id, lex_lexeme, lex_stem FROM kat_lexemes WHERE lex_language = 'kal'")
rows = db.fetchall()
for row in rows:
	id = row[0]
	stems = row[2].strip().split('\n')
	if ' Der/' in row[1]:
		db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [row[1], id])
	for stem in stems:
		if not stem:
			continue
		m = None
		if not (m := re.match(r'^(\+?[^+]*)\+(.*)$', stem)):
			print(f'Warning: Lexeme {id} invalid analysis {stem}')
			continue
		stem = f'"{m[1]}" ' + m[2].replace('+', ' ')
		db.execute("INSERT INTO kat_long_raw VALUES (?, ?)", [stem, id])

con.commit()

print('Katersat updated')
