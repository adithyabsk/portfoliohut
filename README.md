# Portfolio Hut

## Overview
We plan to build a stock portfolio performance web application. Our app will
allow users to compare their portfolio (e.g. Robinhood) performance against a
benchmark (e.g. SPY). This will provide individual investors with the tools to
evaluate their investment strategy.

## Installation / Setup

Tested on Python 3.8.0

Initial setup steps

```shell
$ brew install pre-commit
$ python -m venv venv
$ source ./venv/bin/activate
(venv) $ pip install -r requirements.txt
(venv) $ pip install -r requirements-dev.txt
(venv) $ pre-commit install # runs before each commit you make
(venv) $ cp env.sample .env # Update these values if necessary
```

Provision database

```shell
(venv) $ ./reset_db.sh
```

Running the server

```shell
(venv) $ python manage.py runserver
```

Running pre-commit on all your files. It already automatically runs on each
commit.

```shell
(venv) $ pre-commit run -a
```

Note: If you are running in `DEBUG=False` mode, you will need to run the
following commands. You will need to re-run this command each time you modify a
template file.

```shell
(venv) $ python manage.py collectstatic
```
