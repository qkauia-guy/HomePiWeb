document.addEventListener('shown.bs.offcanvas', function (e) {
  if (e.target.id !== 'sideBar') return;

  const body = document.getElementById('offcanvas-devices-body');
  if (!body) return;

  const url = body.dataset.loadUrl; // ← 從 HTML 的 data-* 取真正 URL
  if (!url) {
    body.innerHTML = '<div class="text-danger">未設定載入網址</div>';
    return;
  }

  if (body.dataset.loaded === '1') return; // 已載過就不重複

  fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then((r) => r.text())
    .then((html) => {
      body.innerHTML = html;
      body.dataset.loaded = '1';
    })
    .catch(() => {
      body.innerHTML = '<div class="text-danger">載入失敗</div>';
    });
});
