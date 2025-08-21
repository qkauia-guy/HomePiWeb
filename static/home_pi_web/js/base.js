document.addEventListener('DOMContentLoaded', () => {
  // 方便比對登入/建群組路徑（若 base.html 有注入 APP_URLS 會自動使用）
  const loginPath = (() => {
    try {
      const u =
        (window.APP_URLS && window.APP_URLS.login) || '/accounts/login/';
      return new URL(u, window.location.origin).pathname;
    } catch {
      return '/accounts/login/';
    }
  })();
  const groupCreatePath = (() => {
    try {
      const u =
        (window.APP_URLS && window.APP_URLS.groupCreate) || '/groups/create/';
      return new URL(u, window.location.origin).pathname;
    } catch {
      return '/groups/create/';
    }
  })();

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
          credentials: 'same-origin', // 確保帶上 session cookie（同源）
        });

        // 先處理狀態碼（配合 Middleware 的 401/403）
        if (resp.status === 401) {
          body.innerHTML = '<div class="text-danger">請先登入</div>';
          return;
        }
        if (resp.status === 403) {
          let data = {};
          try {
            data = await resp.json();
          } catch {
            /* 不是 JSON 就略過 */
          }
          if (data && data.error === 'group_required') {
            body.innerHTML =
              '<div class="text-warning">你尚未加入任何群組，請先建立群組。</div>';
            return;
          }
          body.innerHTML = '<div class="text-danger">無權限</div>';
          return;
        }

        // 保險：若伺服器仍以 302 重導（非 JSON）
        if (resp.redirected) {
          const dest = new URL(resp.url, window.location.origin);
          if (dest.pathname === loginPath) {
            body.innerHTML = '<div class="text-danger">請先登入</div>';
          } else if (dest.pathname === groupCreatePath) {
            body.innerHTML =
              '<div class="text-warning">你尚未加入任何群組，請先建立群組。</div>';
          } else {
            body.innerHTML = `<div class="text-danger">已被導向到 ${dest.pathname}</div>`;
          }
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
