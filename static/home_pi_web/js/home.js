/* home.js — Home 頁面行為（選單載入、表單 AJAX） */
(() => {
  'use strict';

  document.addEventListener('DOMContentLoaded', () => {
    // 啟用 tooltip（若有 Bootstrap）
    if (window.bootstrap?.Tooltip) {
      [...document.querySelectorAll("[data-bs-toggle='tooltip']")].forEach(
        (el) => new bootstrap.Tooltip(el)
      );
    }

    const groupSelect = document.getElementById('groupSelect');
    const deviceSelect = document.getElementById('deviceSelect');
    const capSelect = document.getElementById('capSelect');
    const capForms = document.getElementById('capForms');
    const formPlaceholder = document.getElementById('formPlaceholder');
    const ajaxMsg = document.getElementById('ajaxMsg'); // 若沒有就用 toast

    function showBanner(kind, text) {
      if (!ajaxMsg) return App.toast(text, kind === 'success');
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
      const params = new URLSearchParams();
      if (groupSelect?.value) params.set('g', groupSelect.value);
      if (deviceSelect?.value) params.set('d', deviceSelect.value);
      if (capSelect?.value) params.set('cap', capSelect.value);
      return (window.HOME_URL || '/') + (params.toString() ? `?${params}` : '');
    }

    function syncNextHiddenInputs() {
      const nextUrl = buildNextUrl();
      capForms
        ?.querySelectorAll('form.cap-form input[name="next"]')
        .forEach((inp) => (inp.value = nextUrl));
      capForms
        ?.querySelectorAll('form.cap-form input[name="group_id"]')
        .forEach((inp) => {
          const gval = (groupSelect?.value || '').trim();
          if (gval) inp.value = gval;
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
      showBanner(
        e?.code === 'auth'
          ? 'danger'
          : e?.code === 'group_required'
          ? 'warning'
          : 'danger',
        msg
      );
    }

    // --- 載入流程 ---
    async function onGroupChange() {
      resetSelect(deviceSelect, '請選擇裝置');
      resetSelect(capSelect, '請選擇功能');
      if (capForms) capForms.innerHTML = '';
      if (formPlaceholder) formPlaceholder.hidden = false;

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
      if (formPlaceholder) formPlaceholder.hidden = false;

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
      if (formPlaceholder) formPlaceholder.hidden = !capSelect?.value;
      if (!capSelect?.value) return;
      try {
        const html = await App.fetchText(
          `/controls/cap-form/${encodeURIComponent(
            capSelect.value
          )}/?group_id=${encodeURIComponent(groupSelect.value || '')}`
        );
        capForms.innerHTML = html;
        if (formPlaceholder) formPlaceholder.hidden = true;
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

        if (resp.status === 401) {
          showBanner('danger', '請先登入');
          return;
        }
        if (resp.status === 403) {
          try {
            const data = await resp.clone().json();
            if (data?.error === 'group_required') {
              showBanner('warning', '你尚未加入任何群組，請先建立群組。');
              return;
            }
          } catch {}
          showBanner('danger', '無權限');
          return;
        }

        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const data = await resp.json();
          App.showMessagesFromJson(data);
        } else if (resp.ok) {
          showBanner('success', '已送出指令。');
        } else {
          // 非 200 時保險導回
          window.location.href = nextUrl;
        }
      } catch (err) {
        showBanner('danger', '送出失敗，請稍後再試。');
      }
    });

    // 依 URL 參數自動恢復選擇
    (async function initFromParams() {
      const usp = new URLSearchParams(location.search);
      const g = usp.get('g');
      const d = usp.get('d');
      const cap = usp.get('cap');

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

(function () {
  function getCookie(name) {
    const match = document.cookie.match(
      new RegExp('(^|; )' + name + '=([^;]+)')
    );
    return match ? decodeURIComponent(match[2]) : null;
  }
  const csrftoken = getCookie('csrftoken');

  async function post(url, body) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrftoken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      body,
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp;
  }

  // 小工具：依 auto 開關狀態鎖/解鎖手動燈
  function setManualLockedByAuto(autoEl, locked) {
    const sel = autoEl.dataset.lockTarget;
    if (!sel) return;
    const lightEl = document.querySelector(sel);
    if (!lightEl) return;
    lightEl.disabled = !!locked;
    lightEl.setAttribute('aria-disabled', locked ? 'true' : 'false');
  }

  document.addEventListener('change', async function (evt) {
    const el = evt.target;
    if (!el.matches('.cap-toggle')) return;

    // ❶ 若是手動燈且對應的自動已開，直接阻擋並復原
    if (el.dataset.auto) {
      const autoEl = document.querySelector(el.dataset.auto);
      if (autoEl && autoEl.checked) {
        el.checked = !el.checked; // 還原使用者剛剛的點擊
        alert('已啟用自動模式，請先停用自動再手動操作燈。');
        return;
      }
    }

    // 送出請求
    el.disabled = true; // 防止連點
    const url = el.checked ? el.dataset.onUrl : el.dataset.offUrl;
    const fd = new FormData();
    if (el.dataset.group) fd.append('group_id', el.dataset.group);
    if (el.dataset.next !== undefined) fd.append('next', el.dataset.next);
    if (el.dataset.sensor) fd.append('sensor', el.dataset.sensor);
    if (el.dataset.led) fd.append('led', el.dataset.led);

    try {
      await post(url, fd);

      // ❷ 若是「自動」開關成功，依其狀態鎖/解鎖手動燈
      if (el.dataset.lockTarget) {
        setManualLockedByAuto(el, el.checked);
      }
    } catch (e) {
      // 失敗：復原 UI；若是自動開關也恢復鎖定狀態
      const was = !el.checked;
      el.checked = was;
      if (el.dataset.lockTarget) {
        setManualLockedByAuto(el, was);
      }
      alert('操作失敗，請再試一次：' + e.message);
    } finally {
      el.disabled = false;
    }
  });
})();
