import csv
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.messages import constants as messages
from django.shortcuts import redirect, render
from django.urls import reverse

from portfoliohut.forms.forms import CashForm, CSVForm, StockForm
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
            return render(request, "portfoliohut/add_transaction.html", context)

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

    elif "submit_csv" in request.POST:
        csv_form = CSVForm(request.POST, request.FILES)
        context["csv_form"] = csv_form
        if csv_form.is_valid():
            add_data_from_csv(request, request.FILES["file"])

    elif "submit_cash" in request.POST:
        cash_form = CashForm(request.POST)
        context["cash_form"] = cash_form

        if not cash_form.is_valid():
            return render(request, "portfoliohut/add_transaction.html", context)

        new_transaction = CashBalance(
            profile=request.user.profile,
            date_time=cash_form.cleaned_data["date_time"],
            action=cash_form.cleaned_data["action"],
            value=cash_form.cleaned_data["value"],
        )

        new_transaction.save()

    return redirect(reverse("add-transaction"))
