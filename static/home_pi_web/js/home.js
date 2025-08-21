document.addEventListener('DOMContentLoaded', () => {
  const toolTipAll = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  toolTipAll.forEach((t) => new bootstrap.Tooltip(t));
});

document.addEventListener('DOMContentLoaded', () => {
  const groupSelect = document.getElementById('groupSelect');
  const deviceSelect = document.getElementById('deviceSelect');
  const capSelect = document.getElementById('capSelect');
  const capForms = document.getElementById('capForms');
  const formPlaceholder = document.getElementById('formPlaceholder');
  const ajaxMsg = document.getElementById('ajaxMsg');

  function showMsg(kind, text) {
    ajaxMsg.classList.remove(
      'alert-success',
      'alert-danger',
      'alert-warning',
      'alert-info'
    );
    ajaxMsg.classList.add('alert', `alert-${kind}`, 'mt-3', 'mb-3');
    ajaxMsg.textContent = text;
    ajaxMsg.style.display = '';
    clearTimeout(showMsg._t);
    showMsg._t = setTimeout(() => {
      ajaxMsg.style.display = 'none';
    }, 3000);
  }

  function resetSelect(selectEl, placeholderText) {
    selectEl.innerHTML = `<option value="" disabled selected>${placeholderText}</option>`;
    selectEl.disabled = true;
  }

  function buildNextUrl() {
    const params = new URLSearchParams();
    if (groupSelect?.value) params.set('g', groupSelect.value);
    if (deviceSelect?.value) params.set('d', deviceSelect.value);
    if (capSelect?.value) params.set('cap', capSelect.value);
    return (window.HOME_URL || '/') + (params.toString() ? `?${params}` : '');
  }

  function syncNextHiddenInputs() {
    const nextUrl = buildNextUrl();
    capForms
      .querySelectorAll('form.cap-form input[name="next"]')
      .forEach((inp) => {
        inp.value = nextUrl;
      });

    // ★ 新增：把目前選到的群組（例如 "g5"）也塞進 hidden
    capForms
      .querySelectorAll('form.cap-form input[name="group_id"]')
      .forEach((inp) => {
        const gval = (groupSelect?.value || '').trim();
        if (gval) inp.value = gval;
      });

    return nextUrl;
  }

  // === 單一入口：帶上 cookie，並把 401/403 分類化 ===
  async function fetchText(url) {
    const resp = await fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });

    if (resp.status === 401) {
      const err = new Error('unauth');
      err.code = 'auth';
      throw err;
    }
    if (resp.status === 403) {
      // 優先嘗試讀 JSON（配合 Middleware 的 {"error":"group_required"}）
      try {
        const data = await resp.clone().json();
        if (data?.error === 'group_required') {
          const err = new Error('group required');
          err.code = 'group_required';
          err.redirect = data.redirect;
          throw err;
        }
      } catch (_) {
        /* 非 JSON 就略過 */
      }
      const err = new Error('forbidden');
      err.code = 'forbidden';
      throw err;
    }

    if (!resp.ok) {
      const err = new Error(`HTTP_${resp.status}`);
      err.code = 'http';
      err.status = resp.status;
      throw err;
    }
    return await resp.text();
  }

  function handleFetchError(e, fallbackMsg = '載入失敗') {
    if (e?.code === 'auth') {
      showMsg('danger', '請先登入');
    } else if (e?.code === 'group_required') {
      showMsg('warning', '你尚未加入任何群組，請先建立群組。');
    } else if (e?.code === 'forbidden') {
      showMsg('danger', '無權限');
    } else if (e?.code === 'http' && e.status) {
      showMsg('danger', `${fallbackMsg}（${e.status}）`);
    } else {
      showMsg('danger', fallbackMsg);
    }
  }

  async function onGroupChange() {
    resetSelect(deviceSelect, '請選擇裝置');
    resetSelect(capSelect, '請選擇功能');
    capForms.innerHTML = '';
    formPlaceholder.hidden = false;

    if (!groupSelect.value) return;
    try {
      // ✅ 正確：換成抓裝置清單
      const html = await fetchText(
        `/controls/devices/?group_id=${encodeURIComponent(groupSelect.value)}`
      );
      deviceSelect.insertAdjacentHTML('beforeend', html);
      deviceSelect.disabled = deviceSelect.options.length <= 1;
    } catch (e) {
      handleFetchError(e, '載入裝置失敗');
    }
  }

  async function onDeviceChange() {
    resetSelect(capSelect, '請選擇功能');
    capForms.innerHTML = '';
    formPlaceholder.hidden = false;

    if (!deviceSelect.value) return;
    try {
      // ✅ 正確：換成抓能力清單
      const html = await fetchText(
        `/controls/caps/?device_id=${encodeURIComponent(deviceSelect.value)}`
      );
      capSelect.insertAdjacentHTML('beforeend', html);
      capSelect.disabled = capSelect.options.length <= 1;
    } catch (e) {
      handleFetchError(e, '載入功能失敗');
    }
  }

  async function onCapChange() {
    capForms.innerHTML = '';
    formPlaceholder.hidden = !capSelect.value;
    if (!capSelect.value) return;
    try {
      const html = await fetchText(
        `/controls/cap-form/${encodeURIComponent(
          capSelect.value
        )}/?group_id=${encodeURIComponent(groupSelect.value)}`
      );
      capForms.innerHTML = html;
      formPlaceholder.hidden = true;
      syncNextHiddenInputs();
    } catch (e) {
      handleFetchError(e, '載入表單失敗');
    }
  }

  groupSelect?.addEventListener('change', async () => {
    await onGroupChange();
    syncNextHiddenInputs();
  });

  deviceSelect?.addEventListener('change', async () => {
    await onDeviceChange();
    syncNextHiddenInputs();
  });

  capSelect?.addEventListener('change', async () => {
    await onCapChange();
    syncNextHiddenInputs();
  });

  // capForms 內的 .cap-form 攔截 submit，改用 AJAX（含 401/403）
  capForms.addEventListener('submit', async (e) => {
    const f = e.target.closest('form.cap-form');
    if (!f) return;
    e.preventDefault();

    const nextUrl = syncNextHiddenInputs();
    const action = f.getAttribute('action');
    const method = (f.getAttribute('method') || 'post').toUpperCase();
    const formData = new FormData(f);
    const csrf =
      f.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';

    try {
      const resp = await fetch(action, {
        method,
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrf,
        },
        credentials: 'same-origin',
        body: formData,
      });

      if (resp.status === 401) {
        showMsg('danger', '請先登入');
        return;
      }
      if (resp.status === 403) {
        // 嘗試辨識需要群組
        try {
          const data = await resp.clone().json();
          if (data?.error === 'group_required') {
            showMsg('warning', '你尚未加入任何群組，請先建立群組。');
            return;
          }
        } catch {}
        showMsg('danger', '無權限');
        return;
      }

      if (resp.ok) {
        showMsg('success', '已送出指令。');
      } else {
        showMsg('warning', '伺服器回應非 200，改為導回。');
        window.location.href = nextUrl;
      }
    } catch (err) {
      showMsg('danger', '送出失敗，請稍後再試。');
    }
  });

  // → 進頁自動恢復選擇（依 URL ?g=&d=&cap=）
  (async function initFromParams() {
    const usp = new URLSearchParams(location.search);
    const g = usp.get('g');
    const d = usp.get('d');
    const cap = usp.get('cap');

    if (g && groupSelect.querySelector(`option[value="${g}"]`)) {
      groupSelect.value = g;
      await onGroupChange();
      if (d && deviceSelect.querySelector(`option[value="${d}"]`)) {
        deviceSelect.value = d;
        await onDeviceChange();
        if (cap && capSelect.querySelector(`option[value="${cap}"]`)) {
          capSelect.value = cap;
          await onCapChange();
        }
      }
    }
    syncNextHiddenInputs();
  })();
});
