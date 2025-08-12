(function () {
  // 1) 自動幫所有欄位套上 Bootstrap 樣式
  const form = document.getElementById('register-form');
  if (form) {
    form.querySelectorAll('input, select, textarea').forEach((el) => {
      // 跳過 checkbox/radio 的 form-control
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'checkbox' || type === 'radio') return;
      el.classList.add('form-control');
      // 補常用屬性與 placeholder（若沒設定）
      if (!el.getAttribute('placeholder')) {
        const lbl = form.querySelector('label[for="' + el.id + '"]');
        if (lbl && lbl.textContent.trim())
          el.setAttribute('placeholder', lbl.textContent.trim());
      }
    });
  }

  // 2) 送出前驗證 + 防重複提交
  const btn = document.getElementById('register-btn');
  if (form && btn) {
    form.addEventListener('submit', function (e) {
      if (!form.checkValidity()) {
        e.preventDefault();
        Swal.fire({
          icon: 'warning',
          title: '欄位未填完整',
          text: '請檢查必填欄位與格式',
        });
        return;
      }
      btn.disabled = true;
      btn.textContent = '註冊中…';
    });
  }
})();
