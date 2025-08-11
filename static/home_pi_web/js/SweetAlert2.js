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
    Swal.fire({ icon, title, html: msg, confirmButtonText: '確定' });
  });
});

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
    Swal.fire({ icon, title, html: msg, confirmButtonText: '確定' });
  });
});
