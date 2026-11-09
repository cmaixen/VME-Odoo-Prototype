// Injected into every page of the recording: a visible mouse pointer and a caption band.
// Headless Chromium draws no cursor, and the captions are burned into the video this way,
// so the final MP4 needs no subtitle filter in ffmpeg.
(() => {
    if (window.__vmeOverlay) {
        return;
    }
    window.__vmeOverlay = true;

    const STYLE = `
        #vme-cursor { position: fixed; z-index: 2147483647; width: 22px; height: 22px; margin: -3px 0 0 -3px;
            pointer-events: none; transition: transform 0.08s; }
        #vme-cursor.down { transform: scale(0.8); }
        #vme-click { position: fixed; z-index: 2147483646; width: 44px; height: 44px; margin: -22px 0 0 -22px;
            border-radius: 50%; border: 3px solid #e8a33d; pointer-events: none; opacity: 0; }
        #vme-click.show { animation: vme-ping 0.6s ease-out; }
        @keyframes vme-ping { from { opacity: 1; transform: scale(0.4); } to { opacity: 0; transform: scale(1.4); } }
        #vme-caption { position: fixed; z-index: 2147483645; left: 50%; bottom: 28px; transform: translateX(-50%);
            max-width: 1500px; padding: 16px 28px 18px; border-radius: 12px; pointer-events: none;
            background: rgba(20, 28, 38, 0.88); color: #fff; box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35); transition: opacity 0.3s;
            font: 500 25px/1.38 "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; text-align: center; }
        #vme-caption .step { display: block; margin-bottom: 4px; color: #f2c46d;
            font-size: 17px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }
        #vme-caption:empty { display: none; }
        #vme-mark { position: fixed; z-index: 2147483647; right: 8px; bottom: 8px; width: 12px; height: 12px;
            pointer-events: none; }
    `;
    const CURSOR = `<svg id="vme-cursor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 2 L3 19 L7.5 14.8 L10.6 21.5 L13.4 20.2 L10.4 13.7 L16.5 13.7 Z"
              fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;

    function install() {
        if (document.getElementById('vme-caption') || !document.body) {
            return;
        }
        const style = document.createElement('style');
        style.textContent = STYLE;
        document.head.appendChild(style);
        document.body.insertAdjacentHTML('beforeend', CURSOR + '<div id="vme-click"></div><div id="vme-caption"></div><div id="vme-mark"></div>');
        const pos = JSON.parse(sessionStorage.getItem('vmeCursor') || '[960, 540]');
        moveTo(pos[0], pos[1]);
        setCaption(sessionStorage.getItem('vmeCaption') || '');
        setMark(sessionStorage.getItem('vmeMark'));
    }

    function moveTo(x, y) {
        const cursor = document.getElementById('vme-cursor');
        if (cursor) {
            cursor.style.left = x + 'px';
            cursor.style.top = y + 'px';
        }
        try {
            sessionStorage.setItem('vmeCursor', JSON.stringify([x, y]));
        } catch (e) { /* sandboxed page */ }
    }

    function setCaption(html) {
        const caption = document.getElementById('vme-caption');
        if (caption) {
            caption.innerHTML = html;
        }
        try {
            sessionStorage.setItem('vmeCaption', html);
        } catch (e) { /* sandboxed page */ }
    }

    window.__vmeSetCaption = setCaption;
    // Sync marker: a small square that flips between magenta and green at every spoken sentence.
    // align.py finds the flips in the video; make_video.py paints them out again (delogo).
    function setMark(n) {
        const mark = document.getElementById('vme-mark');
        if (mark && n !== null && n !== undefined) {
            mark.style.background = Number(n) % 2 ? '#00ff00' : '#ff00ff';
        }
        try {
            if (n !== null && n !== undefined) sessionStorage.setItem('vmeMark', String(n));
        } catch (e) { /* sandboxed page */ }
    }
    window.__vmeMark = setMark;
    window.__vmeDimCaption = (dim) => {
        const caption = document.getElementById('vme-caption');
        if (caption) {
            caption.style.opacity = dim ? '0.12' : '';
        }
    };
    document.addEventListener('mousemove', (ev) => moveTo(ev.clientX, ev.clientY), true);
    document.addEventListener('mousedown', (ev) => {
        document.getElementById('vme-cursor')?.classList.add('down');
        const ring = document.getElementById('vme-click');
        if (ring) {
            ring.style.left = ev.clientX + 'px';
            ring.style.top = ev.clientY + 'px';
            ring.classList.remove('show');
            void ring.offsetWidth;
            ring.classList.add('show');
        }
    }, true);
    document.addEventListener('mouseup', () => document.getElementById('vme-cursor')?.classList.remove('down'), true);
    // Odoo re-renders the body on some navigations; put the overlay back when it disappears.
    // Init scripts run before <html> exists, so watch the document itself.
    new MutationObserver(install).observe(document, { childList: true, subtree: true });
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', install);
    } else {
        install();
    }
})();
