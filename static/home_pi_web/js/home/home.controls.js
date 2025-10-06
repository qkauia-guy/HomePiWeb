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

  // 處理電子鎖按鈕點擊（舊版按鈕）
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
      
      // 檢查回應是否為 JSON 格式
      const ct = response.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const data = await response.json();
        App.showMessagesFromJson(data);
      } else if (response.ok) {
        // 顯示成功訊息
        const action = el.id.includes('unlock') ? '開鎖' : '上鎖';
        App.toast(`電子鎖${action}成功`, true);
      }
      
      // 觸發狀態卡片更新
      setTimeout(() => {
        if (window.HomeUI?.triggerStatusUpdate) {
          window.HomeUI.triggerStatusUpdate();
        }
        // 也嘗試初始化狀態卡片
        if (window.initStatusCards) {
          window.initStatusCards();
        }
      }, 50); // 縮短延遲
    } catch (e) {
      console.error('請求失敗:', e);
      const action = el.id.includes('unlock') ? '開鎖' : '上鎖';
      App.toast(`電子鎖${action}失敗：${e.message}`, false);
    } finally {
      el.disabled = false;
    }
  });

  document.addEventListener('change', async (evt) => {
    const el = evt.target;
    if (!el.matches('.cap-toggle, .locker-toggle')) return;

    // 電子鎖開關特殊處理
    if (el.matches('.locker-toggle')) {
      el.disabled = true; // 防止連點
      // 電子鎖邏輯：checked = 開鎖，unchecked = 上鎖
      const url = el.checked ? el.dataset.unlockUrl : el.dataset.lockUrl;
      const fd = new FormData();
      if (el.dataset.group) fd.append('group_id', el.dataset.group);
      if (el.dataset.next !== undefined) fd.append('next', el.dataset.next);

      try {
        const resp = await post(url, fd);
        
        // 檢查回應是否為 JSON 格式
        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('application/json')) {
          const data = await resp.json();
          App.showMessagesFromJson(data);
        } else if (resp.ok) {
          // 顯示成功訊息
          const action = el.checked ? '開鎖' : '上鎖';
          App.toast(`電子鎖${action}成功`, true);
        }
        
        // 更新狀態文字和圖示（支援桌面版和手機版）
        const statusContainers = document.querySelectorAll('#lockerCard .text-muted .lock-status-text');
        const icons = document.querySelectorAll('#lockerCard .text-muted i');
        
        // 更新所有狀態文字
        statusContainers.forEach(statusText => {
          statusText.textContent = el.checked ? '已開鎖' : '已上鎖';
        });
        
        // 更新所有圖示
        icons.forEach(icon => {
          icon.className = `bi bi-${el.checked ? 'unlock' : 'lock'} me-1`;
        });
        
        // 同步其他開關狀態
        const allToggles = document.querySelectorAll('#lockerCard .locker-toggle');
        allToggles.forEach(toggle => {
          if (toggle !== el) {
            toggle.checked = el.checked;
          }
        });
        
        // 觸發狀態卡片更新
        setTimeout(() => {
          if (window.HomeUI?.triggerStatusUpdate) {
            window.HomeUI.triggerStatusUpdate();
          }
          if (window.initStatusCards) {
            window.initStatusCards();
          }
        }, 50);
      } catch (e) {
        const was = !el.checked;
        el.checked = was;
        const action = el.checked ? '開鎖' : '上鎖';
        App.toast(`電子鎖${action}失敗：${e.message}`, false);
      } finally {
        el.disabled = false;
      }
      return; // 電子鎖處理完畢，不執行下面的燈泡邏輯
    }

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
      
             // 觸發狀態卡片更新
             setTimeout(() => {
               if (window.HomeUI?.triggerStatusUpdate) {
                 window.HomeUI.triggerStatusUpdate();
               }
               // 也嘗試初始化狀態卡片
               if (window.initStatusCards) {
                 window.initStatusCards();
               }
             }, 50); // 縮短延遲
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
