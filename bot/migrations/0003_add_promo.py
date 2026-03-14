from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0002_add_bot_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='Promo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(blank=True, max_length=500)),
                ('preco', models.CharField(blank=True, max_length=100)),
                ('cupom', models.CharField(blank=True, max_length=200)),
                ('link_afiliado', models.URLField(max_length=2000)),
                ('imagem_url', models.URLField(blank=True, max_length=2000)),
                ('categoria', models.CharField(
                    choices=[
                        ('ssd', 'SSD / HD'),
                        ('placa_video', 'Placa de Vídeo'),
                        ('processador', 'Processador'),
                        ('memoria_ram', 'Memória RAM'),
                        ('notebook', 'Notebook'),
                        ('monitor', 'Monitor'),
                        ('celular', 'Celular / Smartphone'),
                        ('tv', 'TV'),
                        ('headset', 'Fone / Headset'),
                        ('teclado', 'Teclado'),
                        ('mouse', 'Mouse'),
                        ('cadeira', 'Cadeira Gamer'),
                        ('impressora', 'Impressora'),
                        ('outros', 'Outros'),
                    ],
                    default='outros',
                    max_length=50,
                )),
                ('fonte', models.CharField(default='zFinnY', max_length=100)),
                ('texto_original', models.TextField(blank=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Promoção',
                'verbose_name_plural': 'Promoções',
                'ordering': ['-criado_em'],
            },
        ),
    ]
