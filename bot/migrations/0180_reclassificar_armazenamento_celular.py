"""Reclassifica celulares/tablets cujo 'armazenamento' virou SSD.

Caso alvo:
    Celular Smartphone Realme C75 5G, 256GB de Armazenamento, 8GB de RAM, ...

O classificador tratava qualquer 'armazenamento' como SSD/HD avulso, mesmo
sendo o espaço interno do aparelho. Já corrigido; esta migration reaplica a
categoria nas ofertas antigas.
"""
from django.db import migrations

_DISPOSITIVOS = (
    'celular', 'smartphone', 'iphone', 'tablet', 'ipad', 'notebook', 'laptop',
)


def reclassificar_armazenamento(apps, schema_editor):
    from bot.classifier import detectar_categoria

    Promo = apps.get_model('bot', 'Promo')
    n = 0

    for promo in Promo.objects.filter(categoria='ssd').iterator():
        texto = promo.texto_original or promo.titulo or ''
        baixa = texto.casefold()
        if 'armazenamento' not in baixa:
            continue
        if not any(d in baixa for d in _DISPOSITIVOS):
            continue
        if any(m in baixa for m in ('ssd', 'nvme', 'm.2', 'hdd', 'sata', 'disco rigido')):
            continue
        try:
            correta = detectar_categoria(texto, titulo=promo.titulo)
        except Exception:
            continue
        if correta not in ('celular', 'tablet', 'notebook'):
            continue
        promo.categoria = correta
        promo.save(update_fields=['categoria'])
        n += 1

    if n:
        print(f'Aparelhos com armazenamento interno reclassificados de ssd: {n}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0179_reclassificar_roleta_app'),
    ]

    operations = [
        migrations.RunPython(
            reclassificar_armazenamento, migrations.RunPython.noop
        ),
    ]
