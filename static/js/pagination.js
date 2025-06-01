document.addEventListener('DOMContentLoaded', () => {
    const tbody = document.querySelector('#predictionsTable tbody');
    const pageSizeSelect = document.getElementById('pageSizeSelect');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    let pageSize = +pageSizeSelect.value;
    let currentPage = 1;
    let totalPages = 1;
  
    function renderPage() {
      // grab all <tr> in their current DOM order
      const allRows = Array.from(tbody.querySelectorAll('tr'));
      // only those that aren’t filtered-out (filter sets display:none)
      const validRows = allRows.filter(r => r.style.display !== 'none');
  
      const totalRows = validRows.length;
      totalPages = Math.ceil(totalRows / pageSize) || 1;
      const start = (currentPage - 1) * pageSize;
      const end   = start + pageSize;
  
      // hide *all* rows, then show only the page-slice
      allRows.forEach(r => r.style.display = 'none');
      validRows.slice(start, end).forEach(r => r.style.display = '');
  
      pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
      prevBtn.disabled = currentPage === 1;
      nextBtn.disabled = currentPage === totalPages;
    }
  
    pageSizeSelect.addEventListener('change', () => {
      pageSize = +pageSizeSelect.value;
      currentPage = 1;
      renderPage();
    });
  
    prevBtn.addEventListener('click', () => {
      if (currentPage > 1) currentPage--, renderPage();
    });
  
    nextBtn.addEventListener('click', () => {
      if (currentPage < totalPages) currentPage++, renderPage();
    });
  
    // initial
    renderPage();
  });
  