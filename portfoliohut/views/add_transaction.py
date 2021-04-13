import csv
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from django.contrib.auth.decorators import login_required
from django.contrib.messages import constants as messages
from django.forms import forms
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms import CashForm, CSVForm, StockForm
from portfoliohut.models import CashBalance, Stock


def add_data_from_csv(request, file):
    try:
        if not file.name.endswith(".csv"):
            messages.error(request, "File is not a CSV file")
            return

        decoded_file = file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)
        for row in reader:
            date = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
            action = "BUY" if float(row["AMOUNT"]) < 0 else "SELL"
            ticker = row["SYMBOL"]
            price = row["PRICE"]
            quantity = row["QUANTITY"]

            new_stock = Stock(
                profile=request.user.profile,
                action=action,
                ticker=ticker,
                date_time=date,
                price=price,
                quantity=quantity,
            )
            new_stock.save()
    except:  # TODO (@rohanbansal) convert from bare except to specific exception catching  # noqa: E722, B001
        return


@login_required
def transaction_input(request):
    """
    Allows user to input individual stock/ CSV stock / Cash transactions
    Validated entries are converted to model objects.
    """
    if request.method == "GET":
        return render(
            request,
            "portfoliohut/add_transaction.html",
            {"stock_form": StockForm(), "cash_form": CashForm(), "csv_form": CSVForm()},
        )

    context = {}

    if "submit_stock" in request.POST:
        stock_form = StockForm(request.POST)
        context["stock_form"] = stock_form

        # Check if the transaction data is valid
        if not stock_form.is_valid():
            context["csv_form"] = CSVForm()
            context["cash_form"] = CashForm()
            return render(request, "portfoliohut/add_transaction.html", context)

        action = stock_form.cleaned_data["action"]
        if action == "sell":
            profile = request.user.profile
            ticker = stock_form.cleaned_data["ticker"]
            date_time = stock_form.cleaned_data["date_time"]
            quantity = stock_form.cleaned_data["quantity"]

            if not _validate_sell_transaction(profile, ticker, date_time, quantity):
                context["csv_form"] = CSVForm()
                context["cash_form"] = CashForm()
                stock_error_msg = "Invalid quantity: you had fewer than " + str(
                    quantity
                )
                stock_error_msg += (
                    " shares of " + ticker + " on " + str(date_time.date())
                )
                context["stock_error_msg"] = stock_error_msg
                return render(request, "portfoliohut/add_transaction.html", context)
            else:
                price = stock_form.cleaned_data["price"]
                cash_equivalent = CashBalance(
                    profile=request.user.profile, value=(price * quantity)
                )
                cash_equivalent.save()

        # Create a stock object if it's validate_transaction
        new_stock = Stock(
            profile=request.user.profile,
            action=stock_form.cleaned_data["action"],
            ticker=stock_form.cleaned_data["ticker"],
            date_time=stock_form.cleaned_data["date_time"],
            price=stock_form.cleaned_data["price"],
            quantity=stock_form.cleaned_data["quantity"],
        )

        new_stock.save()

    if "submit_csv" in request.POST:
        csv_form = CSVForm(request.POST, request.FILES)
        context["csv_form"] = csv_form
        if not csv_form.is_valid():
            context["stock_form"] = StockForm()
            context["cash_form"] = CashForm()
            return render(request, "portfoliohut/add_transaction.html", context)
        _add_data_from_csv(request, request.FILES["file"])

    if "submit_cash" in request.POST:
        cash_form = CashForm(request.POST)
        context["cash_form"] = cash_form

        if not cash_form.is_valid():
            context["stock_form"] = StockForm()
            context["csv_form"] = CSVForm()
            return render(request, "portfoliohut/add_transaction.html", context)

        action = cash_form.cleaned_data["action"]
        if action == "withdraw":
            profile = request.user.profile
            value = cash_form.cleaned_data["value"]

            if not _validate_withdraw_transaction(profile, value, cash_form.date_time):
                context["stock_form"] = StockForm()
                context["csv_form"] = CSVForm()
                cash_error_msg = "Invalid value: you had fewer than $" + str(value)
                cash_error_msg += " in your account on " + str(date_time.date())
                context["cash_error_msg"] = cash_error_msg
                return render(request, "portfoliohut/add_transaction.html", context)

        new_transaction = CashBalance(
            profile=request.user.profile,
            date_time=cash_form.cleaned_data["date_time"],
            action=cash_form.cleaned_data["action"],
            value=cash_form.cleaned_data["value"],
        )

        new_transaction.save()

    return redirect(
        reverse("returns-profile")
    )  # redirect to portfolio to see addition of new transaction


# Internal Functions
@login_required
def _validate_sell_transaction(profile, ticker, date_time, quantity):
    all_transactions = Stock.objects.filter(profile=profile, ticker=ticker)

    # Find how many shares the user held of the given stock at the time of sale
    current_quantity = 0
    for i in range(len(all_transactions)):
        if all_transactions[i].date_time < date_time:
            transaction_quantity = all_transactions[i].quantity
            if all_transactions[i].action == "buy":
                current_quantity += transaction_quantity
            else:
                current_quantity -= transaction_quantity

    # Validate sale
    if current_quantity < quantity:
        return False
    return True


@login_required
def _validate_withdraw_transaction(profile, value, date_time):
    all_transactions = CashBalance.objects.filter(profile=profile)

    # Find how many much money user currently has in their account
    current_cash_amount = 0
    for i in range(len(all_transactions)):
        if all_transactions[i].date_time < date_time:
            transaction_value = all_transactions[i].value
            if all_transactions[i].action == "deposit":
                current_cash_amount += transaction_value
            else:
                current_cash_amount -= transaction_value

    # Validate withdraw
    if current_cash_amount < value:
        return False
    return True


@login_required
def _add_data_from_csv(request, file):
    try:
        if not file.name.endswith(".csv"):
            messages.error(request, "Invalid file type: must be a CSV file")
            return

        decoded_file = file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(decoded_file)

        for row in reader:
            date_time = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
            action = "buy" if float(row["AMOUNT"]) < 0 else "sell"
            ticker = row["SYMBOL"]
            price = row["PRICE"]
            quantity = row["QUANTITY"]
            if _validate_csv_element(action, ticker, date_time, price, quantity):
                new_stock = Stock(
                    profile=request.user.profile,
                    action=action,
                    ticker=ticker,
                    date_time=date_time,
                    price=price,
                    quantity=quantity,
                )

                new_stock.save()

    except:
        return


# Validate csv functions
@login_required
def _validate_csv_element(action, ticker, date_time, price, quantity):
    valid_action = _clean_ticker(action)
    if not valid_action:
        return False

    valid_ticker = _clean_ticker(ticker)
    if not valid_ticker:
        return False

    valid_date_time = _clean_date_time(date_time)
    if not valid_date_time:
        return False

    valid_price = _clean_price(action, date_time, price)
    if not valid_price:
        return False

    valid_quantity = _clean_quantity(quantity)
    if not valid_quantity:
        return False

    if action == "sell":
        pass
        # TODO: (@eab148) there is a bug here where profile exists, we need to figure out how to
        # make this function work
        # return _validate_sell_transaction(profile, ticker, date_time, quantity)
    return True


def _clean_ticker(ticker):
    yf_ticker = yf.Ticker(ticker)
    df = yf_ticker.history(period="1d")
    if df.empty:
        raise forms.ValidationError("Invalid ticker: must be a ticker in the NYSE")
    return ticker


def _clean_quantity(quantity):
    if quantity < 0:
        raise forms.ValidationError("Invalid stock quantity: must be positive")
    return quantity


def _clean_action(action):
    if (not action == "buy") and (not action == "sell"):
        return False
    return True


def _clean_price(ticker, date_time, price):
    # Get ticker price on given date
    yf_ticker = yf.Ticker(ticker)
    df = None
    if date_time.date() == date.today():
        df = yf_ticker.history(period="1d")
    else:
        df = yf_ticker.history(
            start=date_time.date(), end=(date_time.date() + timedelta(1)), interval="1d"
        )

    # Compare it to the given price
    if df.empty:
        return False
    if (price < df["Low"].iloc[0]) or (df["High"].iloc[0] < price):
        return False
    return True


def _clean_date_time(date_time):
    if date_time > timezone.now():
        raise forms.ValidationError("Invalid date/time: cannot be in the future")

    return date_time
