document.addEventListener('DOMContentLoaded', () => {
  const container = document.getElementById('deviceLogsContainer');
  const ctx = document.getElementById('deviceLogsChart').getContext('2d');
  const statusBar = document.getElementById('statusBar');
  let chart; // Chart.js 實例
  let pollTimer; // 輪詢計時器

  async function fetchLogs(deviceId) {
    try {
      const resp = await fetch(`/api/device/${deviceId}/logs/?limit=15`);
      const data = await resp.json();
      return data.logs || [];
    } catch (e) {
      console.error('載入紀錄失敗', e);
      return [];
    }
  }

  function renderChart(logs) {
    const cpuData = logs.map((log) => log.cpu_percent ?? null);
    const memData = logs.map((log) => log.memory_percent ?? null);
    const tempData = logs.map((log) => log.temperature ?? null);
    const labels = logs.map((log) => {
      if (!log.ping_at) return '';
      // 只取時間部分
      return log.ping_at.split(' ')[1]; // 取 "HH:mm:ss"
    });

    if (chart) chart.destroy();

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'CPU (%)',
            data: cpuData,
            borderColor: 'rgb(33, 150, 243)',
            backgroundColor: 'rgba(33, 150, 243, 0.1)',
            fill: true,
            yAxisID: 'y',
          },
          {
            label: '記憶體 (%)',
            data: memData,
            borderColor: 'rgb(255, 152, 0)',
            backgroundColor: 'rgba(255, 152, 0, 0.1)',
            fill: true,
            yAxisID: 'y',
          },
          {
            label: '溫度 (°C)',
            data: tempData,
            borderColor: 'rgb(244, 67, 54)',
            backgroundColor: 'rgba(244, 67, 54, 0.1)',
            fill: true,
            yAxisID: 'y1',
          },
        ],
      },
      options: {
        responsive: true,
        animation: false, // 避免一直閃爍
        interaction: {
          mode: 'index',
          intersect: false,
        },
        plugins: {
          title: {
            display: true,
            text: '裝置狀態紀錄',
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const log = logs[ctx.dataIndex];
                const base = `${ctx.dataset.label}: ${ctx.formattedValue}`;
                return log.status === 'offline' ? base + ' (offline)' : base;
              },
            },
          },
        },
        scales: {
          y: {
            type: 'linear',
            position: 'left',
            min: 0,
            max: 100,
            title: { display: true, text: 'CPU / 記憶體 (%)' },
          },
          y1: {
            type: 'linear',
            position: 'right',
            min: 0,
            max: 100, // 樹莓派最高大概 80–90°C，可調整
            grid: { drawOnChartArea: false },
            title: { display: true, text: '溫度 (°C)' },
          },
        },
      },
    });

    renderStatusBar(logs);
  }

  function renderStatusBar(logs) {
    statusBar.innerHTML = ''; // 清空
    const bar = document.createElement('div');
    bar.style.display = 'flex';
    bar.style.height = '28px'; // 原本 20px → 稍微加高
    bar.style.border = '1px solid #ccc';
    bar.style.borderRadius = '6px'; // 加圓角
    bar.style.marginTop = '15px'; // 與圖表分開一點

    logs.forEach((log) => {
      const seg = document.createElement('div');
      seg.style.flex = '1';
      seg.style.background = log.status === 'offline' ? 'var(--status-offline)' : 'var(--status-online)';
      seg.style.borderRight = '1px solid var(--border-color)';
      seg.title = `${log.ping_at} → ${log.status}`;
      bar.appendChild(seg);
    });

    statusBar.appendChild(bar);
  }

  async function loadAndRender(deviceId) {
    const logs = await fetchLogs(deviceId);
    if (logs.length > 0) {
      container.style.display = 'block';
      renderChart(logs);
    } else {
      container.style.display = 'none';
    }
  }

  // 綁定選裝置事件
  const deviceSelect = document.getElementById('deviceSelect');
  if (deviceSelect) {
    deviceSelect.addEventListener('change', async () => {
      const deviceId = deviceSelect.value;
      if (!deviceId) {
        container.style.display = 'none';
        clearInterval(pollTimer);
        return;
      }

      // 第一次載入
      await loadAndRender(deviceId);

      // 清除舊的輪詢
      clearInterval(pollTimer);
      // 每 30 秒重新抓 logs
      pollTimer = setInterval(() => loadAndRender(deviceId), 30000);
    });
  }
});
