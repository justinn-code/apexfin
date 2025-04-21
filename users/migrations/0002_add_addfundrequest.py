from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),  # Make sure this matches your last migration
    ]

    operations = [
        migrations.CreateModel(
            name='AddFundRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_method', models.CharField(max_length=50)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('gift_card_code', models.CharField(max_length=255, blank=True, null=True)),
                ('gift_card_image', models.ImageField(upload_to='gift_cards/', blank=True, null=True)),
                ('crypto_wallet_address', models.CharField(max_length=255, blank=True, null=True)),
                ('is_verified', models.BooleanField(default=False)),
                ('status', models.CharField(max_length=20, default='pending')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
