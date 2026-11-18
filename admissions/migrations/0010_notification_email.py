import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admissions', '0009_seed_housing_and_profile_documents'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidatecontact',
            name='notification_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.CreateModel(
            name='EmailDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient', models.EmailField(max_length=254)),
                ('state', models.CharField(choices=[('pending', 'Oczekuje'), ('sent', 'Wysłano'), ('cancelled', 'Anulowano'), ('failed', 'Wysyłka nie powiodła się')], default='pending', max_length=10)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('available_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notification', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='admissions.notification')),
            ],
            options={
                'indexes': [models.Index(fields=['state', 'available_at'], name='email_delivery_ready_idx')],
            },
        ),
    ]
