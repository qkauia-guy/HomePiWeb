document.addEventListener('DOMContentLoaded', () => {
  const toolTipAll = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  toolTipAll.forEach((t) => new bootstrap.Tooltip(t));
});
