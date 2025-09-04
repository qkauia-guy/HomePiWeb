/* home.schedule.js — 開/關排程 + 顯示下一次開/關（卡片與表單預填 + 到點自動還原） */
(() => {
  'use strict';

  // ========================
  // 工具：時間格式/顯示訊息
  // ========================
  function epochToLocalInput(ts) {
    const d = new Date(ts * 1000);
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
      d.getDate()
    )}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function epochToPrettyLocal(ts) {
    const d = new Date(ts * 1000);
    if (Number.isNaN(d.getTime())) return ' 未排程 ';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(
      d.getDate()
    )} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function localToISOWithOffset(localStr) {
    if (!localStr) return null;
    const d = new Date(localStr);
    if (Number.isNaN(d.getTime())) return null;
    const pad = (n) => String(n).padStart(2, '0');
    const y = d.getFullYear(),
      mo = pad(d.getMonth() + 1),
      da = pad(d.getDate());
    const h = pad(d.getHours()),
      m = pad(d.getMinutes()),
      s = pad(d.getSeconds());
    const offMin = -d.getTimezoneOffset(); // +480 for Taipei
    const sign = offMin >= 0 ? '+' : '-';
    const abs = Math.abs(offMin);
    const oh = pad(Math.floor(abs / 60)),
      om = pad(abs % 60);
    return `${y}-${mo}-${da}T${h}:${m}:${s}${sign}${oh}:${om}`;
  }

  function showSchedMsg(form, text, isError = false) {
    const capId = (form.id && form.id.split('-')[1]) || '';
    const okEl =
      document.getElementById(`schedMsg-${capId}`) ||
      form.querySelector('.text-success');
    const errEl =
      document.getElementById(`schedErr-${capId}`) ||
      form.querySelector('.text-danger');
    if (okEl) {
      okEl.classList.add('d-none');
      okEl.textContent = '';
    }
    if (errEl) {
      errEl.classList.add('d-none');
      errEl.textContent = '';
    }
    const el = isError ? errEl || okEl : okEl || errEl;
    if (el) {
      el.textContent = text;
      el.classList.remove('d-none');
    } else {
      // 後備 banner（若你的專案有 HomeUI.showBanner）
      window.HomeUI?.showBanner?.(isError ? 'danger' : 'success', text);
    }
  }

  function setSchedText(form, which /* 'on' | 'off' */, text, extraClass = '') {
    const capId = (form.id && form.id.split('-')[1]) || '';
    const onEl =
      document.getElementById(`schedOnText-${capId}`) ||
      document.getElementById('schedOnText');
    const offEl =
      document.getElementById(`schedOffText-${capId}`) ||
      document.getElementById('schedOffText');

    const el = which === 'on' ? onEl : offEl;
    if (el) {
      el.textContent = text;
      el.classList.remove(
        'text-muted',
        'text-success',
        'text-danger',
        'fw-semibold'
      );
      if (extraClass) el.classList.add(...extraClass.split(' '));
    }
  }

  function flashExecuted(form, which) {
    // 顯示「已執行 ✓」
    setSchedText(form, which, ' 已執行 ✓ ', 'text-success fw-semibold');
    // 廣播事件（如果其他區塊想要跟著更新 UI）
    document.dispatchEvent(
      new CustomEvent('schedule:executed', { detail: { form, which } })
    );
  }

  // ========================
  // 工具：到點自動清除 & 計時器管理
  // ========================
  function clearTimersForForm(form) {
    const onTid = form._schedOnTimer;
    const offTid = form._schedOffTimer;
    if (onTid) {
      clearTimeout(onTid);
      form._schedOnTimer = null;
    }
    if (offTid) {
      clearTimeout(offTid);
      form._schedOffTimer = null;
    }
  }

  function clearWhenPassed(form, which /* 'on' | 'off' */, atTs /* seconds */) {
    if (!atTs) return;
    const nowSec = Math.floor(Date.now() / 1000);
    const delayMs = Math.max(0, (atTs - nowSec) * 1000) + 200; // +200ms 緩衝

    const doOnDue = async () => {
      // 1) 到點顯示「已執行」
      flashExecuted(form, which);

      // 2) 3 秒後拉一次 upcoming，讓 UI 進入下一筆
      setTimeout(async () => {
        await window.HomeSchedule?.fetchAndRenderUpcoming?.(form);

        // 3) 若後端沒有下一筆 → 保持預設「未排程」
        const capId = (form.id && form.id.split('-')[1]) || '';
        const onEl =
          document.getElementById(`schedOnText-${capId}`) ||
          document.getElementById('schedOnText');
        const offEl =
          document.getElementById(`schedOffText-${capId}`) ||
          document.getElementById('schedOffText');

        if (
          which === 'on' &&
          onEl &&
          (!onEl.textContent || /未排程/.test(onEl.textContent))
        ) {
          setSchedText(form, 'on', ' 未排程 ', 'text-muted');
        }
        if (
          which === 'off' &&
          offEl &&
          (!offEl.textContent || /未排程/.test(offEl.textContent))
        ) {
          setSchedText(form, 'off', ' 未排程 ', 'text-muted');
        }
      }, 3000);
    };

    const tid = setTimeout(doOnDue, delayMs);
    if (which === 'on') form._schedOnTimer = tid;
    else form._schedOffTimer = tid;
  }

  // ========================
  // 讀取 & 渲染 upcoming
  // ========================
  async function fetchAndRenderUpcoming(form) {
    clearTimersForForm(form);

    const upcomingUrl = form?.dataset?.upcomingUrl || '';
    const slug =
      form?.dataset?.slug ||
      form?.querySelector('input[name=slug]')?.value ||
      '';
    if (!upcomingUrl) return;

    const url = upcomingUrl + (slug ? `?slug=${encodeURIComponent(slug)}` : '');
    let data = null;
    try {
      const resp = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!resp.ok) throw new Error(`HTTP_${resp.status}`);
      data = await resp.json();
    } catch {
      return;
    }
    if (!data?.ok) return;

    const capId = (form.id && form.id.split('-')[1]) || '';
    const onEl =
      document.getElementById(`schedOnText-${capId}`) ||
      document.getElementById('schedOnText');
    const offEl =
      document.getElementById(`schedOffText-${capId}`) ||
      document.getElementById('schedOffText');

    const nextOnTs = data.next_on?.ts ?? null;
    const nextOffTs = data.next_off?.ts ?? null;

    if (onEl)
      setSchedText(
        form,
        'on',
        nextOnTs ? epochToPrettyLocal(nextOnTs) : ' 未排程 ',
        nextOnTs ? '' : 'text-muted'
      );
    if (offEl)
      setSchedText(
        form,
        'off',
        nextOffTs ? epochToPrettyLocal(nextOffTs) : ' 未排程 ',
        nextOffTs ? '' : 'text-muted'
      );

    // 表單預填（只有空白時才填）
    const onInput = form.querySelector('input[name=on_at_local]');
    const offInput = form.querySelector('input[name=off_at_local]');
    if (onInput && !onInput.value && nextOnTs)
      onInput.value = epochToLocalInput(nextOnTs);
    if (offInput && !offInput.value && nextOffTs)
      offInput.value = epochToLocalInput(nextOffTs);

    // 設定到點自動清除 & 重新抓取
    if (nextOnTs) clearWhenPassed(form, 'on', nextOnTs);
    if (nextOffTs) clearWhenPassed(form, 'off', nextOffTs);
  }

  // 導出給其他模組使用（例如 home.init.js）
  window.HomeSchedule = { fetchAndRenderUpcoming };

  // ========================
  // 建立排程（只排開 / 只排關 / 同時排）
  // ========================
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest(
      '[data-submit-on],[data-submit-off],[data-submit-both]'
    );
    if (!btn) return;

    const formSel =
      btn.getAttribute('data-submit-on') ||
      btn.getAttribute('data-submit-off') ||
      btn.getAttribute('data-submit-both');
    const f = document.querySelector(formSel);
    if (!f) return;

    e.preventDefault();

    const createUrl = f.getAttribute('data-create-url');
    const onLocal = (
      f.querySelector('[name="on_at_local"]')?.value || ''
    ).trim();
    const offLocal = (
      f.querySelector('[name="off_at_local"]')?.value || ''
    ).trim();

    // 哪一顆？
    const wantOn = btn.hasAttribute('data-submit-on');
    const wantOff = btn.hasAttribute('data-submit-off');
    const wantBoth = btn.hasAttribute('data-submit-both');

    // 「同時排」時：若只填一個，就只排那一個；兩個都空才報錯
    const doOn = wantOn || (wantBoth && !!onLocal);
    const doOff = wantOff || (wantBoth && !!offLocal);

    if (!doOn && !doOff) {
      return showSchedMsg(f, '請至少填一個時間（開燈或關燈）', true);
    }

    // 轉成 ISO。後端已支援 on_at_iso/off_at_iso（建議用 localToISOWithOffset）
    const toISO = (s) => (s ? localToISOWithOffset(s) : null);

    const fd = new FormData(f);
    fd.delete('on_at_local');
    fd.delete('off_at_local');
    if (doOn) fd.append('on_at_iso', toISO(onLocal));
    if (doOff) fd.append('off_at_iso', toISO(offLocal));

    try {
      const resp = await fetch(createUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCsrf(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: fd,
        credentials: 'same-origin',
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error(data?.error || `HTTP ${resp.status}`);
      }

      showSchedMsg(f, '排程已建立', false);

      // 立刻刷新這一張表單的 upcoming
      await fetchAndRenderUpcoming(f);

      // 廣播給其他區塊（若需要）
      document.dispatchEvent(
        new CustomEvent('schedule:created', {
          detail: { created: data.created || [] },
        })
      );
    } catch (err) {
      showSchedMsg(f, '建立排程失敗：' + err.message, true);
    }
  });

  function getCsrf() {
    const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  // ========================
  // 表單載入完成 → 自動抓一次
  // ========================
  document.addEventListener('cap-form-loaded', (ev) => {
    const form = ev.detail?.form;
    if (form) fetchAndRenderUpcoming(form);
  });

  // 建立排程成功（其他地方觸發）→ 全部排程表單刷新
  document.addEventListener('schedule:created', () => {
    document.querySelectorAll("form[id^='schedForm-']").forEach((f) => {
      fetchAndRenderUpcoming(f);
    });
  });

  // 可見性切換：回到分頁時刷新
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      document.querySelectorAll("form[id^='schedForm-']").forEach((f) => {
        fetchAndRenderUpcoming(f);
      });
    }
  });
})();
