/* home.controls.js — 手動/自動燈控制（switch 送指令） */
(() => {
  'use strict';

  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
  }
  const csrftoken = getCookie('csrftoken') || window.App?.getCsrf?.() || '';

  async function post(url, body) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrftoken,
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body,
    });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return resp;
  }

  function setManualLockedByAuto(autoEl, locked) {
    const sel = autoEl.dataset.lockTarget;
    if (!sel) return;
    const lightEl = document.querySelector(sel);
    if (!lightEl) return;
    lightEl.disabled = !!locked;
    lightEl.setAttribute('aria-disabled', locked ? 'true' : 'false');
  }

  // 處理電子鎖按鈕點擊
  document.addEventListener('click', async (evt) => {
    const el = evt.target.closest('.locker-btn');
    if (!el) return;

    console.log('電子鎖按鈕被點擊:', el.id, el.dataset);
    
    el.disabled = true; // 防止連點
    const url = el.dataset.url;
    const fd = new FormData();
    if (el.dataset.group) fd.append('group_id', el.dataset.group);
    if (el.dataset.next !== undefined) fd.append('next', el.dataset.next);

    console.log('發送請求到:', url, 'group_id:', el.dataset.group);

    try {
      const response = await post(url, fd);
      console.log('請求成功:', response);
    } catch (e) {
      console.error('請求失敗:', e);
      alert('操作失敗，請再試一次：' + e.message);
    } finally {
      el.disabled = false;
    }
  });

  document.addEventListener('change', async (evt) => {
    const el = evt.target;
    if (!el.matches('.cap-toggle')) return;

    // 若手動燈對應自動已開，阻擋
    if (el.dataset.auto) {
      const autoEl = document.querySelector(el.dataset.auto);
      if (autoEl && autoEl.checked) {
        el.checked = !el.checked;
        alert('已啟用自動模式，請先停用自動再手動操作燈。');
        return;
      }
    }

    el.disabled = true; // 防止連點
    const url = el.checked ? el.dataset.onUrl : el.dataset.offUrl;
    const fd = new FormData();
    if (el.dataset.group) fd.append('group_id', el.dataset.group);
    if (el.dataset.next !== undefined) fd.append('next', el.dataset.next);
    if (el.dataset.sensor) fd.append('sensor', el.dataset.sensor);
    if (el.dataset.led) fd.append('led', el.dataset.led);

    try {
      await post(url, fd);
      if (el.dataset.lockTarget) setManualLockedByAuto(el, el.checked);
    } catch (e) {
      const was = !el.checked;
      el.checked = was;
      if (el.dataset.lockTarget) setManualLockedByAuto(el, was);
      alert('操作失敗，請再試一次：' + e.message);
    } finally {
      el.disabled = false;
    }
  });
})();
