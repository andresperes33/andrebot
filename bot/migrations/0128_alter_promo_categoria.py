from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0127_reclassificar_cadeiras'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promo',
            name='categoria',
            field=models.CharField(choices=[('ssd', 'SSD / HD'), ('placa_video', 'Placa de Vídeo'), ('placa_mae', 'Placa-mãe'), ('processador', 'Processador'), ('memoria_ram', 'Memória RAM'), ('kit', 'Kit (Placa + CPU + RAM)'), ('notebook', 'Notebook'), ('monitor', 'Monitor'), ('celular', 'Celular / Smartphone'), ('tablet', 'Tablet'), ('tv', 'TV'), ('caixa_som', 'Caixa de Som / Soundbar'), ('headset', 'Fone / Headset'), ('teclado', 'Teclado'), ('mouse', 'Mouse'), ('mousepad', 'Mousepad'), ('cadeira', 'Cadeira Escritório/Gamer'), ('impressora', 'Impressora'), ('fonte', 'Fonte'), ('gabinete', 'Gabinete'), ('cooler', 'Cooler / Water Cooler / Fan'), ('pasta_termica', 'Pasta Térmica'), ('controle', 'Controle / Gamepad'), ('webcam', 'Webcam'), ('cabo', 'Cabo / Carregador'), ('microfone', 'Microfone'), ('roteador', 'Roteador'), ('console', 'Console'), ('jogo', 'Jogo'), ('cupom', 'Cupom'), ('ar_condicionado', 'Ar Condicionado'), ('outros', 'Outros')], default='outros', max_length=50),
        ),
    ]
