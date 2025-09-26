/* home.locker-card.js — 電子鎖卡片渲染 + 輪詢（尊重 2.5s UI hold） */
(() => {
  'use strict';

  const groupSelect = document.getElementById('groupSelect');
  const deviceSelect = document.getElementById('deviceSelect');
  const capSelect = document.getElementById('capSelect');

  // ---- 全域 hold 管理：capId 在 hold 期間不覆寫 switch 狀態 ----
  window.LockerUIHold = (function () {
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
  function renderLocker(card, state) {
    const badge = card.querySelector('#lockerBadge');
    const text = card.querySelector('#lockerText');
    const spin = card.querySelector('#lockerSpinner');

    const isLocked = !!state.locked;
    const autoLockRunning = !!state.auto_lock_running;

    // ★ 取得 capId 與 hold 狀態
    const capId = card.dataset.capId || '';
    const held = window.LockerUIHold?.isHeld(capId);

    // 標章
    badge.classList.remove('bg-success', 'bg-secondary', 'bg-warning');
    if (isLocked) {
      badge.classList.add('bg-secondary');
      badge.textContent = '已上鎖';
    } else {
      badge.classList.add('bg-success');
      badge.textContent = '已開鎖';
    }

    // 文案
    if (autoLockRunning) {
      text.textContent = `目前狀態：已開鎖（${
        isLocked ? '上鎖中' : '開鎖中'
      }）`;
    } else {
      text.textContent = `目前狀態：${isLocked ? '已上鎖🔒' : '已開鎖🔓'}`;
    }

    // 更新狀態文字
    const statusText = card.querySelector('#lockerStatusText');
    const autoText = card.querySelector('#lockerAutoText');
    if (statusText) {
      statusText.textContent = isLocked ? '已上鎖' : '已開鎖';
    }
    if (autoText) {
      autoText.textContent = autoLockRunning ? '啟用中' : '未啟用';
    }

    // spinner：pending 顯示
    if (spin) {
      const pending = Boolean(state.pending);
      spin.classList.toggle('d-none', !pending);
    }

    // 記錄狀態給輪詢節奏用
    card.dataset.isLocked = isLocked ? '1' : '0';
    card.dataset.autoLockRunning = autoLockRunning ? '1' : '0';

    // 同步面板內的按鈕（★hold 中不覆寫按鈕狀態）
    if (capId) {
      const lockBtn = document.getElementById(`lockBtn-${capId}`);
      const unlockBtn = document.getElementById(`unlockBtn-${capId}`);
      const toggleBtn = document.getElementById(`toggleBtn-${capId}`);

      if (!held) {
        // 更新按鈕狀態
        if (lockBtn) lockBtn.disabled = false;
        if (unlockBtn) unlockBtn.disabled = false;
        if (toggleBtn) toggleBtn.disabled = false;
      }
    }
  }

  let _lockerFetchController = null;
  // 帶競態保護的拉狀態
  async function fetchLockerState(card) {
    const url = card.dataset.statusUrl;
    if (!url) return;

    // 取消上一筆還在路上的請求
    if (_lockerFetchController) _lockerFetchController.abort();
    _lockerFetchController = new AbortController();

    const current = (parseInt(card.dataset.reqToken || '0', 10) || 0) + 1;
    card.dataset.reqToken = String(current);

    let data = null;
    try {
      const resp = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        cache: 'no-store', // ← 不使用快取
        signal: _lockerFetchController.signal, // ← 可中止
      });
      if (!resp.ok) throw new Error('HTTP_' + resp.status);
      data = await resp.json();
    } catch {
      card.querySelector('#lockerSpinner')?.classList.add('d-none');
      return;
    }

    if (card.dataset.reqToken !== String(current)) return;

    // ❶ 本地保護期：剛做完操作的一小段時間，忽略回傳的舊狀態
    const holdUntil = parseInt(card.dataset.localHoldUntil || '0', 10) || 0;
    if (Date.now() < holdUntil) {
      // 還在保護期就別覆蓋 UI，但可以記錄 data 以備用（可選）
      return;
    }

    if (data && data.ok) renderLocker(card, data);
    else card.querySelector('#lockerSpinner')?.classList.add('d-none');
  }

  function resetLockerCard(card, msg = '請先從上方選擇「電子鎖」能力') {
    const badge = card.querySelector('#lockerBadge');
    const text = card.querySelector('#lockerText');
    const spin = card.querySelector('#lockerSpinner');
    badge.classList.remove('bg-success', 'bg-secondary', 'bg-warning');
    badge.classList.add('bg-secondary');
    badge.textContent = '未綁定';
    text.textContent = msg;
    spin?.classList.add('d-none');
    card.dataset.capId = '';
    card.dataset.statusUrl = '';
    card.dataset.reqToken = '0';
    card.dataset.burst = '0';
    card.dataset.isLocked = '0';
    card.dataset.autoLockRunning = '0';
  }

  function startLockerPolling(card) {
    let timer = null;

    async function tick() {
      try {
        await fetchLockerState(card);
      } finally {
        clearTimeout(timer);

        const spinOn = !card
          .querySelector('#lockerSpinner')
          ?.classList.contains('d-none');
        const burst = Math.max(0, parseInt(card.dataset.burst || '0', 10) || 0);

        let next;
        if (burst > 0) {
          next = FAST_BURST_MS;
          card.dataset.burst = String(burst - 1);
        } else if (spinOn) {
          next = 900; // 類似自動模式
        } else {
          next = IDLE_MS;
        }
        timer = setTimeout(tick, next);
      }
    }

    tick();
    return () => clearTimeout(timer);
  }

  let stopLockerPoll = null;

  function initLockerCardFromSelection() {
    const card = document.getElementById('lockerCard');
    if (!card) return;

    const sel = capSelect?.selectedOptions?.[0];
    const capId = sel?.value || '';
    const kind = (sel?.dataset?.kind || '').toLowerCase();

    if (!capId || kind !== 'locker') {
      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      resetLockerCard(card);
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
    card.dataset.isLocked = '0';
    card.dataset.autoLockRunning = '0';

    if (stopLockerPoll) {
      stopLockerPoll();
      stopLockerPoll = null;
    }
    stopLockerPoll = startLockerPolling(card);
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 切換群組 / 裝置 → 停輪詢 & 重置
    groupSelect?.addEventListener('change', () => {
      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      const card = document.getElementById('lockerCard');
      if (card) resetLockerCard(card, '請先選擇裝置與功能');
    });
    deviceSelect?.addEventListener('change', () => {
      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      const card = document.getElementById('lockerCard');
      if (card) resetLockerCard(card, '請先選擇功能');
    });

    // 選到 locker → 啟動輪詢
    capSelect?.addEventListener('change', () => {
      initLockerCardFromSelection();
    });

    // 首次進來補一次
    setTimeout(() => initLockerCardFromSelection(), 0);

    // 用按鈕操作時：開 spinner + 啟動爆發輪詢
    document.addEventListener('click', (evt) => {
      const el = evt.target;
      if (!el.matches('.locker-btn')) return;

      const card = document.getElementById('lockerCard');
      if (!card) return;

      // ❶ 立刻樂觀更新（不等伺服器）
      const capId = card.dataset.capId || '';
      const action = el.dataset.action;

      // ❷ 設定本地保護期（這段期間忽略回來的舊狀態）
      card.dataset.localHoldUntil = String(Date.now() + HOLD_MS);

      // ❸ 開啟爆發輪詢
      card.querySelector('#lockerSpinner')?.classList.remove('d-none');
      card.dataset.burst = String(FAST_BURST_TICKS);
      setTimeout(() => fetchLockerState(card).catch(() => {}), 120);
    });

    // 隱藏分頁時暫停、回到分頁時重新啟動，避免延遲堆積
    document.addEventListener('visibilitychange', () => {
      const card = document.getElementById('lockerCard');
      if (!card) return;
      if (document.hidden) {
        if (stopLockerPoll) {
          stopLockerPoll();
          stopLockerPoll = null;
        }
      } else {
        initLockerCardFromSelection();
      }
    });
  });
})();
