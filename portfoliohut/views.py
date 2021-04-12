import csv
from collections import defaultdict
from datetime import datetime
from itertools import chain

import yfinance as yf
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.messages import constants as messages
from django.db.models import CharField, F, Value
from django.shortcuts import get_list_or_404, get_object_or_404, redirect, render
from django.urls import reverse

from .forms import CashForm, CSVForm, LoginForm, ProfileForm, RegisterForm, StockForm
from .models import CashBalance, Profile, Stock, StockTable


def index(request):
    if request.user.is_authenticated:
        return redirect(reverse("global-competition"))
    else:
        return redirect(reverse("login"))


def login_action(request):
    if request.method == "GET":
        return render(request, "portfoliohut/login.html", {"login_form": LoginForm()})

    login_form = LoginForm(request.POST)

    # Validates form
    if not login_form.is_valid():
        return render(request, "portfoliohut/login.html", {"login_form": login_form})

    new_user = authenticate(
        username=login_form.cleaned_data["username"],
        password=login_form.cleaned_data["password"],
    )
    login(request, new_user)

    return redirect(reverse("index"))


@login_required
def logout_action(request):
    logout(request)
    return redirect(reverse("login"))


def register_action(request):
    if request.method == "GET":
        return render(
            request, "portfoliohut/register.html", {"register_form": RegisterForm()}
        )

    context = {}

    register_form = RegisterForm(request.POST)
    context["register_form"] = register_form

    if not register_form.is_valid():
        return render(request, "portfoliohut/register.html", context)

    # Create user since the form is valid
    new_user = User.objects.create_user(
        username=register_form.cleaned_data["username"],
        password=register_form.cleaned_data["password"],
        email=register_form.cleaned_data["email"],
        first_name=register_form.cleaned_data["first_name"],
        last_name=register_form.cleaned_data["last_name"],
    )
    new_user.save()

    profile = Profile.objects.create(user=new_user)
    profile.save()

    new_user = authenticate(
        username=register_form.cleaned_data["username"],
        password=register_form.cleaned_data["password"],
    )

    login(request, new_user)
    return redirect(reverse("index"))


@login_required
def global_competition(request):
    context = {}
    profiles = Profile.objects.all()
    context["profiles"] = profiles
    context["page_name"] = "Global Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def friends_competition(request):
    context = {}
    context["page_name"] = "Friends Competition"
    return render(request, "portfoliohut/stream.html", context)


@login_required
def profile_page(request, id_num):
    context = {}

    profile_exists = Profile.objects.filter(id=id_num)
    if not profile_exists:
        return redirect("index")

    context["profile"] = Profile.objects.get(id=id_num)
    return render(request, "portfoliohut/profile.html", context)


@login_required
def update_profile(request):
    context = {}

    if request.method == "GET":
        return redirect("profile-page", id_num=request.user.id)

    profile = Profile.objects.get(user=request.user)

    if request.method == "POST":
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        print(profile_form)

        if not profile_form.is_valid():
            print("Form is not valid")
            context["profile_form"] = profile_form
            context["profile"] = profile
            context["message"] = "Form not valid"
            return render(
                request, "portfoliohut/profile.html", context
            )  # NEED TO FIX THIS

        # profile.profile_picture = profile_form.cleaned_data['profile_picture']
        # profile.content_type = profile_form.cleaned_data['profile_picture'].content_type
        profile.bio = profile_form.cleaned_data["bio"]
        profile.save()

        context["profile_form"] = profile_form
        context["profile"] = profile

        return render(request, "portfoliohut/profile.html", context)  # NEED TO FIX THIS


@login_required
def validate_transaction(stock_data=None, cash_data=None):
    # TODO: check the transaction given some form data, return true or false

    return True


def validate_csv(date, ticker, price, quantity, action):
    # TODO
    return True


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

            if validate_csv(date, ticker, price, quantity, action):
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
def transcation_input(request):
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
        if (not stock_form.is_valid()) or (validate_transaction is False):
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

    return redirect(reverse("add_transaction"))


def get_current_prices(stock_map):
    """
    Lookup the current price using yfinance and then return a dictionary with
    current prices of the stock.
    """
    total = 0
    result = []
    for k, v in stock_map.items():
        if v > 0:
            ticker_details = []
            ticker_details.append(k)
            ticker_price = yf.Ticker(k)
            ticker_details.append(ticker_price.info["regularMarketPreviousClose"])
            stock_value = ticker_price.info["regularMarketPreviousClose"] * v
            total += stock_value
            ticker_details.append(round(stock_value, 2))
            result.append(ticker_details)

        else:
            continue

    return result, total


@login_required
def return_profile(request):
    """
    Call Yahoo finance for all the stocks that are present in the user's portfolio
    Call all the transactions of the current user profile.
    """
    if request.method == "GET":
        stock_map = defaultdict(int)
        # Query the database
        profile = get_object_or_404(Profile, user=request.user)
        all_stock_transactions = get_list_or_404(Stock, profile=profile)
        for transaction in all_stock_transactions:
            if transaction.action.upper() == "BUY":
                stock_map[transaction.ticker] += transaction.quantity
            else:
                stock_map[transaction.ticker] -= transaction.quantity

        all_cash_transactions = get_list_or_404(CashBalance, profile=profile)
        cash_balance = 0
        for transaction in all_cash_transactions:
            if transaction.action.upper() == "DEPOSIT":
                cash_balance += transaction.value
            else:
                cash_balance -= transaction.value

        stocks, total = get_current_prices(stock_map)

        # Write logic for pagination and transactions table
        stock_transactions_table = Stock.objects.filter(profile=profile).order_by(
            "date_time"
        )
        cash_transactions_table = CashBalance.objects.filter(profile=profile).order_by(
            "date_time"
        )

        cash_transactions_table = cash_transactions_table.annotate(
            price=F("value"), ticker=Value("--Cash--", output_field=CharField())
        ).values("price", "action", "date_time", "ticker")

        cash_transactions_table = cash_transactions_table.filter(
            profile=profile
        ).order_by("date_time")

        records = chain(stock_transactions_table, cash_transactions_table)

        table = StockTable(records)

        table.paginate(page=request.GET.get("page", 1), per_page=25)

        return render(
            request,
            "portfoliohut/portfolio_profile.html",
            {
                "profile_table": stocks,
                "total": "${:,.2f}".format(total),
                "table": table,
                "cash": "${:,.2f}".format(cash_balance),
            },
        )
