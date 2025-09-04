/* home.light-card.js — 燈光卡片渲染 + 輪詢（尊重 2.5s UI hold） */
(() => {
  'use strict';

  const groupSelect = document.getElementById('groupSelect');
  const deviceSelect = document.getElementById('deviceSelect');
  const capSelect = document.getElementById('capSelect');

  // ---- 全域 hold 管理：capId 在 hold 期間不覆寫 switch 狀態 ----
  window.LightUIHold = (function () {
    const map = new Map(); // capId -> expireTs(ms)
    function setHold(capId, ms = 2500) {
      if (!capId) return;
      map.set(String(capId), Date.now() + ms);
    }
    function isHeld(capId) {
      if (!capId) return false;
      const exp = map.get(String(capId));
      if (!exp) return false;
      if (Date.now() > exp) {
        map.delete(String(capId));
        return false;
      }
      return true;
    }
    return { setHold, isHeld };
  })();

  // 速度參數
  const FAST_BURST_MS = 300; // 動作後爆發輪詢間隔
  const FAST_BURST_TICKS = 8; // 動作後快速輪詢次數（~2.4s）
  const AUTO_MS = 900; // 自動模式輪詢
  const HOLD_MS = 2500;
  const IDLE_MS = 5000; // 閒置輪詢

  function shouldApplyRemote(card, remoteTs) {
    const now = Date.now();
    const holdUntil = parseInt(card.dataset.localHoldUntil || '0', 10) || 0;
    const lastAppliedTs = parseFloat(card.dataset.lastAppliedTs || '0') || 0;
    const rts = typeof remoteTs === 'number' ? remoteTs : 0;

    // 還在本地保護期 → 只有伺服器帶「更大的 ts」才覆蓋
    if (now < holdUntil) {
      return rts > lastAppliedTs;
    }
    // 保護期已過 → 沒帶 ts 也允許；若帶 ts，需 >= 目前已知
    if (rts && rts < lastAppliedTs) return false;
    return true;
  }

  // 渲染卡片（尊重 hold）
  function renderLight(card, state) {
    const badge = card.querySelector('#lightBadge');
    const text = card.querySelector('#lightText');
    const spin = card.querySelector('#lightSpinner');

    const isAuto = !!state.auto_light_running;
    const isOn = !!state.light_is_on;

    // ★ 取得 capId 與 hold 狀態
    const capId = card.dataset.capId || '';
    const held = window.LightUIHold?.isHeld(capId);

    // 標章
    badge.classList.remove('bg-success', 'bg-secondary', 'bg-info');
    if (isAuto) {
      badge.classList.add('bg-info');
      badge.textContent = '自動偵測中';
    } else if (isOn) {
      badge.classList.add('bg-success');
      badge.textContent = '啟動';
    } else {
      badge.classList.add('bg-secondary');
      badge.textContent = '關閉';
    }

    // 文案
    text.textContent = isAuto
      ? `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`
      : `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`;

    // spinner：自動或 pending 顯示
    if (spin) {
      const pending = Boolean(state.pending);
      spin.classList.toggle('d-none', !(isAuto || pending));
    }

    // 記錄 isAuto 給輪詢節奏用
    card.dataset.isAuto = isAuto ? '1' : '0';

    // 同步面板內的兩個 switch（★hold 中不覆寫 switch，僅維持手動鎖定）
    if (capId) {
      const autoSwitch = document.getElementById(`autoSwitch-${capId}`);
      const lightSwitch = document.getElementById(`lightSwitch-${capId}`);

      if (autoSwitch && !held) {
        if (autoSwitch.checked !== isAuto) autoSwitch.checked = isAuto;
        if (lightSwitch) lightSwitch.disabled = isAuto; // 自動時鎖手動
      } else if (autoSwitch && held) {
        if (lightSwitch) lightSwitch.disabled = true; // hold 期間先鎖住
      }

      if (lightSwitch && !held) {
        if (lightSwitch.checked !== isOn) lightSwitch.checked = isOn;
      }
    }
  }
  let _lightFetchController = null;
  // 帶競態保護的拉狀態
  async function fetchLightState(card) {
    const url = card.dataset.statusUrl;
    if (!url) return;

    // 取消上一筆還在路上的請求
    if (_lightFetchController) _lightFetchController.abort();
    _lightFetchController = new AbortController();

    const current = (parseInt(card.dataset.reqToken || '0', 10) || 0) + 1;
    card.dataset.reqToken = String(current);

    let data = null;
    try {
      const resp = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        cache: 'no-store', // ← 不使用快取
        signal: _lightFetchController.signal, // ← 可中止
      });
      if (!resp.ok) throw new Error('HTTP_' + resp.status);
      data = await resp.json();
    } catch {
      card.querySelector('#lightSpinner')?.classList.add('d-none');
      return;
    }

    if (card.dataset.reqToken !== String(current)) return;

    // ❶ 本地保護期：剛做完操作的一小段時間，忽略回傳的舊狀態
    const holdUntil = parseInt(card.dataset.localHoldUntil || '0', 10) || 0;
    if (Date.now() < holdUntil) {
      // 還在保護期就別覆蓋 UI，但可以記錄 data 以備用（可選）
      return;
    }

    if (data && data.ok) renderLight(card, data);
    else card.querySelector('#lightSpinner')?.classList.add('d-none');
  }

  function resetLightCard(card, msg = '請先從上方選擇「燈光」能力') {
    const badge = card.querySelector('#lightBadge');
    const text = card.querySelector('#lightText');
    const spin = card.querySelector('#lightSpinner');
    badge.classList.remove('bg-success', 'bg-info');
    badge.classList.add('bg-secondary');
    badge.textContent = '未綁定';
    text.textContent = msg;
    spin?.classList.add('d-none');
    card.dataset.capId = '';
    card.dataset.statusUrl = '';
    card.dataset.reqToken = '0';
    card.dataset.burst = '0';
    card.dataset.isAuto = '0';
  }

  function startLightPolling(card) {
    let timer = null;

    async function tick() {
      try {
        await fetchLightState(card);
      } finally {
        clearTimeout(timer);

        const spinOn = !card
          .querySelector('#lightSpinner')
          ?.classList.contains('d-none');
        const burst = Math.max(0, parseInt(card.dataset.burst || '0', 10) || 0);
        const isAuto = card.dataset.isAuto === '1';

        let next;
        if (burst > 0) {
          next = FAST_BURST_MS;
          card.dataset.burst = String(burst - 1);
        } else if (isAuto || spinOn) {
          next = AUTO_MS;
        } else {
          next = IDLE_MS;
        }
        timer = setTimeout(tick, next);
      }
    }

    tick();
    return () => clearTimeout(timer);
  }

  let stopLightPoll = null;

  function initLightCardFromSelection() {
    const card = document.getElementById('lightCard');
    if (!card) return;

    const sel = capSelect?.selectedOptions?.[0];
    const capId = sel?.value || '';
    const kind = (sel?.dataset?.kind || '').toLowerCase();

    if (!capId || kind !== 'light') {
      if (stopLightPoll) {
        stopLightPoll();
        stopLightPoll = null;
      }
      resetLightCard(card);
      return;
    }

    const g = groupSelect?.value || '';
    const statusUrl =
      `/api/cap/${encodeURIComponent(capId)}/status/` +
      (g ? `?group_id=${encodeURIComponent(g)}` : '');

    card.dataset.capId = capId;
    card.dataset.statusUrl = statusUrl;
    card.dataset.reqToken = '0';
    card.dataset.burst = '0';
    card.dataset.isAuto = '0';

    if (stopLightPoll) {
      stopLightPoll();
      stopLightPoll = null;
    }
    stopLightPoll = startLightPolling(card);
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 切換群組 / 裝置 → 停輪詢 & 重置
    groupSelect?.addEventListener('change', () => {
      if (stopLightPoll) {
        stopLightPoll();
        stopLightPoll = null;
      }
      const card = document.getElementById('lightCard');
      if (card) resetLightCard(card, '請先選擇裝置與功能');
    });
    deviceSelect?.addEventListener('change', () => {
      if (stopLightPoll) {
        stopLightPoll();
        stopLightPoll = null;
      }
      const card = document.getElementById('lightCard');
      if (card) resetLightCard(card, '請先選擇功能');
    });

    // 選到 light → 啟動輪詢
    capSelect?.addEventListener('change', () => {
      initLightCardFromSelection();
    });

    // 首次進來補一次
    setTimeout(() => initLightCardFromSelection(), 0);

    // 用 switch 操作時：開 spinner + 啟動爆發輪詢
    document.addEventListener('change', (evt) => {
      const el = evt.target;
      if (!el.matches('.cap-toggle')) return;

      const card = document.getElementById('lightCard');
      if (!card) return;

      // ❶ 立刻樂觀更新（不等伺服器）
      const isAutoSwitch = !!el.dataset.lockTarget; // 你的自動開關
      const capId = card.dataset.capId || '';
      const autoSwitch = document.getElementById(`autoSwitch-${capId}`);
      const lightSwitch = document.getElementById(`lightSwitch-${capId}`);

      if (isAutoSwitch) {
        // 開/關自動 → 先把手動鎖/解鎖
        if (lightSwitch) lightSwitch.disabled = el.checked;
      } else {
        // 手動燈 → 直接以目前勾選狀態更新 UI（badge、文字）
        const isOn = el.checked;
        const badge = card.querySelector('#lightBadge');
        const text = card.querySelector('#lightText');
        badge.classList.remove('bg-success', 'bg-secondary', 'bg-info');
        if (autoSwitch?.checked) {
          badge.classList.add('bg-info');
          badge.textContent = '自動偵測中';
          text.textContent = `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`;
        } else {
          badge.classList.add(isOn ? 'bg-success' : 'bg-secondary');
          badge.textContent = isOn ? '啟動' : '關閉';
          text.textContent = `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`;
        }
      }

      // ❷ 設定本地保護期（這段期間忽略回來的舊狀態）
      card.dataset.localHoldUntil = String(Date.now() + HOLD_MS);

      // ❸ 開啟爆發輪詢
      card.querySelector('#lightSpinner')?.classList.remove('d-none');
      card.dataset.burst = String(FAST_BURST_TICKS);
      setTimeout(() => fetchLightState(card).catch(() => {}), 120);
    });

    // 隱藏分頁時暫停、回到分頁時重新啟動，避免延遲堆積
    document.addEventListener('visibilitychange', () => {
      const card = document.getElementById('lightCard');
      if (!card) return;
      if (document.hidden) {
        if (stopLightPoll) {
          stopLightPoll();
          stopLightPoll = null;
        }
      } else {
        initLightCardFromSelection();
      }
    });
  });
})();
