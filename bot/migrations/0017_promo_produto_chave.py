from django.db import migrations, models
from bot.services import _chave_produto


def backfill_produto_chave(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    for promo in Promo.objects.all().iterator():
        chave = _chave_produto(promo.texto_original or promo.titulo)
        if chave and chave != promo.produto_chave:
            promo.produto_chave = chave
            promo.save(update_fields=['produto_chave'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0016_promo_kit'),
    ]

    operations = [
        migrations.AddField(
            model_name='promo',
            name='produto_chave',
            field=models.CharField(blank=True, db_index=True, max_length=1000),
        ),
        migrations.RunPython(backfill_produto_chave, noop),
    ]
