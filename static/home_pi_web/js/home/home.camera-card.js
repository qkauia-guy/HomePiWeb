/* home.camera-card.js — 監控錄影卡片狀態管理 */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);

  // 渲染監控錄影卡片
  function renderCamera(card, state) {
    const badge = card.querySelector('#cameraBadge');
    const text = card.querySelector('#cameraText');
    const liveBtn = card.querySelector('#cameraLiveBtn');
    const qualityText = card.querySelector('#cameraQualityText');
    const tipText = card.querySelector('#cameraTipText');
    const deviceName = card.querySelector('#cameraDeviceName');

    // 根據 API 回應判斷裝置狀態
    // 如果 API 回應成功且有資料，表示裝置上線
    const isOnline = !!(state && state.ok);
    const isRecording = !!(state && state.is_streaming);
    const quality = (state && state.quality) || '1080p';
    const hlsUrl = state && state.hls_url;
    const deviceId = card.dataset.deviceId;
    const groupId = card.dataset.groupId;

    // 標章狀態
    badge.classList.remove('bg-success', 'bg-secondary', 'bg-warning', 'bg-danger');
    if (isOnline) {
      if (isRecording) {
        badge.classList.add('bg-danger');
        badge.textContent = '錄影中';
      } else {
        badge.classList.add('bg-success');
        badge.textContent = '監控中';
      }
    } else {
      badge.classList.add('bg-secondary');
      badge.textContent = '離線';
    }

    // 狀態文字
    if (isOnline) {
      text.textContent = isRecording ? '正在錄影中 📹' : '監控就緒 📹';
    } else {
      text.textContent = '裝置離線';
    }

    // 直播按鈕
    if (liveBtn) {
      if (isOnline && deviceId && groupId) {
        // 使用 HLS URL 或預設的直播連結
        if (hlsUrl) {
          liveBtn.href = hlsUrl;
        } else {
          liveBtn.href = `/live/${deviceId}/${deviceId}/?group_id=${groupId}`;
        }
        liveBtn.style.display = 'inline-block';
        liveBtn.textContent = isRecording ? '觀看直播（開新視窗）' : '開始直播（開新視窗）';
      } else {
        liveBtn.style.display = 'none';
      }
    }

    // 錄影品質
    if (qualityText) {
      qualityText.textContent = quality;
    }

    // 提示文字
    if (tipText) {
      if (isOnline) {
        tipText.textContent = isRecording ? '按「觀看直播」會另開視窗播放。' : '按「開始直播」會另開視窗播放。';
      } else {
        tipText.textContent = '請先選擇群組和裝置。';
      }
    }

    // 更新裝置名稱
    if (deviceName && state.device_name) {
      deviceName.textContent = state.device_name;
    }
  }

  // 重置監控錄影卡片
  function resetCameraCard(card, msg = null) {
    const badge = card.querySelector('#cameraBadge');
    const text = card.querySelector('#cameraText');
    const liveBtn = card.querySelector('#cameraLiveBtn');
    const qualityText = card.querySelector('#cameraQualityText');
    const tipText = card.querySelector('#cameraTipText');
    const deviceName = card.querySelector('#cameraDeviceName');

    // 根據螢幕大小決定預設訊息
    if (!msg) {
      const isMobile = window.innerWidth <= 767.98;
      msg = isMobile ? '點擊卡片開始監控' : '請先從上方選擇「監控錄影」能力';
    }

    badge.classList.remove('bg-success', 'bg-secondary', 'bg-warning', 'bg-danger');
    badge.classList.add('bg-secondary');
    badge.textContent = '未綁定';

    text.textContent = msg;

    if (liveBtn) {
      liveBtn.style.display = 'none';
    }

    if (qualityText) {
      qualityText.textContent = '未設定';
    }

    if (tipText) {
      tipText.textContent = '請先選擇群組和裝置。';
    }

    // 重置裝置名稱
    if (deviceName) {
      deviceName.textContent = '未選擇';
    }

    // 清除資料屬性
    card.dataset.deviceId = '';
    card.dataset.groupId = '';
  }

  // 獲取監控錄影狀態
  async function fetchCameraState(card) {
    const deviceId = card.dataset.deviceId;
    const groupId = card.dataset.groupId;
    
    if (!deviceId || !groupId) {
      console.log('監控錄影狀態更新失敗：缺少裝置ID或群組ID');
      return;
    }

    // 先獲取裝置狀態來檢查裝置是否上線
    const deviceStatusUrl = `/api/device/${encodeURIComponent(deviceId)}/status/` + 
      (groupId ? `?group_id=${encodeURIComponent(groupId)}` : '');
    
    console.log('開始獲取裝置狀態:', deviceStatusUrl);

    try {
      const deviceResp = await fetch(deviceStatusUrl, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
        cache: 'no-store',
      });
      
      if (!deviceResp.ok) throw new Error('HTTP_' + deviceResp.status);
      
      const deviceData = await deviceResp.json();
      console.log('裝置狀態API回應:', deviceData);

      if (deviceData && deviceData.ok && deviceData.is_online && deviceData.capabilities && deviceData.capabilities.camera) {
        const cameraCap = deviceData.capabilities.camera;
        console.log('找到監控錄影能力:', cameraCap);
        
        // 使用能力狀態來渲染卡片
        const cameraState = {
          ok: true,
          device_name: deviceData.device_name,
          is_streaming: cameraCap.is_streaming || false,
          quality: '1080p', // 預設品質
          hls_url: cameraCap.hls_url || null
        };
        
        console.log('更新監控錄影狀態卡片:', cameraState);
        renderCamera(card, cameraState);
      } else {
        console.log('裝置沒有監控錄影能力或裝置離線');
        resetCameraCard(card);
      }
    } catch (e) {
      console.error('監控錄影狀態API請求失敗:', e);
      resetCameraCard(card);
    }
  }

  // 初始化監控錄影卡片
  function initCameraCard(card, deviceId, groupId) {
    if (!card || !deviceId || !groupId) {
      console.log('監控錄影卡片初始化失敗：缺少必要參數');
      return;
    }

    console.log('初始化監控錄影卡片，裝置ID:', deviceId, '群組ID:', groupId);

    // 設定資料屬性
    card.dataset.deviceId = deviceId;
    card.dataset.groupId = groupId;
    card.dataset.statusUrl = `/api/device/${encodeURIComponent(deviceId)}/status/` + 
      (groupId ? `?group_id=${encodeURIComponent(groupId)}` : '');

    // 立即獲取狀態
    fetchCameraState(card);

    // 設定定期更新（每30秒檢查一次）
    const intervalId = setInterval(() => {
      fetchCameraState(card);
    }, 30000);

    // 儲存 interval ID 以便後續清理
    card.dataset.intervalId = intervalId;
  }

  // 停止監控錄影卡片更新
  function stopCameraCard(card) {
    const intervalId = card.dataset.intervalId;
    if (intervalId) {
      clearInterval(parseInt(intervalId, 10));
      card.dataset.intervalId = '';
    }
    resetCameraCard(card);
  }

  // 導出到全域
  window.renderCamera = renderCamera;
  window.resetCameraCard = resetCameraCard;
  window.fetchCameraState = fetchCameraState;
  window.initCameraCard = initCameraCard;
  window.stopCameraCard = stopCameraCard;

})();
