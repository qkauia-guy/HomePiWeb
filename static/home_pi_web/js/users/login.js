// 登入頁面基本功能（移除 API 相關代碼）

(function () {
  const form = document.getElementById('login-form');
  const btn = document.getElementById('login-btn');
  if (!form || !btn) return; // 防呆
  
  form.addEventListener('submit', function (e) {
    if (!form.checkValidity()) {
      e.preventDefault();
      // 使用簡單的 alert 替代 SweetAlert
      alert('請填寫 Email 與密碼');
      return;
    }
    btn.disabled = true;
    btn.textContent = '登入中…';
  });
})();
