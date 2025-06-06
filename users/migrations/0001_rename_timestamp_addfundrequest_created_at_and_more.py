# Generated by Django 4.2 on 2025-04-21 23:24

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import users.models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "000X_add_bank_details_to_addfundrequest"),
    ]

    operations = [
        migrations.RenameField(
            model_name="addfundrequest",
            old_name="timestamp",
            new_name="created_at",
        ),
        migrations.AddField(
            model_name="transaction",
            name="balance_after",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
        migrations.AlterField(
            model_name="addfundrequest",
            name="amount",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name="addfundrequest",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("gift_card", "Gift Card"),
                    ("bank_transfer", "Bank Transfer"),
                    ("crypto", "Crypto (USDT)"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="narration",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="recipient_account",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="recipient_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="sender_account",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="sender_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="status",
            field=models.CharField(
                choices=[
                    ("completed", "Completed"),
                    ("pending", "Pending"),
                    ("failed", "Failed"),
                ],
                default="completed",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="GiftCard",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        max_length=255,
                        unique=True,
                        validators=[users.models.validate_gift_card_code],
                    ),
                ),
                ("value", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="users.userprofile",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FiatConversionRequest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "destination",
                    models.TextField(help_text="Bank account or crypto wallet info"),
                ),
                ("narration", models.TextField(blank=True, null=True)),
                (
                    "gas_fee_method",
                    models.CharField(
                        choices=[("usdt", "USDT"), ("gift_card", "Gift Card")],
                        max_length=20,
                    ),
                ),
                (
                    "usdt_transaction_hash",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "gift_card_code",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
