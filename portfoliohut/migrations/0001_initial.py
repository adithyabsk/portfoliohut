# Generated by Django 3.1.7 on 2021-04-30 21:15

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EquityInfo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ticker", models.CharField(max_length=20, unique=True)),
                ("logo_url", models.URLField()),
                ("address1", models.CharField(max_length=255)),
                ("city", models.CharField(max_length=255)),
                ("country", models.CharField(max_length=255)),
                ("zipcode", models.CharField(max_length=255)),
                ("industry", models.CharField(max_length=255)),
                ("sector", models.CharField(max_length=255)),
                ("summary", models.TextField()),
                ("name", models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "bio",
                    models.CharField(
                        default="Hello! I'm new to Portfolio Hut.", max_length=240
                    ),
                ),
                (
                    "profile_type",
                    models.CharField(
                        choices=[("public", "PUBLIC"), ("private", "PRIVATE")],
                        default="public",
                        max_length=7,
                    ),
                ),
                (
                    "friend_requests",
                    models.ManyToManyField(
                        blank=True,
                        related_name="friend_requests_list",
                        to="portfoliohut.Profile",
                    ),
                ),
                (
                    "friends",
                    models.ManyToManyField(
                        blank=True,
                        related_name="friends_list",
                        to="portfoliohut.Profile",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PortfolioReturn",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_time", models.DateTimeField()),
                ("floating_return", models.FloatField()),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="portfoliohut.profile",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="PortfolioItem",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("EQ", "Equity"),
                            ("EC", "External Cash"),
                            ("IC", "Internal Cash"),
                        ],
                        max_length=4,
                    ),
                ),
                ("ticker", models.CharField(max_length=20)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("quantity", models.IntegerField()),
                ("price", models.DecimalField(decimal_places=2, max_digits=100)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="portfoliohut.profile",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HistoricalEquity",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("EQ", "Equity"),
                            ("EC", "External Cash"),
                            ("IC", "Internal Cash"),
                        ],
                        max_length=4,
                    ),
                ),
                ("ticker", models.CharField(max_length=20)),
                ("date", models.DateField()),
                ("open", models.DecimalField(decimal_places=2, max_digits=100)),
                ("high", models.DecimalField(decimal_places=2, max_digits=100)),
                ("low", models.DecimalField(decimal_places=2, max_digits=100)),
                ("close", models.DecimalField(decimal_places=2, max_digits=100)),
                ("volume", models.PositiveBigIntegerField()),
                ("dividends", models.DecimalField(decimal_places=2, max_digits=100)),
                ("stock_splits", models.IntegerField()),
            ],
            options={
                "ordering": ("date",),
                "unique_together": {("ticker", "date")},
            },
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("EQ", "Equity"),
                            ("EC", "External Cash"),
                            ("IC", "Internal Cash"),
                        ],
                        max_length=4,
                    ),
                ),
                ("ticker", models.CharField(max_length=20)),
                ("date_time", models.DateTimeField()),
                ("quantity", models.IntegerField()),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=100,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0.01"))
                        ],
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="portfoliohut.profile",
                    ),
                ),
            ],
            options={
                "unique_together": {("profile", "ticker", "date_time")},
            },
        ),
    ]
