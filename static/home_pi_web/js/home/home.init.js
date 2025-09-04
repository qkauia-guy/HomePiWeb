/* home.init.js — 群組/裝置/能力載入、表單 AJAX、共用工具 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);

  // 專案級共用 UI 小工具
  function showBanner(kind, text) {
    const ajaxMsg = $('#ajaxMsg');
    if (!ajaxMsg) return window.App?.toast?.(text, kind === 'success');
    ajaxMsg.className = `alert alert-${kind} mt-3 mb-3`;
    ajaxMsg.textContent = text;
    ajaxMsg.style.display = '';
    clearTimeout(showBanner._t);
    showBanner._t = setTimeout(() => {
      ajaxMsg.style.display = 'none';
    }, 3000);
  }
  function resetSelect(selectEl, placeholderText) {
    if (!selectEl) return;
    selectEl.innerHTML = `<option value="" disabled selected>${placeholderText}</option>`;
    selectEl.disabled = true;
  }
  function buildNextUrl() {
    const groupSelect = $('#groupSelect');
    const deviceSelect = $('#deviceSelect');
    const capSelect = $('#capSelect');
    const params = new URLSearchParams();
    if (groupSelect?.value) params.set('g', groupSelect.value);
    if (deviceSelect?.value) params.set('d', deviceSelect.value);
    if (capSelect?.value) params.set('cap', capSelect.value);
    return (window.HOME_URL || '/') + (params.toString() ? `?${params}` : '');
  }
  function syncNextHiddenInputs() {
    const capForms = $('#capForms');
    const nextUrl = buildNextUrl();
    capForms
      ?.querySelectorAll('form.cap-form input[name="next"]')
      .forEach((inp) => (inp.value = nextUrl));
    const groupSelect = $('#groupSelect');
    capForms
      ?.querySelectorAll('form.cap-form input[name="group_id"]')
      .forEach((inp) => {
        const g = (groupSelect?.value || '').trim();
        if (g) inp.value = g;
      });
    return nextUrl;
  }
  function handleFetchError(e, fallbackMsg = '載入失敗') {
    const map = {
      auth: '請先登入',
      group_required: '你尚未加入任何群組，請先建立群組。',
      forbidden: '無權限',
    };
    const msg =
      map[e?.code] ||
      (e?.status ? `${fallbackMsg}（${e.status}）` : fallbackMsg);
    showBanner(e?.code === 'group_required' ? 'warning' : 'danger', msg);
  }

  // 將共用工具掛到全域，給其他模組用
  window.HomeUI = {
    showBanner,
    resetSelect,
    syncNextHiddenInputs,
    handleFetchError,
  };

  document.addEventListener('DOMContentLoaded', async () => {
    // 啟用 tooltip（若有 Bootstrap）
    if (window.bootstrap?.Tooltip) {
      [...document.querySelectorAll("[data-bs-toggle='tooltip']")].forEach(
        (el) => new bootstrap.Tooltip(el)
      );
    }

    const groupSelect = $('#groupSelect');
    const deviceSelect = $('#deviceSelect');
    const capSelect = $('#capSelect');
    const capForms = $('#capForms');
    const formPh = $('#formPlaceholder');

    async function onGroupChange() {
      resetSelect(deviceSelect, '請選擇裝置');
      resetSelect(capSelect, '請選擇功能');
      if (capForms) capForms.innerHTML = '';
      if (formPh) formPh.hidden = false;

      if (!groupSelect?.value) return;
      try {
        const html = await App.fetchText(
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
      if (capForms) capForms.innerHTML = '';
      if (formPh) formPh.hidden = false;

      if (!deviceSelect?.value) return;
      try {
        const html = await App.fetchText(
          `/controls/caps/?device_id=${encodeURIComponent(deviceSelect.value)}`
        );
        capSelect.insertAdjacentHTML('beforeend', html);
        capSelect.disabled = capSelect.options.length <= 1;
      } catch (e) {
        handleFetchError(e, '載入功能失敗');
      }
    }

    async function onCapChange() {
      if (capForms) capForms.innerHTML = '';
      if (formPh) formPh.hidden = !capSelect?.value;
      if (!capSelect?.value) return;

      try {
        const html = await App.fetchText(
          `/controls/cap-form/${encodeURIComponent(
            capSelect.value
          )}/?group_id=${encodeURIComponent(groupSelect.value || '')}`
        );
        capForms.innerHTML = html;
        if (formPh) formPh.hidden = true;
        syncNextHiddenInputs();

        // 通知其他模組：表單已載入
        const schedForm = capForms.querySelector('form[id^="schedForm-"]');
        document.dispatchEvent(
          new CustomEvent('cap-form-loaded', {
            detail: { form: schedForm, container: capForms },
          })
        );
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

    // capForms 內的 .cap-form 攔截 submit，改用 AJAX
    capForms?.addEventListener('submit', async (e) => {
      const f = e.target.closest('form.cap-form');
      if (!f) return;
      e.preventDefault();

      const nextUrl = syncNextHiddenInputs();
      const action = f.getAttribute('action');
      const method = (f.getAttribute('method') || 'post').toUpperCase();
      const formData = new FormData(f);

      try {
        const resp = await fetch(action, {
          method,
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': App.getCsrf(),
          },
          credentials: 'same-origin',
          body: formData,
        });

        if (resp.status === 401) return showBanner('danger', '請先登入');
        if (resp.status === 403) {
          try {
            const data = await resp.clone().json();
            if (data?.error === 'group_required')
              return showBanner(
                'warning',
                '你尚未加入任何群組，請先建立群組。'
              );
          } catch {}
          return showBanner('danger', '無權限');
        }

        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const data = await resp.json();
          App.showMessagesFromJson(data);
        } else if (resp.ok) {
          showBanner('success', '已送出指令。');
        } else {
          window.location.href = nextUrl; // 保險導回
        }
      } catch {
        showBanner('danger', '送出失敗，請稍後再試。');
      }
    });

    // 依 URL 參數自動恢復選擇
    (async function initFromParams() {
      const usp = new URLSearchParams(location.search);
      const g = usp.get('g'),
        d = usp.get('d'),
        cap = usp.get('cap');

      if (g && groupSelect?.querySelector(`option[value="${g}"]`)) {
        groupSelect.value = g;
        await onGroupChange();
        if (d && deviceSelect?.querySelector(`option[value="${d}"]`)) {
          deviceSelect.value = d;
          await onDeviceChange();
          if (cap && capSelect?.querySelector(`option[value="${cap}"]`)) {
            capSelect.value = cap;
            await onCapChange();
          }
        }
      }
      syncNextHiddenInputs();
    })();
  });
})();
