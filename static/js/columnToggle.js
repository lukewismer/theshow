document.addEventListener('DOMContentLoaded', () => {
    // Listen for column checkbox changes
    document.querySelectorAll('.column-toggle input[type="checkbox"]').forEach(chk => {
      chk.addEventListener('change', e => {
        const idx = parseInt(e.target.dataset.col, 10) + 1; // 1-based
        document.querySelectorAll(
          `#predictionsTable th:nth-child(${idx}), #predictionsTable td:nth-child(${idx})`
        ).forEach(cell => {
          cell.style.display = e.target.checked ? '' : 'none';
        });
      });
    });
  });
  