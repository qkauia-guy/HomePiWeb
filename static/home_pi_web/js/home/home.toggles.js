/* home.toggles.js — 切換手動/自動的前端行為（含 2.5s UI hold） */
(function () {
  'use strict';

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
      credentials: 'same-origin',
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

  // 從元素 id 推 capId（e.g., autoSwitch-123 → 123）
  function getCapIdFromEl(el) {
    const id = el.id || '';
    const idx = id.lastIndexOf('-');
    return idx >= 0 ? id.slice(idx + 1) : '';
  }

  document.addEventListener('change', async function (evt) {
    const el = evt.target;
    if (!el.matches('.cap-toggle')) return;

    // 若是手動燈且對應的自動已開，阻擋並復原
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

      // 若是「自動」開關成功，依其狀態鎖/解鎖手動燈
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

      // ★ 新增：設定 2.5 秒的 UI hold，避免輪詢把剛剛的切換覆寫
      const capId = getCapIdFromEl(el);
      if (window.LightUIHold?.setHold) {
        window.LightUIHold.setHold(capId, 2500);
      }
    }
  });
})();
