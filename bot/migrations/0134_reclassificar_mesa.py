from django.db import migrations


def reclassificar_mesa(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    qs = Promo.objects.filter(categoria='cupom')
    alteradas = 0
    for p in qs.iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        if 'mesa' in titulo or 'mesa' in texto:
            p.categoria = 'mesa'
            p.save(update_fields=['categoria'])
            alteradas += 1
    if alteradas:
        print(f'Reclassificadas {alteradas} promocoes de cupom para mesa.')


def reverter(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    Promo.objects.filter(categoria='mesa').update(categoria='cupom')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0133_reclassificar_consoles_switch'),
    ]

    operations = [
        migrations.RunPython(reclassificar_mesa, reverter),
    ]
