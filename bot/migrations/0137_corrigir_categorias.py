from django.db import migrations
import re


def corrigir_categorias(apps, schema_editor):
    """Corrige classificacao de produtos que foram分类ados errado."""
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.all().iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        nova_categoria = None

        # Regra principal: se o titulo contem a palavra-chave da categoria,
        # classifica corretamente, independente da categoria atual.
        if re.search(r'\bgabinete\b', titulo) or re.search(r'\bgabinete\b', texto):
            nova_categoria = 'gabinete'
        elif re.search(r'\bpc\s*gamer\b|\bcomputador\s*gamer\b', titulo):
            nova_categoria = 'pc_gamer'
        elif re.search(r'\broteador\b|\brouter\b', titulo) or re.search(r'\broteador\b|\brouter\b', texto):
            nova_categoria = 'roteador'
        elif re.search(r'\bmesa\b', titulo) and 'cupom' not in titulo:
            nova_categoria = 'mesa'
        elif re.search(r'\btv\b|\bsmart\s*tv\b|\btelevis', titulo):
            nova_categoria = 'tv'
        elif re.search(r'\bqled\b|\boled\b|\bminiled\b', titulo) and not re.search(r'\bmonitor\b', titulo):
            nova_categoria = 'tv'

        if nova_categoria and nova_categoria != p.categoria:
            p.categoria = nova_categoria
            p.save(update_fields=['categoria'])
            alteradas += 1

    if alteradas:
        print(f'Corrigidas {alteradas} promocoes.')


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0136_reclassificar_roteador'),
    ]

    operations = [
        migrations.RunPython(corrigir_categorias, reverter),
    ]
