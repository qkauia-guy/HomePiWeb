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
      err.redirect = dest.pathname;
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

  // ===== 導出到全域（給其他頁用）=====
  window.App = Object.assign(window.App || {}, {
    getCsrf,
    toast,
    fetchText,
    postForm,
    showMessagesFromJson,
    paths: { LOGIN_PATH, GROUP_CREATE_PATH },
  });
})();
