(function () {
    var banner = document.getElementById('cookieBanner');
    if (!banner) return;
    var KEY = 'nitrotech_cookie_consent';

    function getConsent() {
        try { return localStorage.getItem(KEY); } catch (e) { return null; }
    }

    function setConsent(value) {
        try { localStorage.setItem(KEY, value); } catch (e) {}
    }

    function isConsentSet() {
        var v = getConsent();
        return v === 'accepted' || v === 'rejected';
    }

    // Se o usuário já decidiu antes, não mostra o banner.
    if (isConsentSet()) {
        banner.style.display = 'none';
        return;
    }

    // Pequeno atraso para garantir que o banner seja perceptível e legível.
    setTimeout(function () { banner.classList.add('show'); }, 400);

    function hide() {
        banner.classList.remove('show');
        setTimeout(function () { banner.style.display = 'none'; }, 350);
    }

    var accept = document.getElementById('cookieAccept');
    var reject = document.getElementById('cookieReject');

    if (accept) {
        accept.addEventListener('click', function () {
            setConsent('accepted');
            hide();
        });
    }
    if (reject) {
        reject.addEventListener('click', function () {
            setConsent('rejected');
            hide();
        });
    }
})();
