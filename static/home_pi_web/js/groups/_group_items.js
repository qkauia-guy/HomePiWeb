// static/home_pi_web/js/groups/_group_items.js
(() => {
  // 展開：用內容實際高度動畫，並打開可見性
  function expand(actions) {
    // 先從 0 → 內容高度
    actions.style.visibility = 'visible';
    actions.style.opacity = '1';
    actions.style.borderTop = '1px solid var(--bs-border-color)';
    // 高度動畫
    const h = actions.scrollHeight; // 量到完整內容高度
    actions.style.height = h + 'px';
    // 動畫完把 height 設為 auto，讓內文換行也不截斷
    const onEnd = (e) => {
      if (e.propertyName !== 'height') return;
      actions.style.height = 'auto';
      actions.removeEventListener('transitionend', onEnd);
    };
    actions.addEventListener('transitionend', onEnd);
  }

  // 收合：從 auto/px → 0，結束後隱藏
  function collapse(actions) {
    // 把 auto 先固定成 px，才能有動畫
    const h = actions.scrollHeight;
    actions.style.height = h + 'px';
    // 強制 reflow，確保下一步動畫生效
    void actions.offsetHeight;
    // 正式收合
    actions.style.height = '0px';
    actions.style.opacity = '0';
    const onEnd = (e) => {
      if (e.propertyName !== 'height') return;
      actions.style.visibility = 'hidden';
      actions.style.borderTop = '0';
      actions.removeEventListener('transitionend', onEnd);
    };
    actions.addEventListener('transitionend', onEnd);
  }

  function onClick(e) {
    const item = e.target.closest('.groups-scope .device-item.toggleable');
    if (!item) return;
    const actions = item.nextElementSibling;
    if (!actions || !actions.classList.contains('device-actions')) return;

    const expanded = item.classList.toggle('expanded');
    item.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    expanded ? expand(actions) : collapse(actions);
  }

  function onKeydown(e) {
    const t = e.target;
    if (
      !t.classList ||
      !t.classList.contains('device-item') ||
      !t.classList.contains('toggleable')
    )
      return;
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      t.click();
    }
  }

  // 視窗尺寸變動：如果目前展開且 height 為 px，就重新量一次
  function onResize() {
    document
      .querySelectorAll('.groups-scope .device-item.expanded')
      .forEach((item) => {
        const actions = item.nextElementSibling;
        if (!actions || !actions.classList.contains('device-actions')) return;
        if (actions.style.height && actions.style.height !== 'auto') {
          actions.style.height = actions.scrollHeight + 'px';
        }
      });
  }

  // 綁一次（支援 Turbo）
  function bindOnce() {
    if (document.documentElement.dataset.grpBound === '1') return;
    document.documentElement.dataset.grpBound = '1';
    document.addEventListener('click', onClick);
    document.addEventListener('keydown', onKeydown);
    window.addEventListener('resize', onResize);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindOnce, { once: true });
  } else {
    bindOnce();
  }
  document.addEventListener('turbo:load', () => {
    document.documentElement.dataset.grpBound = '';
    bindOnce();
  });
})();
