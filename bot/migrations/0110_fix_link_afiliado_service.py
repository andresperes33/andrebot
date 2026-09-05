from django.db import migrations
import re

def update_link_afiliado(apps, schema_editor):
    Promo = apps.get_model('bot', 'Promo')
    # Patterns for service links to ignore
    service_patterns = ['amazonprime', 'netflix', 'disney+', 'hbo+', 'spotify', 'apple.music', 'steam', 'pago.com.br', 'asassinatura', 'assinatura', 'plus', 'prime', 'completed']
    for promo in Promo.objects.all():
        if promo.link_afiliado and any(p in promo.link_afiliado for p in service_patterns):
            # Recalculate using the updated logic
            from bot.services import _link_produto_compra
            new_link = _link_produto_compra(promo.texto_original or '')
            if new_link and new_link != promo.link_afiliado:
                promo.link_afiliado = new_link
                promo.save(update_fields=['link_afiliado'])
                print(f"Atualizado promo {promo.pk} link_afiliado -> {new_link}")

def reverse_func(apps, schema_editor):
    # Não há reversão automática
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('bot', '0110_alter_evento_conteudo'),
    ]
    operations = [
        migrations.RunPython(update_link_afiliado, reverse_func),
    ]
