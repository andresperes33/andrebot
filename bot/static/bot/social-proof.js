(function () {
    var NAMES = [
        'João', 'Pedro', 'Lucas', 'Mateus', 'Rafael', 'Bruno', 'Gustavo',
        'Felipe', 'Thiago', 'Ricardo', 'Marcelo', 'Anderson', 'Carlos',
        'Eduardo', 'Fernando', 'Paulo', 'Rodrigo', 'Diego', 'Leonardo',
        'Rafaela', 'Juliana', 'Camila', 'Patrícia', 'Amanda', 'Bruna',
        'Carla', 'Fernanda', 'Letícia', 'Vanessa', 'Priscila'
    ];
    var CITIES = [
        'São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Curitiba',
        'Porto Alegre', 'Salvador', 'Recife', 'Fortaleza', 'Brasília',
        'Goiânia', 'Florianópolis', 'Campinas', 'Manaus', 'Belém'
    ];
    var PRODUCTS = [
        { icon: 'fa-microchip', text: 'Placa de Vídeo RTX 4060' },
        { icon: 'fa-tv', text: 'Smart TV 55" 4K' },
        { icon: 'fa-microchip', text: 'Processador AMD Ryzen 5' },
        { icon: 'fa-memory', text: 'SSD NVMe 1TB' },
        { icon: 'fa-laptop', text: 'Notebook Gamer' },
        { icon: 'fa-desktop', text: 'Monitor 144Hz' },
        { icon: 'fa-keyboard', text: 'Teclado Mecânico' },
        { icon: 'fa-mouse', text: 'Mouse Gamer' },
        { icon: 'fa-headphones', text: 'Headset RGB' },
        { icon: 'fa-memory', text: 'Memória RAM 16GB' },
        { icon: 'fa-motherboard', text: 'Placa-Mãe B550' },
        { icon: 'fa-plug', text: 'Fonte 650W 80 Plus' },
        { icon: 'fa-hdd', text: 'HD Externo 2TB' },
        { icon: 'fa-camera', text: 'Webcam Full HD' },
        { icon: 'fa-volume-high', text: 'Caixa de Som Bluetooth' },
        { icon: 'fa-wifi', text: 'Roteador Wi-Fi 6' },
        { icon: 'fa-laptop', text: 'Notebook Dell i5' },
        { icon: 'fa-bolt', text: 'Carregador 65W PD' },
        { icon: 'fa-plug', text: 'Hub USB-C 7 em 1' },
        { icon: 'fa-tablet-screen-button', text: 'Tablet Android 10"' },
        { icon: 'fa-gamepad', text: 'Controle Xbox Series' },
        { icon: 'fa-microchip', text: 'Placa de Vídeo RX 7600' },
        { icon: 'fa-tv', text: 'Smart TV 50" Full HD' },
        { icon: 'fa-mobile-screen', text: 'Smartphone Moto G84' },
        { icon: 'fa-headphones', text: 'Fone Bluetooth TWS' },
        { icon: 'fa-watch', text: 'Smartwatch Xiaomi' }
    ];
    var TIMES = [
        'há 2 minutos', 'há 5 minutos', 'há 8 minutos', 'há 12 minutos',
        'há 15 minutos', 'há 20 minutos', 'há 3 minutos', 'há 7 minutos',
        'há 1 minuto', 'há 10 minutos'
    ];

    function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

    function buildMessage() {
        var name = pick(NAMES);
        var city = pick(CITIES);
        var product = pick(PRODUCTS);
        var time = pick(TIMES);
        return {
            icon: product.icon,
            html: '<strong>' + name + '</strong> de ' + city + ' <br>comprou <strong>' + product.text + '</strong>',
            time: time
        };
    }

    var el = document.getElementById('socialProof');
    if (!el) return;

    var iconEl = el.querySelector('.social-proof-icon i');
    var textEl = el.querySelector('.social-proof-text');
    var timeEl = el.querySelector('.social-proof-time');
    var closeBtn = el.querySelector('.social-proof-close');
    var timer = null;
    var interval = null;

    function showNotification() {
        var msg = buildMessage();
        iconEl.className = 'fas ' + msg.icon;
        textEl.innerHTML = msg.html;
        timeEl.textContent = msg.time;
        el.classList.add('show');
        timer = setTimeout(hideNotification, 5000);
    }

    function hideNotification() {
        if (timer) { clearTimeout(timer); timer = null; }
        el.classList.remove('show');
    }

    function startCycle() {
        showNotification();
        interval = setInterval(function () {
            hideNotification();
            setTimeout(showNotification, 600);
        }, 12000);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', function () {
            hideNotification();
            if (interval) { clearInterval(interval); interval = null; }
        });
    }

    setTimeout(startCycle, 3000);
})();
