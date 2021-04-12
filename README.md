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
$ python -m venv venv
$ source ./venv/bin/activate
(venv) $ python manage.py migrate
(venv) $ pip install -r requirements.txt
```

Running the server

```shell
(venv) $ python manage.py runserver
```
