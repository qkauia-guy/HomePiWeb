/* home.mobile.js — 手機版狀態卡片點擊控制 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);
  
  // 快取機制，避免重複請求
  const deviceStatusCache = new Map();
  const CACHE_DURATION = 5000; // 5秒快取

  // 檢查是否為手機版
  function isMobile() {
    return window.innerWidth <= 767.98;
  }

  // 快取的裝置狀態獲取函數
  async function getCachedDeviceStatus(deviceId, groupId) {
    const cacheKey = `${deviceId}-${groupId}`;
    const now = Date.now();
    
    // 檢查快取
    if (deviceStatusCache.has(cacheKey)) {
      const cached = deviceStatusCache.get(cacheKey);
      if (now - cached.timestamp < CACHE_DURATION) {
        console.log('使用快取的裝置狀態');
        return cached.data;
      }
    }
    
    // 獲取新數據
    const statusUrl = `/api/device/${encodeURIComponent(deviceId)}/status/` + 
      (groupId ? `?group_id=${encodeURIComponent(groupId)}` : '');
    
    const statusResponse = await fetch(statusUrl, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
      cache: 'no-store',
    });
    
    if (!statusResponse.ok) {
      throw new Error(`HTTP ${statusResponse.status}: ${statusResponse.statusText}`);
    }
    
    const statusData = await statusResponse.json();
    
    // 更新快取
    deviceStatusCache.set(cacheKey, {
      data: statusData,
      timestamp: now
    });
    
    return statusData;
  }

  // 手機版狀態卡片點擊處理
  function handleMobileCardClick(event) {
    if (!isMobile()) return;

    const card = event.currentTarget;
    const capability = card.dataset.capability;
    const groupId = card.dataset.groupId;
    
    // 檢查是否已選擇群組和裝置
    const groupSelect = $('#groupSelect');
    const deviceSelect = $('#deviceSelect');
    
    if (!groupSelect?.value || !deviceSelect?.value) {
      // 顯示提示訊息
      showBanner('warning', '請先選擇群組和裝置');
      return;
    }

    // 根據能力類型載入對應的表單
    if (capability === 'light') {
      loadLightForm(groupSelect.value, deviceSelect.value);
    } else if (capability === 'locker') {
      loadLockerForm(groupSelect.value, deviceSelect.value);
    }
  }

  // 載入燈光表單 - 優化版本
  async function loadLightForm(groupId, deviceId) {
    try {
      console.log('開始載入燈光表單，群組ID:', groupId, '裝置ID:', deviceId);
      
      // 使用快取的裝置狀態
      const statusData = await getCachedDeviceStatus(deviceId, groupId);
      console.log('裝置狀態回應:', statusData);
      
      if (statusData && statusData.ok && statusData.capabilities && statusData.capabilities.light) {
        const lightCap = statusData.capabilities.light;
        console.log('找到燈光能力ID:', lightCap.id);
        
        // 直接使用能力 ID 載入表單
        await loadFormByCapId(lightCap.id, groupId, '燈光');
      } else {
        showBanner('warning', '此裝置沒有燈光功能');
      }
      
    } catch (error) {
      console.error('載入燈光表單失敗:', error);
      showBanner('error', `載入表單失敗: ${error.message}`);
    }
  }

  // 載入電子鎖表單 - 優化版本
  async function loadLockerForm(groupId, deviceId) {
    try {
      console.log('開始載入電子鎖表單，群組ID:', groupId, '裝置ID:', deviceId);
      
      // 使用快取的裝置狀態
      const statusData = await getCachedDeviceStatus(deviceId, groupId);
      console.log('裝置狀態回應:', statusData);
      
      if (statusData && statusData.ok && statusData.capabilities && statusData.capabilities.locker) {
        const lockerCap = statusData.capabilities.locker;
        console.log('找到電子鎖能力ID:', lockerCap.id);
        
        // 直接使用能力 ID 載入表單
        await loadFormByCapId(lockerCap.id, groupId, '電子鎖');
      } else {
        showBanner('warning', '此裝置沒有電子鎖功能');
      }
      
    } catch (error) {
      console.error('載入電子鎖表單失敗:', error);
      showBanner('error', `載入表單失敗: ${error.message}`);
    }
  }

  // 初始化狀態卡片
  async function initStatusCards() {
    console.log('初始化狀態卡片...');
    
    const groupSelect = $('#groupSelect');
    const deviceSelect = $('#deviceSelect');
    
    if (!groupSelect?.value || !deviceSelect?.value) {
      console.log('缺少群組或裝置選擇');
      return;
    }
    
    try {
      // 獲取裝置狀態和能力信息
      const g = groupSelect.value;
      const deviceId = deviceSelect.value;
      
      console.log('獲取裝置狀態，裝置ID:', deviceId, '群組ID:', g);
      
      // 使用快取的裝置狀態
      const data = await getCachedDeviceStatus(deviceId, g);
      console.log('裝置狀態API回應:', data);
      
      if (data && data.ok && data.capabilities) {
        console.log('裝置能力:', data.capabilities);
        
        // 初始化燈光卡片
        const lightCard = $('#lightCard');
        if (lightCard && data.capabilities.light) {
          const lightCap = data.capabilities.light;
          
          lightCard.dataset.capId = lightCap.id;
          lightCard.dataset.statusUrl = `/api/cap/${lightCap.id}/status/` + 
            (g ? `?group_id=${encodeURIComponent(g)}` : '');
          lightCard.dataset.reqToken = '0';
          lightCard.dataset.burst = '0';
          lightCard.dataset.isAuto = '0';
          
          console.log('燈光卡片已初始化:', lightCard.dataset.statusUrl);
          
          // 觸發燈光卡片輪詢
          if (window.startLightPolling) {
            if (window.stopLightPoll) {
              window.stopLightPoll();
            }
            window.stopLightPoll = window.startLightPolling(lightCard);
            console.log('燈光輪詢已啟動');
          }
          
          // 立即執行一次狀態更新
          if (window.fetchLightState) {
            console.log('立即執行燈光狀態更新');
            window.fetchLightState(lightCard).catch((e) => {
              console.error('燈光狀態更新失敗:', e);
            });
          }
        }
        
        // 初始化電子鎖卡片
        const lockerCard = $('#lockerCard');
        if (lockerCard && data.capabilities.locker) {
          const lockerCap = data.capabilities.locker;
          
          lockerCard.dataset.capId = lockerCap.id;
          lockerCard.dataset.statusUrl = `/api/cap/${lockerCap.id}/status/` + 
            (g ? `?group_id=${encodeURIComponent(g)}` : '');
          lockerCard.dataset.reqToken = '0';
          lockerCard.dataset.burst = '0';
          lockerCard.dataset.isLocked = '0';
          
          console.log('電子鎖卡片已初始化:', lockerCard.dataset.statusUrl);
          
          // 觸發電子鎖卡片輪詢
          if (window.startLockerPolling) {
            if (window.stopLockerPoll) {
              window.stopLockerPoll();
            }
            window.stopLockerPoll = window.startLockerPolling(lockerCard);
          }
          
          // 立即執行一次狀態更新
          if (window.fetchLockerState) {
            console.log('立即執行電子鎖狀態更新');
            window.fetchLockerState(lockerCard).catch((e) => {
              console.error('電子鎖狀態更新失敗:', e);
            });
          }
        }
      }
    } catch (error) {
      console.error('初始化狀態卡片失敗:', error);
    }
  }

  // 導出到全域
  window.initStatusCards = initStatusCards;

  // 通用表單載入函數
  async function loadFormByCapId(capId, groupId, capabilityName) {
    try {
      console.log(`載入${capabilityName}表單，能力ID:`, capId, '群組ID:', groupId);
      
      const formUrl = `/controls/cap-form/${capId}/?group_id=${groupId}`;
      console.log('載入表單URL:', formUrl);
      
      const formResponse = await fetch(formUrl);
      
      if (!formResponse.ok) {
        throw new Error(`HTTP ${formResponse.status}: ${formResponse.statusText}`);
      }
      
      const formHtml = await formResponse.text();
      console.log('獲取表單HTML:', formHtml);
      
      // 顯示表單
      const capForms = $('#capForms');
      if (capForms) {
        capForms.innerHTML = formHtml;
        capForms.scrollIntoView({ behavior: 'smooth' });
        
        // 觸發表單載入事件
        const schedForm = capForms.querySelector('form[id^="schedForm-"]');
        document.dispatchEvent(
          new CustomEvent('cap-form-loaded', {
            detail: { form: schedForm, container: capForms },
          })
        );
        
        // 立即觸發狀態卡片初始化
        await initStatusCards();
        
        // 立即強制同步表單狀態
        const switches = capForms.querySelectorAll('.cap-toggle');
        console.log('表單載入後，強制同步開關狀態，開關數量:', switches.length);
        
        // 強制更新狀態卡片
        const lightCard = document.getElementById('lightCard');
        if (lightCard && window.forceUpdateLightState) {
          window.forceUpdateLightState(lightCard);
        }
        
        // 觸發狀態更新來同步表單
        if (window.HomeUI?.triggerStatusUpdate) {
          window.HomeUI.triggerStatusUpdate();
        }
        
        // 簡單測試：檢查開關是否存在
        setTimeout(() => {
          const switches = capForms.querySelectorAll('.cap-toggle');
          console.log('表單中的開關數量:', switches.length);
          if (switches.length > 0) {
            console.log('第一個開關:', switches[0].id, switches[0].dataset);
          }
        }, 300);
        
        
        console.log(`${capabilityName}表單載入成功`);
        showBanner('success', `${capabilityName}控制表單已載入`);
      }
      
    } catch (error) {
      console.error(`載入${capabilityName}表單失敗:`, error);
      showBanner('error', `載入表單失敗: ${error.message}`);
    }
  }

  // 顯示提示訊息
  function showBanner(kind, text) {
    const ajaxMsg = $('#ajaxMsg');
    if (!ajaxMsg) return;
    
    ajaxMsg.className = `alert alert-${kind} mt-3 mb-3`;
    ajaxMsg.textContent = text;
    ajaxMsg.style.display = '';
    
    clearTimeout(showBanner._t);
    showBanner._t = setTimeout(() => {
      ajaxMsg.style.display = 'none';
    }, 3000);
  }

  // 初始化手機版功能
  function initMobileFeatures() {
    if (!isMobile()) return;

    // 綁定狀態卡片點擊事件
    const lightCard = $('#lightCard');
    const lockerCard = $('#lockerCard');
    
    if (lightCard) {
      lightCard.addEventListener('click', handleMobileCardClick);
    }
    
    if (lockerCard) {
      lockerCard.addEventListener('click', handleMobileCardClick);
    }
  }

  // 頁面載入完成後初始化
  document.addEventListener('DOMContentLoaded', initMobileFeatures);

  // 視窗大小改變時重新初始化
  window.addEventListener('resize', () => {
    setTimeout(initMobileFeatures, 100);
  });

})();
