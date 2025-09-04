/* home.polling.js — 燈光面板狀態輪詢（快取輪詢 + 動作後爆發） */
(() => {
  'use strict';

  const $ = (sel, root = document) => root.querySelector(sel);

  const FAST_BURST_MS = 300;
  const FAST_BURST_TICKS = 8;
  const AUTO_MS = 900;
  const IDLE_MS = 5000;

  function renderLight(card, state) {
    const badge = card.querySelector('#lightBadge');
    const text = card.querySelector('#lightText');
    const spin = card.querySelector('#lightSpinner');

    const isAuto = !!state.auto_light_running;
    const isOn = !!state.light_is_on;

    badge.classList.remove('bg-success', 'bg-secondary', 'bg-info');
    if (isAuto) {
      badge.classList.add('bg-drange');
      badge.textContent = '自動偵測中';
    } else if (isOn) {
      badge.classList.add('bg-success');
      badge.textContent = '啟動';
    } else {
      badge.classList.add('bg-secondary');
      badge.textContent = '關閉';
    }

    text.textContent = isAuto
      ? `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`
      : `目前狀態：${isOn ? '開燈中💡' : '已熄燈'}`;

    if (spin) {
      const pending = Boolean(state.pending);
      spin.classList.toggle('d-none', !(isAuto || pending));
    }

    card.dataset.isAuto = isAuto ? '1' : '0';

    const capId = card.dataset.capId;
    if (capId) {
      const autoSwitch = document.getElementById(`autoSwitch-${capId}`);
      const lightSwitch = document.getElementById(`lightSwitch-${capId}`);
      if (autoSwitch && autoSwitch.checked !== isAuto)
        autoSwitch.checked = isAuto;
      if (lightSwitch) {
        lightSwitch.disabled = isAuto;
        if (lightSwitch.checked !== isOn) lightSwitch.checked = isOn;
      }
    }
  }

  async function fetchLightState(card) {
    const url = card.dataset.statusUrl;
    if (!url) return;

    const current = (parseInt(card.dataset.reqToken || '0', 10) || 0) + 1;
    card.dataset.reqToken = String(current);

    let data = null;
    try {
      const resp = await fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });
      if (!resp.ok) throw new Error('HTTP_' + resp.status);
      data = await resp.json();
    } catch {
      card.querySelector('#lightSpinner')?.classList.add('d-none');
      return;
    }

    if (card.dataset.reqToken !== String(current)) return;
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
        } else if (isAuto || spinOn) next = AUTO_MS;
        else next = IDLE_MS;
        timer = setTimeout(tick, next);
      }
    }
    tick();
    return () => clearTimeout(timer);
  }

  let stopLightPoll = null;

  function initLightCardFromSelection() {
    const card = $('#lightCard');
    const capSelect = $('#capSelect');
    const groupSelect = $('#groupSelect');
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
    const groupSelect = $('#groupSelect');
    const deviceSelect = $('#deviceSelect');
    const capSelect = $('#capSelect');

    groupSelect?.addEventListener('change', () => {
      if (stopLightPoll) {
        stopLightPoll();
        stopLightPoll = null;
      }
      const card = $('#lightCard');
      if (card) resetLightCard(card, '請先選擇裝置與功能');
    });
    deviceSelect?.addEventListener('change', () => {
      if (stopLightPoll) {
        stopLightPoll();
        stopLightPoll = null;
      }
      const card = $('#lightCard');
      if (card) resetLightCard(card, '請先選擇功能');
    });

    capSelect?.addEventListener('change', () => {
      initLightCardFromSelection();
    });
    setTimeout(() => initLightCardFromSelection(), 0);

    // 用 switch 操作：開 spinner + 爆發輪詢
    document.addEventListener('change', (evt) => {
      const el = evt.target;
      if (!el.matches('.cap-toggle')) return;
      const card = $('#lightCard');
      if (!card || !card.dataset.statusUrl) return;
      card.querySelector('#lightSpinner')?.classList.remove('d-none');
      card.dataset.burst = String(FAST_BURST_TICKS);
      setTimeout(() => fetchLightState(card).catch(() => {}), 200);
    });

    document.addEventListener('visibilitychange', () => {
      const card = $('#lightCard');
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
