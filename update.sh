#!/bin/bash
set -e
cd $(dirname "$0")

SHA=""
if [[ -s data.sql ]]; then
	SHA=$(cat data.sql | shasum)
	echo "$SHA" | awk '{print $1}' > etag.txt
fi

curl -D headers.txt --no-progress-meter --compressed --etag-compare etag.txt --etag-save etag.txt https://tech.oqaasileriffik.gl/katersat/export-katersat.php -o data.sql

NEW=$(cat data.sql | shasum)
if [[ "$SHA" != "$NEW" ]]; then
	rm -fv katersat.sqlite
	cat schema.sql | sqlite3 katersat.sqlite
	cat data.sql | sqlite3 katersat.sqlite
fi
