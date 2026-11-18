from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('admissions', '0002_postgresql_features')]
    operations = [migrations.SeparateDatabaseAndState(state_operations=[
        migrations.CreateModel(name='OfferStats', fields=[
            ('offer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='stats', serialize=False, to='admissions.offer')),
            ('applications', models.BigIntegerField(default=0)),
            ('verified', models.BigIntegerField(default=0)),
            ('confirmed', models.BigIntegerField(default=0)),
        ], options={'db_table': 'pk_offer_stats'})
    ])]
