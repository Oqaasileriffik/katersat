#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path
import sqlite3

dir = os.path.dirname(__file__)
os.chdir(dir)

con = sqlite3.connect('katersat.sqlite', isolation_level=None)
db = con.cursor()

tbls = {
	'kat_genders': 'gen_code',
	'kat_languages': 'lang_code',
	'kat_domains': 'dom_id',
	'kat_semclasses': 'sem_code',
	'kat_valence': 'val_id',
	'kat_wordclasses': 'wc_class',
}

for t, i in tbls.items():
	print(t)
	fname = f'data/{t}.sql'
	os.makedirs('data', exist_ok=True)
	subprocess.run(['rm', '-f', fname])
	p = subprocess.run(['sqlite3', 'katersat.sqlite', '.mode insert TBL', f'SELECT * FROM {t} ORDER BY {i} ASC;'], capture_output=True, encoding='UTF-8')
	sql = p.stdout
	sql = sql.replace(';\nINSERT INTO TBL VALUES', ',\n')
	sql = sql.replace('INSERT INTO TBL VALUES', f'INSERT INTO {t} VALUES\n')
	sql = sql.replace(';\n', '\n;\n')
	Path(fname).write_text(sql, encoding='UTF-8')
