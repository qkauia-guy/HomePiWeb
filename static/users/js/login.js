(function () {
  const form = document.getElementById('login-form');
  const btn = document.getElementById('login-btn');
  if (!form || !btn) return; // 防呆
  form.addEventListener('submit', function (e) {
    if (!form.checkValidity()) {
      e.preventDefault();
      Swal.fire({
        icon: 'warning',
        title: '欄位未填完整',
        text: '請填寫 Email 與密碼',
      });
      return;
    }
    btn.disabled = true;
    btn.textContent = '登入中…';
  });
})();
