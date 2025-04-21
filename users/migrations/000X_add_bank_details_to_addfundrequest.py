from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        # Ensure you reference the correct previous migration
        ('users', '0002_add_addfundrequest'),  # Adjust if necessary
    ]

    operations = [
        migrations.AddField(
            model_name='addfundrequest',
            name='bank_details',
            field=models.TextField(blank=True, null=True),
        ),
    ]
