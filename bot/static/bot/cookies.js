(function () {
    var banner = document.getElementById('cookieBanner');
    if (!banner) return;
    var KEY = 'nitrotech_cookie_consent';
    var SESSION = 'noSession';

    function getConsent() {
        try { return localStorage.getItem(KEY); } catch (e) { return null; }
    }

    function setConsent(value) {
        try { localStorage.setItem(KEY, value); } catch (e) {}
    }

    function isConsentSet() {
        var v = getConsent();
        return v === 'accepted' || v === 'rejected' || v === SESSION;
    }

    if (isConsentSet()) {
        banner.style.display = 'none';
        return;
    }

    banner.classList.add('show');

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

    // Se o usuário rolar bastante a página, tratamos como consentimento
    // implícito (padrão de mercado) salvo apenas na sessão.
    window.addEventListener('scroll', function () {
        if (isConsentSet()) return;
        if (window.scrollY > 300) {
            setConsent(SESSION);
            hide();
        }
    }, { passive: true });
})();
