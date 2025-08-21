document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.offcanvas').forEach((oc) => {
    oc.addEventListener('show.bs.offcanvas', async () => {
      const body = oc.querySelector('.offcanvas-body[data-load-url]');
      if (!body) return;

      // 已載入就不再請求
      if (body.dataset.loaded === '1') return;

      const url = body.dataset.loadUrl || body.getAttribute('data-load-url');
      if (!url) {
        console.warn('[offcanvas] 缺少 data-load-url');
        body.innerHTML = '<div class="text-danger">未設定載入位址</div>';
        return;
      }

      body.innerHTML = '<div class="text-muted">載入中…</div>';

      try {
        const resp = await fetch(url, {
          method: 'GET',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
          credentials: 'same-origin', // 確保帶上 session cookie
        });

        // 若被導到登入頁（302/redirect）
        if (resp.redirected) {
          body.innerHTML = '<div class="text-danger">請先登入</div>';
          return;
        }

        if (!resp.ok) {
          body.innerHTML = `<div class="text-danger">載入失敗（${resp.status}）</div>`;
          return;
        }

        const html = await resp.text();
        body.innerHTML = html;
        body.dataset.loaded = '1';
        console.log('[offcanvas] loaded:', url);
      } catch (e) {
        console.error('[offcanvas] fetch error:', e);
        body.innerHTML = '<div class="text-danger">連線失敗，稍後再試</div>';
      }
    });
  });
});
