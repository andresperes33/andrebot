from django.db import migrations
import re


def corrigir_categorias(apps, schema_editor):
    """Corrige classificacao de produtos分类ados errado pelas migrations anteriores."""
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.all().iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        nova_categoria = None

        if re.search(r'\bgabinete\b', titulo) or re.search(r'\bgabinete\b', texto):
            nova_categoria = 'gabinete'
        elif re.search(r'\bpc\s*gamer\b|\bcomputador\s*gamer\b', titulo):
            nova_categoria = 'pc_gamer'
        elif re.search(r'\broteador\b|\brouter\b', titulo) or re.search(r'\broteador\b|\brouter\b', texto):
            nova_categoria = 'roteador'
        elif re.search(r'\bmesa\b', titulo) and 'cupom' not in titulo:
            nova_categoria = 'mesa'
        elif re.search(r'\b(tv|smart\s*tv|televis)\b', titulo):
            nova_categoria = 'tv'
        elif re.search(r'\b(qled|oled|miniled)\b', titulo) and not re.search(r'\bmonitor\b', titulo):
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
