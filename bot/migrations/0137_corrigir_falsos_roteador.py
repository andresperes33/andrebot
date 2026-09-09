from django.db import migrations
import re


def corrigir_falsos_roteador(apps, schema_editor):
    """Reclassifica produtos marcados como 'roteador' que NÃO contêm
    'roteador' ou 'router' no título/texto (falsos positivos da migration
    anterior que casava 'wifi', 'mesh', etc.)."""
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.filter(categoria='roteador').iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        if not re.search(r'\b(?:roteador|router)\b', titulo) and \
           not re.search(r'\b(?:roteador|router)\b', texto):
            p.categoria = 'outros'
            p.save(update_fields=['categoria'])
            alteradas += 1
    if alteradas:
        print(f'Revertidos {alteradas} falsos roteadores para outros.')


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0136_reclassificar_roteador'),
    ]

    operations = [
        migrations.RunPython(corrigir_falsos_roteador, reverter),
    ]
