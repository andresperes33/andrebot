from django.db import migrations


def classificar_artigos(apps, schema_editor):
    """Define a categoria padrão dos artigos existentes (os novos são
    definidos no admin). Apenas preenche 'guia' onde estiver vazio."""
    Artigo = apps.get_model('bot', 'Artigo')
    for artigo in Artigo.objects.all():
        if not artigo.categoria or artigo.categoria == 'guia':
            artigo.categoria = 'guia'
            artigo.save(update_fields=['categoria'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0046_artigo_categoria'),
    ]

    operations = [
        migrations.RunPython(classificar_artigos, noop),
    ]
