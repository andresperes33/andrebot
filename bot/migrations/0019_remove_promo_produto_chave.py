from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0018_reclassificar_promos_cupom'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='promo',
            name='produto_chave',
        ),
    ]