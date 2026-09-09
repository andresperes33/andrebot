from django.db import migrations
import re


def reclassificar_roteador(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.exclude(categoria='roteador').iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        if re.search(r'\b(?:roteador|router)\b', titulo) or \
           re.search(r'\b(?:roteador|router)\b', texto):
            p.categoria = 'roteador'
            p.save(update_fields=['categoria'])
            alteradas += 1
    if alteradas:
        print(f'Reclassificadas {alteradas} promocoes para roteador.')


def reverter(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    Promo.objects.filter(categoria='roteador').update(categoria='outros')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0135_adicionar_pc_gamer'),
    ]

    operations = [
        migrations.RunPython(reclassificar_roteador, reverter),
    ]
