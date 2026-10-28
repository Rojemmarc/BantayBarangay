from django.db import migrations


def create_categories(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    for name in ('Infrastructure', 'Safety', 'Sanitation', 'Flooding', 'Noise', 'Emergency'):
        Category.objects.get_or_create(name=name, defaults={'is_emergency': name == 'Emergency'})


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_add_tisa_barangay'),
    ]

    operations = [
        migrations.RunPython(create_categories, migrations.RunPython.noop),
    ]
