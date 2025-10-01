// 獲取當前主題
function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') || 
         document.body.getAttribute('data-theme') || 
         (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
}

// 若後端未套 Bootstrap，小幫手：把欄位套 form-control
(function () {
  const ids = ['id_new_password1', 'id_new_password2'];
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('form-control');
      el.setAttribute('autocomplete', 'new-password');
      el.setAttribute('required', 'required');
      if (!el.getAttribute('placeholder'))
        el.setAttribute('placeholder', '••••••••');
    }
  });
})();

// 前端防呆與防重複提交
(function () {
  const form = document.getElementById('setpw-form');
  const btn = document.getElementById('setpw-btn');
  if (!form || !btn) return;
  form.addEventListener('submit', function (e) {
    // 基礎檢查：兩欄必填且相同（瀏覽器原生 + 簡單檢查）
    const p1 = document.getElementById('id_new_password1');
    const p2 = document.getElementById('id_new_password2');
    if (!p1.value || !p2.value) {
      e.preventDefault();
      Swal.fire({
        icon: 'warning',
        title: '欄位未填完整',
        text: '請輸入並確認新密碼',
        colorScheme: getCurrentTheme(),
        background: getCurrentTheme() === 'dark' ? '#1a1a1a' : '#fff',
        color: getCurrentTheme() === 'dark' ? '#f5f5f5' : '#333',
        confirmButtonColor: getCurrentTheme() === 'dark' ? '#6366f1' : '#007bff'
      });
      return;
    }
    if (p1.value !== p2.value) {
      e.preventDefault();
      Swal.fire({
        icon: 'error',
        title: '兩次密碼不一致',
        text: '請再次確認新密碼',
        colorScheme: getCurrentTheme(),
        background: getCurrentTheme() === 'dark' ? '#1a1a1a' : '#fff',
        color: getCurrentTheme() === 'dark' ? '#f5f5f5' : '#333',
        confirmButtonColor: getCurrentTheme() === 'dark' ? '#6366f1' : '#007bff'
      });
      return;
    }
    btn.disabled = true;
    btn.textContent = '更新中…';
  });
})();
