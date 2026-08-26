(function () {
    var overlay = document.getElementById('exitPopup');
    if (!overlay) return;
    var closeBtn = document.getElementById('exitPopupClose');
    var dismissBtn = document.getElementById('exitPopupDismiss');
    var shown = false;
    var KEY = 'exitPopupDismissed';

    function shouldShow() {
        try {
            if (sessionStorage.getItem(KEY)) return false;
        } catch (e) {}
        return !shown;
    }

    function show() {
        if (!shouldShow()) return;
        shown = true;
        overlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function hide() {
        overlay.classList.remove('show');
        document.body.style.overflow = '';
        try { sessionStorage.setItem(KEY, '1'); } catch (e) {}
    }

    if (closeBtn) closeBtn.addEventListener('click', hide);
    if (dismissBtn) dismissBtn.addEventListener('click', hide);
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) hide();
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.classList.contains('show')) hide();
    });

    function trigger() {
        if (!shouldShow()) return;
        if (document.activeElement) document.activeElement.blur();
        show();
    }

    if (typeof document.hidden !== 'undefined') {
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) trigger();
        });
    }

    document.addEventListener('mouseout', function (e) {
        if (!e.relatedTarget && !e.toElement && e.clientY <= 0) trigger();
    });

    var timer = null;
    window.addEventListener('blur', function () {
        clearTimeout(timer);
        timer = setTimeout(function () {
            if (!document.hasFocus()) trigger();
        }, 200);
    });

    setTimeout(function () {
        if (!shouldShow()) return;
        setTimeout(trigger, 25000);
    }, 1000);
})();
