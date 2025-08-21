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
    // 先移除舊的顏色類別
    ajaxMsg.classList.remove(
      'alert-success',
      'alert-danger',
      'alert-warning',
      'alert-info'
    );

    // 固定保留 margin 與 alert 基礎類別，再加上這次的顏色
    ajaxMsg.classList.add('alert', `alert-${kind}`, 'mt-3', 'mb-3');

    ajaxMsg.textContent = text;
    ajaxMsg.style.display = ''; // 顯示
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
    if (groupSelect?.value) params.set('g', groupSelect.value); // g12
    if (deviceSelect?.value) params.set('d', deviceSelect.value); // device id
    if (capSelect?.value) params.set('cap', capSelect.value); // cap id
    return (window.HOME_URL || '/') + (params.toString() ? `?${params}` : '');
  }

  function syncNextHiddenInputs() {
    const nextUrl = buildNextUrl();
    capForms
      .querySelectorAll('form.cap-form input[name="next"]')
      .forEach((inp) => {
        inp.value = nextUrl;
      });
    return nextUrl;
  }

  async function fetchText(url) {
    const resp = await fetch(url, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.text();
  }

  async function onGroupChange() {
    resetSelect(deviceSelect, '請選擇裝置');
    resetSelect(capSelect, '請選擇功能');
    capForms.innerHTML = '';
    formPlaceholder.hidden = false;

    if (!groupSelect.value) return;
    try {
      const html = await fetchText(
        `/controls/devices/?group_id=${encodeURIComponent(groupSelect.value)}`
      );
      deviceSelect.insertAdjacentHTML('beforeend', html);
      // deviceSelect.disabled = deviceSelect.options.length > 1;
      deviceSelect.disabled = deviceSelect.options.length <= 1;
    } catch (e) {
      showMsg('danger', '載入裝置失敗');
    }
  }

  async function onDeviceChange() {
    resetSelect(capSelect, '請選擇功能');
    capForms.innerHTML = '';
    formPlaceholder.hidden = false;

    if (!deviceSelect.value) return;
    try {
      const html = await fetchText(
        `/controls/caps/?device_id=${encodeURIComponent(deviceSelect.value)}`
      );
      capSelect.insertAdjacentHTML('beforeend', html);
      // capSelect.disabled = capSelect.options.length > 1;
      capSelect.disabled = capSelect.options.length <= 1;
    } catch (e) {
      showMsg('danger', '載入功能失敗');
    }
  }

  async function onCapChange() {
    capForms.innerHTML = '';
    formPlaceholder.hidden = !capSelect.value;
    if (!capSelect.value) return;
    try {
      const html = await fetchText(
        `/controls/cap-form/${encodeURIComponent(capSelect.value)}/`
      );
      capForms.innerHTML = html;
      formPlaceholder.hidden = true;
      syncNextHiddenInputs();
    } catch (e) {
      showMsg('danger', '載入表單失敗');
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

  // 事件委派：capForms 內的 .cap-form 攔截 submit，改用 AJAX
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
        body: formData,
      });
      if (resp.ok) {
        showMsg('success', '已送出指令。');
      } else {
        // 後備：後端若未支援 AJAX，導回 next（仍保留選擇）
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
    const g = usp.get('g'); // g12
    const d = usp.get('d'); // device id
    const cap = usp.get('cap'); // cap id

    if (g && groupSelect.querySelector(`option[value="${g}"]`)) {
      groupSelect.value = g;
      await onGroupChange();
      if (d) {
        // 等裝置載入完後再選
        if (deviceSelect.querySelector(`option[value="${d}"]`)) {
          deviceSelect.value = d;
          await onDeviceChange();
          if (cap && capSelect.querySelector(`option[value="${cap}"]`)) {
            capSelect.value = cap;
            await onCapChange();
          }
        }
      }
    }
    syncNextHiddenInputs();
  })();
});
