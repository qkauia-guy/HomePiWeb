// SweetAlert2 配置函數
function getSwalConfig(icon, title, html, confirmButtonText = '確定') {
  // 取得當前主題
  const theme = document.documentElement.getAttribute('data-theme') || 
                document.body.getAttribute('data-theme') || 
                (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  
  return {
    icon,
    title,
    html,
    confirmButtonText,
    // 移除 background 設定，讓 CSS 的毛玻璃效果生效
    color: theme === 'dark' ? '#f5f5f5' : '#333',
    confirmButtonColor: theme === 'dark' ? '#6366f1' : '#007bff',
    cancelButtonColor: theme === 'dark' ? '#6b7280' : '#6c757d',
    customClass: {
      popup: theme === 'dark' ? 'swal2-dark-popup' : 'swal2-light-popup',
      backdrop: theme === 'dark' ? 'swal2-dark-backdrop' : 'swal2-light-backdrop'
    }
  };
}

document.addEventListener('DOMContentLoaded', function () {
  const nodes = document.querySelectorAll('#flash-messages > div');
  nodes.forEach((n) => {
    const level = n.dataset.level || '';
    const msg = n.dataset.msg || '';
    const icon = level.includes('success')
      ? 'success'
      : level.includes('warning')
      ? 'warning'
      : level.includes('error')
      ? 'error'
      : 'info';
    const title = level.includes('success')
      ? '成功'
      : level.includes('warning')
      ? '提醒'
      : level.includes('error')
      ? '錯誤'
      : '訊息';
    
    Swal.fire(getSwalConfig(icon, title, msg));
  });
});
