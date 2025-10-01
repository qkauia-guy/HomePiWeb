// 使用全局配置函數（如果存在）
function getSwalConfig(icon, title, html, confirmButtonText = '確定') {
  if (window.getSwalConfig) {
    return window.getSwalConfig(icon, title, html, confirmButtonText);
  }
  
  // 備援配置
  const theme = document.documentElement.getAttribute('data-theme') || 
                document.body.getAttribute('data-theme') || 
                (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  
  return {
    icon,
    title,
    html,
    confirmButtonText,
    colorScheme: theme,
    background: theme === 'dark' ? '#1a1a1a' : '#fff',
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
