from django.db import migrations


def add_tisa(apps, schema_editor):
    Barangay = apps.get_model('core', 'Barangay')
    Barangay.objects.get_or_create(
        name='Tisa',
        city_municipality='Cebu City',
        defaults={'province': 'Cebu'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_tisa, migrations.RunPython.noop),
    ]
