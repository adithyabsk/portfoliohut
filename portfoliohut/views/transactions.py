from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from portfoliohut.forms import CashForm, CSVForm, StockForm

# def add_data_from_csv(request, file):
#     try:
#         if not file.name.endswith(".csv"):
#             messages.error(request, "File is not a CSV file")
#             return
#
#         decoded_file = file.read().decode("utf-8").splitlines()
#         reader = csv.DictReader(decoded_file)
#         for row in reader:
#             date = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
#             action = "BUY" if float(row["AMOUNT"]) < 0 else "SELL"
#             ticker = row["SYMBOL"]
#             price = row["PRICE"]
#             quantity = row["QUANTITY"]
#
#             new_stock = Stock(
#                 profile=request.user.profile,
#                 action=action,
#                 ticker=ticker,
#                 date_time=date,
#                 price=price,
#                 quantity=quantity,
#             )
#             new_stock.save()
#     except:  # TODO (@rohanbansal) convert from bare except to specific exception catching  # noqa: E722, B001
#         return


@login_required
def transaction_input(request):
    """
    Allows user to input individual Stock/Cash Transactions or upload CSV.
    Validated entries are converted to model objects.
    """
    context = {}

    # Initialize context with blank forms
    profile = request.user.profile
    context["stock_form"] = StockForm(profile=profile)
    context["cash_form"] = CashForm(profile=profile)
    context["csv_form"] = CSVForm()

    # GET request
    if request.method == "GET":
        return render(request, "portfoliohut/add_transaction.html", context)

    # Submitted StockForm with POST request
    if "submit_stock" in request.POST:
        stock_form = StockForm(request.POST, profile=profile)
        context["stock_form"] = stock_form

        if not stock_form.is_valid():
            return render(request, "portfoliohut/add_transaction.html", context)

        context["message"] = "Stock transaction submitted"
        stock_form.save()

    # Submitted CashForm with POST request
    elif "submit_cash" in request.POST:
        cash_form = CashForm(request.POST, profile=profile)
        context["cash_form"] = cash_form

        if not cash_form.is_valid():
            return render(request, "portfoliohut/add_transaction.html", context)

        context["message"] = "Cash transaction submitted"
        cash_form.save()

    # Submitted CSVForm with POST request
    # elif "submit_csv" in request.POST:
    #     csv_form = CSVForm(request.POST, request=request)
    #     context["csv_form"] = csv_form

    #     if not csv_form.is_valid():
    #         return render(request, "portfoliohut/add_transaction.html", context)

    return render(request, "portfoliohut/add_transaction.html", context)


# @login_required
# def transaction_input(request):
#     """
#     Allows user to input individual stock/ CSV stock / Cash transactions
#     Validated entries are converted to model objects.
#     """
#     if request.method == "GET":
#         return render(
#             request,
#             "portfoliohut/add_transaction.html",
#             {"stock_form": StockForm(), "cash_form": CashForm(), "csv_form": CSVForm()},
#         )
#
#     context = {}
#
#     if "submit_stock" in request.POST:
#         stock_form = StockForm(request.POST)
#         context["stock_form"] = stock_form
#
#         # Check if the transaction data is valid
#         if not stock_form.is_valid():
#             context["csv_form"] = CSVForm()
#             context["cash_form"] = CashForm()
#             return render(request, "portfoliohut/add_transaction.html", context)
#
#         action = stock_form.cleaned_data["action"]
#         if action == "sell":
#             profile = request.user.profile
#             ticker = stock_form.cleaned_data["ticker"]
#             date_time = stock_form.cleaned_data["date_time"]
#             quantity = stock_form.cleaned_data["quantity"]
#
#             if not _validate_sell_transaction(profile, ticker, date_time, quantity):
#                 context["csv_form"] = CSVForm()
#                 context["cash_form"] = CashForm()
#                 stock_error_msg = "Invalid quantity: you had fewer than " + str(
#                     quantity
#                 )
#                 stock_error_msg += (
#                     " shares of " + ticker + " on " + str(date_time.date())
#                 )
#                 context["stock_error_msg"] = stock_error_msg
#                 return render(request, "portfoliohut/add_transaction.html", context)
#             else:
#                 price = stock_form.cleaned_data["price"]
#                 cash_equivalent = CashBalance(
#                     profile=request.user.profile, value=(price * quantity)
#                 )
#                 cash_equivalent.save()
#
#         # Create a stock object if it's validate_transaction
#         new_stock = Stock(
#             profile=request.user.profile,
#             action=stock_form.cleaned_data["action"],
#             ticker=stock_form.cleaned_data["ticker"],
#             date_time=stock_form.cleaned_data["date_time"],
#             price=stock_form.cleaned_data["price"],
#             quantity=stock_form.cleaned_data["quantity"],
#         )
#
#         new_stock.save()
#
#     if "submit_csv" in request.POST:
#         csv_form = CSVForm(request.POST, request.FILES)
#         context["csv_form"] = csv_form
#         if not csv_form.is_valid():
#             context["stock_form"] = StockForm()
#             context["cash_form"] = CashForm()
#             return render(request, "portfoliohut/add_transaction.html", context)
#         _add_data_from_csv(request, request.FILES["file"])
#
#     if "submit_cash" in request.POST:
#         cash_form = CashForm(request.POST)
#         context["cash_form"] = cash_form
#
#         if not cash_form.is_valid():
#             context["stock_form"] = StockForm()
#             context["csv_form"] = CSVForm()
#             return render(request, "portfoliohut/add_transaction.html", context)
#
#         action = cash_form.cleaned_data["action"]
#         if action == "withdraw":
#             profile = request.user.profile
#             value = cash_form.cleaned_data["value"]
#
#             if not _validate_withdraw_transaction(profile, value, cash_form.date_time):
#                 context["stock_form"] = StockForm()
#                 context["csv_form"] = CSVForm()
#                 cash_error_msg = "Invalid value: you had fewer than $" + str(value)
#                 cash_error_msg += " in your account on " + str(date_time.date())
#                 context["cash_error_msg"] = cash_error_msg
#                 return render(request, "portfoliohut/add_transaction.html", context)
#
#         new_transaction = CashBalance(
#             profile=request.user.profile,
#             date_time=cash_form.cleaned_data["date_time"],
#             action=cash_form.cleaned_data["action"],
#             value=cash_form.cleaned_data["value"],
#         )
#
#         new_transaction.save()
#
#     return redirect(
#         reverse("portfolio")
#     )  # redirect to portfolio to see addition of new transaction


# @login_required
# def _add_data_from_csv(request, file):
#     try:
#         if not file.name.endswith(".csv"):
#             messages.error(request, "Invalid file type: must be a CSV file")
#             return
#
#         decoded_file = file.read().decode("utf-8").splitlines()
#         reader = csv.DictReader(decoded_file)
#
#         for row in reader:
#             date_time = datetime.strptime(row["DATE"], "%m/%d/%Y").date()
#             action = "buy" if float(row["AMOUNT"]) < 0 else "sell"
#             ticker = row["SYMBOL"]
#             price = row["PRICE"]
#             quantity = row["QUANTITY"]
#             if _validate_csv_element(action, ticker, date_time, price, quantity):
#                 new_stock = Stock(
#                     profile=request.user.profile,
#                     action=action,
#                     ticker=ticker,
#                     date_time=date_time,
#                     price=price,
#                     quantity=quantity,
#                 )
#
#                 new_stock.save()
#
#     except:
#         return
