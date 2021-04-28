from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from portfoliohut.forms import CashForm, CSVForm, StockForm


@login_required
def transaction_input(request):
    """
    Allows user to input individual Stock/Cash Transactions or upload CSV.
    Validated entries are converted to model objects.
    """
    context = {}

    # Initialize context with blank forms
    profile = request.user.profile
    context["stock_form"] = StockForm()
    context["cash_form"] = CashForm()
    context["csv_form"] = CSVForm()

    # GET request
    if request.method == "GET":
        return render(request, "portfoliohut/add_transaction.html", context)

    # Submitted StockForm with POST request
    if "submit_stock" in request.POST:
        stock_form = StockForm(request.POST, profile=profile)

        if not stock_form.is_valid():
            return render(
                request,
                "portfoliohut/add_transaction.html",
                {**context, "stock_form": stock_form},
            )

        stock_form.save()
        ticker = stock_form.cleaned_data.get("ticker")
        messages.success(request, f"{ticker} transaction successfully saved")

    # Submitted CashForm with POST request
    elif "submit_cash" in request.POST:
        cash_form = CashForm(request.POST, profile=profile)

        if not cash_form.is_valid():
            return render(
                request,
                "portfoliohut/add_transaction.html",
                {**context, "cash_form": cash_form},
            )

        cash_form.save()
        messages.success(request, "Cash transaction successfully saved")

    # Submitted CSVForm with POST request
    elif "submit_csv" in request.POST:
        # Note: The clean function actually saves data if it is successful, there is no save method
        #       on this class because we need partial saves after each transaction to check if the
        #       subsequent transactions are valid. That's why it doesn't make sense to just cache
        #       the forms and save them all at once.
        csv_form = CSVForm(request.POST, request.FILES, profile=profile)

        if not csv_form.is_valid():
            return render(
                request,
                "portfoliohut/add_transaction.html",
                {**context, "csv_form": csv_form},
            )

        messages.success(request, "Successfully saved CSV transactions")

    return render(request, "portfoliohut/add_transaction.html", context)
