from django.db import migrations
import re


def corrigir_categorias(apps, schema_editor):
    """Corrige falsos positivos e classifica corretamente produtos que foram
    classificados errado pelas migrations anteriores."""
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.all().iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        nova_categoria = None

        # Se está como 'roteador' mas não tem 'roteador'/'router' no titulo/texto
        if p.categoria == 'roteador':
            if not re.search(r'\b(?:roteador|router)\b', titulo) and \
               not re.search(r'\b(?:roteador|router)\b', texto):
                # Tentar recategorizar corretamente
                if re.search(r'\bgabinete\b', titulo) or re.search(r'\bgabinete\b', texto):
                    nova_categoria = 'gabinete'
                elif re.search(r'\bpc\s*gamer\b|\bcomputador\s*gamer\b', titulo):
                    nova_categoria = 'pc_gamer'
                else:
                    nova_categoria = 'outros'

        # Se está como 'outros' mas deveria ter outra categoria
        if p.categoria == 'outros' or nova_categoria == 'outros':
            if re.search(r'\bgabinete\b', titulo) or re.search(r'\bgabinete\b', texto):
                nova_categoria = 'gabinete'
            elif re.search(r'\bpc\s*gamer\b|\bcomputador\s*gamer\b', titulo):
                nova_categoria = 'pc_gamer'
            elif re.search(r'\bmesa\b', titulo) and 'cupom' not in titulo:
                nova_categoria = 'mesa'

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
