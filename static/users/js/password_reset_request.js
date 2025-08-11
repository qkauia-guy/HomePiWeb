// 表單防呆＋防重複送出
(function () {
  const form = document.getElementById('reset-form');
  const btn = document.getElementById('reset-btn');
  if (form && btn) {
    form.addEventListener('submit', function (e) {
      if (!form.checkValidity()) {
        e.preventDefault();
        Swal.fire({
          icon: 'warning',
          title: '欄位未填完整',
          text: '請填寫 Email',
        });
        return;
      }
      btn.disabled = true;
      btn.textContent = '處理中…';
    });
  }
})();

// 複製功能（Clipboard API + 備援）
(function () {
  const btn = document.getElementById('copy-link');
  if (!btn) return;

  async function copyText(text) {
    if (!text) return false;

    // 1) 首選安全環境 API
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (e) {
        /* 轉用備援 */
      }
    }

    // 2) 備援：textarea + execCommand
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  btn.addEventListener('click', async function () {
    const ta = document.getElementById('reset-link-text');
    const text = ta ? ta.value : '';
    const ok = await copyText(text);

    if (ok) {
      Swal.fire({
        icon: 'success',
        title: '已複製',
        text: '重設連結已複製到剪貼簿',
      });
    } else {
      if (ta) {
        ta.focus();
        ta.select();
        ta.setSelectionRange(0, ta.value.length);
      }
      Swal.fire({ icon: 'error', title: '複製失敗', text: '請手動選取後複製' });
    }
  });
})();
