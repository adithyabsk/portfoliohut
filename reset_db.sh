#!/bin/zsh
# Exit on first error
set -e

#rm db.sqlite3 || :
dropdb portfoliohut || :
createdb portfoliohut
python manage.py migrate
python manage.py make_sample_data
