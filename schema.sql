PRAGMA case_sensitive_like = ON;
PRAGMA foreign_keys = OFF;
PRAGMA journal_mode = MEMORY;
PRAGMA locking_mode = EXCLUSIVE;
PRAGMA synchronous = OFF;
PRAGMA threads = 4;
PRAGMA trusted_schema = OFF;
PRAGMA page_size = 65536;
VACUUM;
PRAGMA locking_mode = NORMAL;


CREATE TABLE kat_genders (
	gen_code TEXT NOT NULL,
	gen_eng TEXT DEFAULT NULL,
	gen_dan TEXT DEFAULT NULL,
	gen_kal TEXT DEFAULT NULL,

	PRIMARY KEY (gen_code)
);


CREATE TABLE kat_languages (
	-- Holds valid ISO 639-3 language codes
	lang_code TEXT NOT NULL,
	lang_eng TEXT DEFAULT NULL, -- English
	lang_dan TEXT DEFAULT NULL, -- Danish
	lang_kal TEXT DEFAULT NULL, -- Greenlandic
	lang_deu TEXT DEFAULT NULL, -- German
	lang_code2 TEXT DEFAULT NULL, -- Old 2 letter code, if any

	PRIMARY KEY (lang_code)
);


CREATE TABLE kat_registers (
	reg_code TEXT NOT NULL,
	reg_eng TEXT NOT NULL,
	reg_dan TEXT DEFAULT NULL,
	reg_kal TEXT DEFAULT NULL,

	PRIMARY KEY (reg_code),
	UNIQUE (reg_eng)
);


CREATE TABLE kat_semclasses (
	sem_code TEXT NOT NULL,
	sem_eng TEXT DEFAULT NULL, -- English
	sem_dan TEXT DEFAULT NULL, -- Danish
	sem_kal TEXT DEFAULT NULL, -- Greenlandic
	sem_misc TEXT NOT NULL DEFAULT '',

	PRIMARY KEY (sem_code)
);


CREATE TABLE kat_valence (
	val_id INTEGER NOT NULL,
	val_code TEXT NOT NULL,
	-- val_langs set('dan','eng','kal') NOT NULL DEFAULT 'dan,eng',
	val_langs INTEGER NOT NULL DEFAULT 3,
	val_eng TEXT DEFAULT NULL,
	val_dan TEXT DEFAULT NULL,
	val_kal TEXT DEFAULT NULL,

	PRIMARY KEY (val_id AUTOINCREMENT),
	UNIQUE (val_code)
);


CREATE TABLE kat_wordclasses (
	wc_class TEXT NOT NULL,
	wc_eng TEXT DEFAULT NULL, -- English
	wc_dan TEXT DEFAULT NULL, -- Danish
	wc_kal TEXT DEFAULT NULL, -- Greenlandic

	PRIMARY KEY (wc_class)
);


CREATE TABLE kat_lexemes (
	lex_id INTEGER NOT NULL,
	lex_lexeme TEXT NOT NULL, -- lexeme
	lex_wordclass TEXT NOT NULL, -- word class
	lex_valence INTEGER NOT NULL DEFAULT 0,
	lex_language TEXT NOT NULL,
	lex_stem TEXT DEFAULT NULL, -- word stem
	lex_semclass TEXT NOT NULL DEFAULT 'UNK', -- semantic class
	lex_sem2 TEXT NOT NULL DEFAULT 'UNK',
	lex_register TEXT NOT NULL DEFAULT 'nnn',
	lex_gender TEXT DEFAULT NULL,
	lex_tiebreak TEXT NOT NULL DEFAULT '',
	lex_info TEXT DEFAULT NULL,
	lex_verbframe TEXT DEFAULT NULL,
	lex_oldspelling TEXT DEFAULT NULL, -- old spelling
	lex_definition TEXT NOT NULL DEFAULT '', -- definition
	lex_misc TEXT DEFAULT NULL, -- misc
	lex_ctime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	lex_stamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
	wp_uid INTEGER DEFAULT NULL,

	PRIMARY KEY (lex_id AUTOINCREMENT),
	UNIQUE (lex_lexeme,lex_language,lex_wordclass,lex_valence,lex_semclass,lex_sem2,lex_register,lex_tiebreak),

	FOREIGN KEY (lex_sem2) REFERENCES kat_semclasses (sem_code) ON UPDATE CASCADE,
	FOREIGN KEY (lex_valence) REFERENCES kat_valence (val_id) ON UPDATE CASCADE,
	FOREIGN KEY (lex_wordclass) REFERENCES kat_wordclasses (wc_class) ON UPDATE CASCADE,
	FOREIGN KEY (lex_language) REFERENCES kat_languages (lang_code) ON UPDATE CASCADE,
	FOREIGN KEY (lex_semclass) REFERENCES kat_semclasses (sem_code) ON UPDATE CASCADE,
	FOREIGN KEY (lex_register) REFERENCES kat_registers (reg_code) ON UPDATE CASCADE,
	FOREIGN KEY (lex_gender) REFERENCES kat_genders (gen_code) ON UPDATE CASCADE
);

CREATE INDEX kat_lexemes_lex_language ON kat_lexemes (lex_language);
CREATE INDEX kat_lexemes_lex_wordclass ON kat_lexemes (lex_wordclass);
CREATE INDEX kat_lexemes_lex_semclass ON kat_lexemes (lex_semclass);
CREATE INDEX kat_lexemes_lex_gender ON kat_lexemes (lex_gender);
CREATE INDEX kat_lexemes_lex_register ON kat_lexemes (lex_register);
CREATE INDEX kat_lexemes_lex_sem2 ON kat_lexemes (lex_sem2);
CREATE INDEX kat_lexemes_lex_valence ON kat_lexemes (lex_valence);


CREATE TABLE kat_lexeme_attrs (
	lex_id INTEGER NOT NULL,
	-- lex_attrs set('hidden','root','artificial','archaic','alternate','plural','mass','abbreviation','acronym','dermorph','enclitic','strict-stem','qual-plus','qual-minus','quant-plus','quant-minus') NOT NULL,
	let_attrs INTEGER NOT NULL,
	-- lex_sandhi enum('tru','add','gem','rec','rep','dep') NOT NULL,
	lex_sandhi INTEGER NOT NULL,

	PRIMARY KEY (lex_id),

	FOREIGN KEY (lex_id) REFERENCES kat_lexemes (lex_id) ON DELETE CASCADE ON UPDATE CASCADE
);


CREATE TABLE kat_long_raw (
	fst_ana TEXT NOT NULL,
	lex_id INTEGER NOT NULL,

	FOREIGN KEY (lex_id) REFERENCES kat_lexemes (lex_id) ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX kat_long_raw_lex_id ON kat_long_raw (lex_id);
CREATE INDEX kat_long_raw_fst_ana ON kat_long_raw (substr(fst_ana,1,16));


CREATE TABLE glue_lexeme_synonyms (
	lex_id INTEGER NOT NULL,
	lex_syn INTEGER NOT NULL,
	syn_order INTEGER NOT NULL DEFAULT 255,
	syn_rule TEXT DEFAULT NULL,
	gsyn_stamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

	PRIMARY KEY (lex_id,lex_syn),
	UNIQUE (lex_syn,lex_id),

	FOREIGN KEY (lex_id) REFERENCES kat_lexemes (lex_id) ON DELETE CASCADE ON UPDATE CASCADE,
	FOREIGN KEY (lex_syn) REFERENCES kat_lexemes (lex_id) ON DELETE CASCADE ON UPDATE CASCADE
);
