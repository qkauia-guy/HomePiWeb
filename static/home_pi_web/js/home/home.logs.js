document.addEventListener('DOMContentLoaded', () => {
  const tableBody = document.querySelector('#deviceLogsTable tbody');
  const deviceSelect = document.querySelector('#deviceSelect');
  let pollTimer;

  async function loadLogs(deviceId) {
    if (!deviceId) {
      tableBody.innerHTML = `<tr><td colspan="6" class="text-muted text-center">請先選擇裝置</td></tr>`;
      return;
    }

    try {
      const resp = await fetch(
        `/api/device/${encodeURIComponent(deviceId)}/logs/?limit=10`
      );
      if (!resp.ok) throw new Error('HTTP ' + resp.status);

      const data = await resp.json();
      const logs = data.logs || [];

      if (logs.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">沒有紀錄</td></tr>`;
        return;
      }

      tableBody.innerHTML = '';
      logs.forEach((log) => {
        const row = document.createElement('tr');
        
        // 計算可用容量百分比（100 - 使用百分比）
        let diskDisplay = '-';
        let capacityClass = '';
        if (log.disk_percent != null) {
          const availablePercent = 100 - log.disk_percent;
          diskDisplay = availablePercent.toFixed(1) + '%';
          
          // 根據可用容量設定顏色
          if (availablePercent >= 50) {
            capacityClass = 'data-available="good"';
          } else if (availablePercent >= 20) {
            capacityClass = 'data-available="low"';
          } else {
            capacityClass = 'data-available="critical"';
          }
        }
        
        row.innerHTML = `
          <td>${log.ping_at || '-'}</td>
          <td class="disk-capacity" ${capacityClass}>
            ${diskDisplay}
          </td>
          <td>${log.ip || '-'}</td>
          <td>${
            log.cpu_percent != null ? log.cpu_percent.toFixed(1) + '%' : '-'
          }</td>
          <td>${
            log.memory_percent != null
              ? log.memory_percent.toFixed(1) + '%'
              : '-'
          }</td>
          <td>${
            log.temperature != null ? log.temperature.toFixed(1) + '°C' : '-'
          }</td>
        `;
        tableBody.appendChild(row);
      });
    } catch (err) {
      console.error('載入日誌失敗:', err);
      tableBody.innerHTML = `<tr><td colspan="6" class="text-danger text-center">載入失敗</td></tr>`;
    }
  }

  // 綁定「裝置選擇事件」
  deviceSelect?.addEventListener('change', async () => {
    const deviceId = deviceSelect.value;

    // 先載入一次
    await loadLogs(deviceId);

    // 清掉舊的輪詢
    clearInterval(pollTimer);

    if (deviceId) {
      // 每 30 秒自動刷新
      pollTimer = setInterval(() => loadLogs(deviceId), 30000);
    }
  });

  // 預設顯示「請先選擇裝置」
  loadLogs(null);
});

document.addEventListener('DOMContentLoaded', () => {
  const deviceSelect = document.getElementById('deviceSelect');
  const logsWrapper = document.getElementById('deviceLogsWrapper');

  if (deviceSelect) {
    deviceSelect.addEventListener('change', () => {
      if (deviceSelect.value) {
        logsWrapper.style.display = 'block'; // 顯示
      } else {
        logsWrapper.style.display = 'none'; // 隱藏
      }
    });
  }
});
