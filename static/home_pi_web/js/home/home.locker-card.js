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

  // 速度參數 - 優化為更快的更新
  const FAST_BURST_MS = 200; // 動作後爆發輪詢間隔 (0.2秒)
  const FAST_BURST_TICKS = 12; // 動作後快速輪詢次數（~2.4s）
  const HOLD_MS = 1500; // 縮短保護期
  const IDLE_MS = 2000; // 閒置輪詢 (2秒)

  // 時間格式化函數
  function formatScheduleTime(timestamp) {
    if (!timestamp) return ' 未排程 ';
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = date.getTime() - now.getTime();
    
    if (diff < 0) return ' 已過期 ';
    if (diff < 60000) return ' 即將執行 ';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours > 0) {
      return ` ${hours}小時${minutes}分鐘後 `;
    } else {
      return ` ${minutes}分鐘後 `;
    }
  }

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

  // 初始化按鈕狀態樣式
  function initButtonStyles(capId, isLocked) {
    if (!capId) return;
    
    const lockBtn = document.getElementById(`lockBtn-${capId}`);
    const unlockBtn = document.getElementById(`unlockBtn-${capId}`);
    const toggleBtn = document.getElementById(`toggleBtn-${capId}`);

    // 上鎖按鈕：只有在已上鎖時才發光
    if (lockBtn) {
      lockBtn.classList.remove('active-locked', 'active-unlocked');
      if (isLocked) {
        lockBtn.classList.add('active-locked');
      }
    }

    // 開鎖按鈕：只有在已開鎖時才發光
    if (unlockBtn) {
      unlockBtn.classList.remove('active-locked', 'active-unlocked');
      if (!isLocked) {
        unlockBtn.classList.add('active-unlocked');
      }
    }

    // 切換按鈕：根據當前狀態顯示對應顏色
    if (toggleBtn) {
      toggleBtn.classList.remove('active-locked', 'active-unlocked');
      if (isLocked) {
        toggleBtn.classList.add('active-locked');
      } else {
        toggleBtn.classList.add('active-unlocked');
      }
    }
  }

  // 渲染卡片（尊重 hold）
  function renderLocker(card, state) {
    console.log('[Locker] 渲染狀態:', state);
    const badge = card.querySelector('#lockerBadge');
    const text = card.querySelector('#lockerText');
    const spin = card.querySelector('#lockerSpinner');
    const deviceName = card.querySelector('#lockerDeviceName');

    const isLocked = !!state.locked;

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
    text.textContent = `目前狀態：${isLocked ? '已上鎖🔒' : '已開鎖🔓'}`;

    // 更新狀態文字
    const statusText = card.querySelector('#lockerStatusText');
    const schedOnText = card.querySelector('#lockerSchedOnText');
    const schedOffText = card.querySelector('#lockerSchedOffText');
    
    if (statusText) {
      statusText.textContent = isLocked ? '已上鎖' : '已開鎖';
    }
    
    // 更新排程文字（如果有的話）
    if (schedOnText) {
      console.log('[Locker] 更新開鎖排程:', state.next_unlock);
      schedOnText.textContent = state.next_unlock ? formatScheduleTime(state.next_unlock) : ' 未排程 ';
    }
    if (schedOffText) {
      console.log('[Locker] 更新上鎖排程:', state.next_lock);
      schedOffText.textContent = state.next_lock ? formatScheduleTime(state.next_lock) : ' 未排程 ';
    }

    // 控制移除排程按鈕顯示/隱藏
    const removeScheduleBtn = card.querySelector('#lockerRemoveScheduleBtn');
    if (removeScheduleBtn) {
      const hasSchedule = state.next_unlock || state.next_lock;
      removeScheduleBtn.classList.toggle('d-none', !hasSchedule);
    }

    // 更新裝置名稱
    if (deviceName && state.device_name) {
      deviceName.textContent = state.device_name;
    }

    // spinner：pending 顯示
    if (spin) {
      const pending = Boolean(state.pending);
      if (pending) {
        spin.classList.remove('d-none');
      } else {
        spin.classList.add('d-none');
      }
    }

    // 記錄狀態給輪詢節奏用
    card.dataset.isLocked = isLocked ? '1' : '0';

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
        
        // 更新按鈕樣式
        initButtonStyles(capId, isLocked);
      }
    }
  }

  let _lockerFetchController = null;
  // 帶競態保護的拉狀態
  async function fetchLockerState(card) {
    const url = card.dataset.statusUrl;
    if (!url) {
      console.log('[Locker] 沒有狀態 URL，跳過更新');
      return;
    }
    
    console.log('[Locker] 開始更新狀態，URL:', url);

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
    } catch (error) {
      console.error('電子鎖狀態更新失敗:', error);
      card.querySelector('#lockerSpinner')?.classList.add('d-none');
      
      // 更詳細的錯誤處理
      const text = card.querySelector('#lockerText');
      if (text) {
        if (error.name === 'AbortError') {
          // 請求被取消，不顯示錯誤
          return;
        } else if (error.message.includes('HTTP_401')) {
          text.textContent = '請重新登入';
        } else if (error.message.includes('HTTP_403')) {
          text.textContent = '無權限存取此裝置';
        } else if (error.message.includes('HTTP_404')) {
          text.textContent = '裝置不存在';
        } else if (error.message.includes('HTTP_')) {
          text.textContent = `伺服器錯誤 (${error.message})`;
        } else {
          text.textContent = '連線失敗，請檢查網路';
        }
      }
      return;
    }

    if (card.dataset.reqToken !== String(current)) return;

    // ❶ 本地保護期：剛做完操作的一小段時間，忽略回傳的舊狀態
    const holdUntil = parseInt(card.dataset.localHoldUntil || '0', 10) || 0;
    if (Date.now() < holdUntil) {
      // 還在保護期就別覆蓋 UI，但可以記錄 data 以備用（可選）
      return;
    }

    if (data && data.ok) {
      console.log('[Locker] API 回應:', data);
      renderLocker(card, data);
    } else {
      console.log('[Locker] API 回應失敗:', data);
      card.querySelector('#lockerSpinner')?.classList.add('d-none');
      // 如果 API 回傳失敗，顯示錯誤狀態
      const text = card.querySelector('#lockerText');
      if (text) {
        if (data && data.error) {
          text.textContent = `錯誤: ${data.error}`;
        } else {
          text.textContent = '狀態更新失敗';
        }
      }
    }
  }

  function resetLockerCard(card, msg = null) {
    // 根據螢幕大小決定預設訊息
    if (!msg) {
      const isMobile = window.innerWidth <= 767.98;
      msg = isMobile ? '點擊卡片操作電子鎖' : '請先從上方選擇「電子鎖」能力';
    }
    const badge = card.querySelector('#lockerBadge');
    const text = card.querySelector('#lockerText');
    const spin = card.querySelector('#lockerSpinner');
    const statusText = card.querySelector('#lockerStatusText');
    const autoText = card.querySelector('#lockerAutoText');
    const deviceName = card.querySelector('#lockerDeviceName');
    
    badge.classList.remove('bg-success', 'bg-secondary', 'bg-warning');
    badge.classList.add('bg-secondary');
    badge.textContent = '未綁定';
    text.textContent = msg;
    spin?.classList.add('d-none');
    
    // 重置狀態文字
    if (statusText) statusText.textContent = '未連接';
    
    // 重置排程文字
    const schedOnText = card.querySelector('#lockerSchedOnText');
    const schedOffText = card.querySelector('#lockerSchedOffText');
    if (schedOnText) schedOnText.textContent = ' 未排程 ';
    if (schedOffText) schedOffText.textContent = ' 未排程 ';
    
    // 重置裝置名稱
    if (deviceName) {
      deviceName.textContent = '未選擇';
    }
    
    card.dataset.capId = '';
    card.dataset.statusUrl = '';
    card.dataset.reqToken = '0';
    card.dataset.burst = '0';
    card.dataset.isLocked = '0';
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
  
  // 暴露函數到全域，讓其他模組可以調用
  window.stopLockerPoll = () => {
    if (stopLockerPoll) {
      stopLockerPoll();
      stopLockerPoll = null;
    }
  };
  window.startLockerPolling = startLockerPolling;
  window.fetchLockerState = fetchLockerState;

  // 根據裝置 ID 初始化狀態卡片
  async function initDeviceStatusFromSelection(deviceId) {
    const lightCard = document.getElementById('lightCard');
    const lockerCard = document.getElementById('lockerCard');
    
    if (!lightCard && !lockerCard) return;

    const g = groupSelect?.value || '';
    const statusUrl = `/api/device/${encodeURIComponent(deviceId)}/status/` + 
      (g ? `?group_id=${encodeURIComponent(g)}` : '');

    try {
      const resp = await fetch(statusUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        cache: 'no-store',
      });
      
      if (!resp.ok) throw new Error('HTTP_' + resp.status);
      const data = await resp.json();
      
      if (data && data.ok && data.capabilities) {
        // 初始化燈光卡片
        if (lightCard && data.capabilities.light) {
          const lightCap = data.capabilities.light;
          
          lightCard.dataset.capId = lightCap.id;
          lightCard.dataset.statusUrl = `/api/cap/${lightCap.id}/status/` + 
            (g ? `?group_id=${encodeURIComponent(g)}` : '');
          lightCard.dataset.reqToken = '0';
          lightCard.dataset.burst = '0';
          lightCard.dataset.isAuto = '0';

          // 停止現有輪詢（需要從 light-card.js 獲取）
          if (window.stopLightPoll) {
            window.stopLightPoll();
            window.stopLightPoll = null;
          }
          
          // 開始輪詢（需要從 light-card.js 獲取）
          if (window.startLightPolling) {
            window.stopLightPoll = window.startLightPolling(lightCard);
          }
          
          // 立即執行一次狀態更新
          setTimeout(() => {
            if (window.fetchLightState) {
              window.fetchLightState(lightCard).catch(() => {});
            }
          }, 100);
        }
        
        // 初始化電子鎖卡片
        if (lockerCard && data.capabilities.locker) {
          const lockerCap = data.capabilities.locker;
          
          lockerCard.dataset.capId = lockerCap.id;
          lockerCard.dataset.statusUrl = `/api/cap/${lockerCap.id}/status/` + 
            (g ? `?group_id=${encodeURIComponent(g)}` : '');
          lockerCard.dataset.reqToken = '0';
          lockerCard.dataset.burst = '0';
          lockerCard.dataset.isLocked = '0';

          // 停止現有輪詢
          if (stopLockerPoll) {
            stopLockerPoll();
            stopLockerPoll = null;
          }
          
          // 立即初始化按鈕樣式（使用裝置狀態中的鎖定狀態）
          const isLocked = !!(data.capabilities.locker.status && data.capabilities.locker.status.locked);
          initButtonStyles(lockerCap.id, isLocked);
          
          // 開始輪詢
          stopLockerPoll = startLockerPolling(lockerCard);
          
          // 立即執行一次狀態更新
          setTimeout(() => fetchLockerState(lockerCard).catch(() => {}), 100);
        }
      }
    } catch (error) {
      console.error('載入裝置狀態失敗:', error);
    }
  }

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

    // 選擇功能後，使用裝置狀態 API 來獲取整體狀態
    const deviceId = deviceSelect?.value;
    if (deviceId) {
      initDeviceStatusFromSelection(deviceId);
    } else {
      // 如果沒有選定裝置，使用原有的能力狀態 API
      const g = groupSelect?.value || '';
      const statusUrl =
        `/api/cap/${encodeURIComponent(capId)}/status/` +
        (g ? `?group_id=${encodeURIComponent(g)}` : '');

      card.dataset.capId = capId;
      card.dataset.statusUrl = statusUrl;
      card.dataset.reqToken = '0';
      card.dataset.burst = '0';
      card.dataset.isLocked = '0';

      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      stopLockerPoll = startLockerPolling(card);
      
      // 立即執行一次狀態更新
      setTimeout(() => fetchLockerState(card).catch(() => {}), 100);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    // 切換群組 → 停輪詢 & 重置，不嘗試顯示狀態
    groupSelect?.addEventListener('change', () => {
      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      const card = document.getElementById('lockerCard');
      if (card) resetLockerCard(card);
      
      // 群組選擇時不嘗試顯示狀態，因為還沒有選擇裝置和能力
    });
    
    // 切換裝置 → 停輪詢 & 重置，然後顯示裝置狀態
    deviceSelect?.addEventListener('change', () => {
      if (stopLockerPoll) {
        stopLockerPoll();
        stopLockerPoll = null;
      }
      const card = document.getElementById('lockerCard');
      if (card) resetLockerCard(card);
      
      // 等待能力選單載入完成後，嘗試顯示裝置狀態
      setTimeout(() => {
        const deviceId = deviceSelect?.value;
        if (deviceId) {
          initDeviceStatusFromSelection(deviceId);
        }
      }, 500);
    });

    // 選到 locker → 啟動輪詢
    capSelect?.addEventListener('change', () => {
      initLockerCardFromSelection();
    });

    // 監聽 URL 參數恢復完成事件
    document.addEventListener('url-params-restored', () => {
      initLockerCardFromSelection();
    });
    
    // 首次進來補一次（延遲更久，等待 URL 參數恢復完成）
    setTimeout(() => initLockerCardFromSelection(), 1000);

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
