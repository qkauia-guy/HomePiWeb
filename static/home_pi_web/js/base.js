/* base.js — 全站共用工具與委派事件 */
(() => {
  'use strict';

  // ===== 基本設定（由後端可注入 APP_URLS） =====
  const APP = window.APP_URLS || {};
  const LOGIN_PATH = safePath(APP.login || '/accounts/login/');
  const GROUP_CREATE_PATH = safePath(APP.groupCreate || '/groups/create/');

  function safePath(u) {
    try {
      return new URL(u, window.location.origin).pathname;
    } catch {
      return u;
    }
  }

  // ===== CSRF / Cookie =====
  function getCookie(name) {
    const m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]+)'));
    return m ? decodeURIComponent(m[2]) : null;
  }
  function getCsrf() {
    return (
      getCookie('csrftoken') ||
      document.querySelector('input[name=csrfmiddlewaretoken]')?.value ||
      ''
    );
  }

  // ===== Toast（Bootstrap 5 友善；沒有 BS 也能用） =====
  function ensureToastContainer() {
    let c = document.getElementById('toast-container');
    if (!c) {
      c = document.createElement('div');
      c.id = 'toast-container';
      c.className = 'toast-container position-fixed top-0 end-0 p-3';
      c.style.zIndex = 1080;
      document.body.appendChild(c);
    }
    return c;
  }

  function toast(msg, ok = true) {
    const c = ensureToastContainer();
    const el = document.createElement('div');
    el.className =
      'toast align-items-center text-white ' +
      (ok ? 'bg-success' : 'bg-danger') +
      ' show';
    el.role = 'alert';
    el.style.minWidth = '220px';
    el.style.marginBottom = '8px';
    el.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">${msg}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close"></button>
      </div>`;
    el.querySelector('.btn-close').addEventListener('click', () => el.remove());
    c.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  // ===== 共用 fetch 工具 =====
  async function fetchText(url) {
    const resp = await fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    });

    // 中央處理 401/403/302
    if (resp.status === 401) {
      const err = new Error('unauth');
      err.code = 'auth';
      throw err;
    }
    if (resp.status === 403) {
      try {
        const data = await resp.clone().json();
        if (data?.error === 'group_required') {
          const err = new Error('group required');
          err.code = 'group_required';
          err.redirect = data.redirect;
          throw err;
        }
      } catch {}
      const err = new Error('forbidden');
      err.code = 'forbidden';
      throw err;
    }
    if (resp.redirected) {
      // 後端仍可能重導（保險）
      const dest = new URL(resp.url, window.location.origin);
      const err = new Error('redirect');
      err.code =
        dest.pathname === LOGIN_PATH
          ? 'auth'
          : dest.pathname === GROUP_CREATE_PATH
          ? 'group_required'
          : 'redirect';
      // 清理 URL 中的 hash 片段
      err.redirect = dest.pathname + dest.search;
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

  async function postForm(url, formData) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCsrf(),
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: formData,
    });
    return resp;
  }

  function showMessagesFromJson(json) {
    const msgs = Array.isArray(json?.messages) ? json.messages : [];
    if (msgs.length) {
      msgs.forEach((m) =>
        toast(m.message, m.level !== 'error' && m.level !== 'danger')
      );
    } else if (json?.message) {
      toast(json.message, json.ok !== false);
    } else {
      toast(json?.ok === false ? '操作失敗' : '已完成', json?.ok !== false);
    }
  }

  // ===== Offcanvas lazy-load（共用）=====
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.offcanvas').forEach((oc) => {
      oc.addEventListener('show.bs.offcanvas', async () => {
        const body = oc.querySelector('.offcanvas-body[data-load-url]');
        if (!body || body.dataset.loaded === '1') return;

        const url = body.dataset.loadUrl || body.getAttribute('data-load-url');
        if (!url) {
          body.innerHTML = '<div class="text-danger">未設定載入位址</div>';
          return;
        }
        body.innerHTML = '<div class="text-muted">載入中…</div>';

        try {
          const html = await fetchText(url);
          body.innerHTML = html;
          body.dataset.loaded = '1';
          // console.log("[offcanvas] loaded:", url);
        } catch (e) {
          console.error('[offcanvas] fetch error:', e);
          const map = {
            auth: '請先登入',
            group_required: '你尚未加入任何群組，請先建立群組。',
            forbidden: '無權限',
          };
          body.innerHTML = `<div class="text-danger">${
            map[e?.code] || '載入失敗'
          }</div>`;
        }
      });
    });
  });

  // ===== 委派：cap-toggle（燈／自動）全站可用 =====
  document.addEventListener('change', async (evt) => {
    const el = evt.target;
    if (!el.matches('.cap-toggle')) return;

    const url = el.checked ? el.dataset.onUrl : el.dataset.offUrl;
    const fd = new FormData();
    if (el.dataset.group) fd.append('group_id', el.dataset.group);
    if (el.dataset.next !== undefined) fd.append('next', el.dataset.next);
    if (el.dataset.sensor) fd.append('sensor', el.dataset.sensor);
    if (el.dataset.led) fd.append('led', el.dataset.led);

    el.disabled = true;
    try {
      const resp = await postForm(url, fd);
      const ct = resp.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        const data = await resp.json();
        showMessagesFromJson(data);
        // 若後端回來當前狀態，可在這裡同步 UI：e.g. el.checked = !!data.light_is_on;
      } else if (resp.ok) {
        toast(el.checked ? '已開' : '已關');
      } else {
        throw new Error('HTTP ' + resp.status);
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
      el.checked = !el.checked; // 復原
      toast('操作失敗，請再試一次：' + (e?.message || e), false);
    } finally {
      el.disabled = false;
    }
  });

  // ===== URL 清理工具 =====
  function cleanUrl(url) {
    try {
      const parsed = new URL(url, window.location.origin);
      return parsed.pathname + parsed.search;
    } catch {
      return url;
    }
  }

  // ===== 自動打開 offcanvas 功能 =====
  function openOffcanvasIfNeeded() {
    // 檢查 URL 中是否有 #sideBar 或 #sideBarGroups
    const hash = window.location.hash;
    if (hash === '#sideBar') {
      const offcanvas = document.getElementById('sideBar');
      if (offcanvas) {
        const bsOffcanvas = new bootstrap.Offcanvas(offcanvas);
        bsOffcanvas.show();
        // 清理 URL
        history.replaceState(null, null, window.location.pathname + window.location.search);
      }
    } else if (hash === '#sideBarGroups') {
      const offcanvas = document.getElementById('sideBarGroups');
      if (offcanvas) {
        const bsOffcanvas = new bootstrap.Offcanvas(offcanvas);
        bsOffcanvas.show();
        // 清理 URL
        history.replaceState(null, null, window.location.pathname + window.location.search);
      }
    }
  }

  // 頁面載入時檢查是否需要打開 offcanvas
  document.addEventListener('DOMContentLoaded', openOffcanvasIfNeeded);

  // ===== 裝置編輯 SweetAlert 功能 =====
  function openDeviceEditModal(deviceId, currentName, serialNumber) {
    // 檢查是否為黑暗模式
    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
    
    Swal.fire({
      title: '<i class="fas fa-edit me-2"></i>編輯裝置',
      html: `
        <div class="text-start">
          <div class="mb-3">
            <label class="form-label">
              <i class="fas fa-microchip me-1"></i>
              序號：${serialNumber}
            </label>
          </div>
          <div class="mb-3">
            <label for="device-name" class="form-label">
              <i class="fas fa-tag me-2"></i>
              裝置名稱
            </label>
            <input type="text" 
                   id="device-name" 
                   class="form-control" 
                   value="${currentName || ''}"
                   placeholder="請輸入裝置名稱">
            <div class="form-text">
              <i class="fas fa-info-circle me-1"></i>
              留空則顯示序號。
            </div>
          </div>
        </div>
      `,
      showCancelButton: true,
      confirmButtonText: '<i class="fas fa-save me-2"></i>儲存',
      cancelButtonText: '<i class="fas fa-times me-2"></i>取消',
      confirmButtonColor: '#3085d6',
      cancelButtonColor: '#6c757d',
      width: '400px',
      // 毛玻璃背景樣式
      background: isDarkMode ? 'rgba(30, 41, 59, 0.7)' : 'rgba(255, 255, 255, 0.7)',
      backdrop: `
        ${isDarkMode ? 'blur(20px) saturate(180%)' : 'blur(10px)'}
      `,
      customClass: {
        popup: 'swal2-popup-glass',
        title: 'swal2-title-glass',
        content: 'swal2-content-glass',
        confirmButton: 'swal2-confirm-glass',
        cancelButton: 'swal2-cancel-glass'
      },
      preConfirm: () => {
        const name = document.getElementById('device-name').value.trim();
        
        return {
          name: name
        };
      }
    }).then((result) => {
      if (result.isConfirmed) {
        saveDeviceEdit(deviceId, result.value);
      }
    });
  }

  function saveDeviceEdit(deviceId, data) {
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrf());
    formData.append('display_name', data.name);
    
    fetch(`/devices/${deviceId}/edit/`, {
      method: 'POST',
      body: formData,
      headers: {
        'X-CSRFToken': getCsrf(),
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        Swal.fire({
          icon: 'success',
          title: '儲存成功！',
          text: '裝置資訊已更新',
          timer: 2000,
          showConfirmButton: false
        }).then(() => {
          // 重新載入頁面以更新顯示
          window.location.reload();
        });
      } else {
        console.error('儲存失敗:', data);
        Swal.fire({
          icon: 'error',
          title: '儲存失敗',
          text: data.message || '請稍後再試',
          footer: data.debug ? '<small>詳細錯誤請查看控制台</small>' : ''
        });
      }
    })
    .catch(error => {
      console.error('Error:', error);
      Swal.fire({
        icon: 'error',
        title: '儲存失敗',
        text: '網路錯誤，請稍後再試'
      });
    });
  }

  // 綁定裝置項目點擊事件
  document.addEventListener('DOMContentLoaded', function() {
    // 使用事件委派處理動態載入的內容
    document.addEventListener('click', function(event) {
      const deviceItem = event.target.closest('.device-item');
      if (deviceItem) {
        const href = deviceItem.getAttribute('href');
        
        // 檢查是否為編輯頁面連結
        if (href && href.includes('/edit/')) {
          event.preventDefault();
          
          // 從 href 中提取裝置 ID
          const deviceId = href.match(/\/devices\/(\d+)\/edit\//)?.[1];
          if (!deviceId) return;
          
          // 獲取當前裝置名稱
          const nameElement = deviceItem.querySelector('.fw-semibold');
          const currentName = nameElement ? nameElement.textContent.trim() : '';
          
          // 獲取序號（從 IP 或其他地方，這裡先使用裝置 ID）
          const serialElement = deviceItem.querySelector('.text-monospace');
          const serialNumber = serialElement ? serialElement.textContent.trim() : `PI-${deviceId}`;
          
          // 打開編輯模態框
          openDeviceEditModal(deviceId, currentName, serialNumber);
        }
      }
    });
  });

  // ===== 導出到全域（給其他頁用）=====
  window.App = Object.assign(window.App || {}, {
    getCsrf,
    toast,
    fetchText,
    postForm,
    showMessagesFromJson,
    cleanUrl,
    openOffcanvasIfNeeded,
    paths: { LOGIN_PATH, GROUP_CREATE_PATH },
  });
})();
