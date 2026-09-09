from django.db import migrations


def reclassificar_pc_gamer(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    alteradas = 0
    for p in Promo.objects.exclude(categoria='pc_gamer').iterator():
        titulo = (p.titulo or '').lower()
        texto = (p.texto_original or '').lower()
        if 'pc gamer' in titulo or 'computador gamer' in titulo or 'pc gamer' in texto or 'computador gamer' in texto:
            p.categoria = 'pc_gamer'
            p.save(update_fields=['categoria'])
            alteradas += 1
    if alteradas:
        print(f'Reclassificadas {alteradas} promocoes para pc_gamer.')


def reverter(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    Promo.objects.filter(categoria='pc_gamer').update(categoria='outros')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0134_reclassificar_mesa'),
    ]

    operations = [
        migrations.RunPython(reclassificar_pc_gamer, reverter),
    ]
