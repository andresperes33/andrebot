"""Troca a tag de associado Amazon antiga pela nova (andreindica0c-20).

As ofertas já salvas guardam o link de afiliado (e o texto original) com a
tag vigente na época. Como a tag mudou, os links antigos continuariam
creditando a conta errada. Esta migration reescreve apenas o parâmetro
``tag=`` dentro de ``link_afiliado`` e ``texto_original``.

Idempotente: rodar de novo não altera nada (a tag nova não está na lista
de tags antigas).
"""
import re

from django.db import migrations

TAG_NOVA = 'andreindica0c-20'
TAGS_ANTIGAS = ('andreindic02b-20', 'andre0cda-20')

# (?<=[?&]) garante que só trocamos o parâmetro 'tag', não algo como
# 'mytag=' ou 'tag=' no meio de outro valor.
_RE_TAG = re.compile(
    r'(?<=[?&])tag=(?:' + '|'.join(re.escape(t) for t in TAGS_ANTIGAS) + r')(?=[&#]|$)',
    re.IGNORECASE,
)


def _trocar(texto):
    if not texto:
        return texto
    return _RE_TAG.sub(f'tag={TAG_NOVA}', texto)


def atualizar_tag_amazon(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')

    alterados = []
    for promo in Promo.objects.all().iterator():
        link = _trocar(promo.link_afiliado)
        original = _trocar(promo.texto_original)
        if link != promo.link_afiliado or original != promo.texto_original:
            promo.link_afiliado = link
            promo.texto_original = original
            alterados.append(promo)

    if alterados:
        Promo.objects.bulk_update(
            alterados, ['link_afiliado', 'texto_original'], batch_size=200
        )
        print(f'Promos com tag Amazon atualizada para {TAG_NOVA}: {len(alterados)}')


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0172_reclassificar_cupom_resgate_codigos'),
    ]

    operations = [
        migrations.RunPython(
            atualizar_tag_amazon, migrations.RunPython.noop
        ),
    ]
