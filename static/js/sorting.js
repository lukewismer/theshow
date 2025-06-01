document.addEventListener('DOMContentLoaded', () => {
    let sortKey   = 'ovr';
    let sortOrder = 'desc';  // start desc
  
    const tbody = document.querySelector('#predictionsTable tbody');
    const rows  = () => Array.from(tbody.querySelectorAll('tr'));
  
    function applyFilterSortAndPage() {
      // 1) run your existing filter logic here…
      //    (set row.style.display = 'none' or '' based on rarity & search)
  
      // 2) sort the *filtered* rows in the DOM
      const filtered = rows().filter(r => r.style.display !== 'none');
      filtered.sort((a, b) => {
        const aV = a.dataset[sortKey];
        const bV = b.dataset[sortKey];
        // numeric? try parseFloat, else string compare
        const aN = parseFloat(aV);
        const bN = parseFloat(bV);
        let cmp;
        if (!isNaN(aN) && !isNaN(bN)) {
          cmp = aN - bN;
        } else {
          cmp = aV.localeCompare(bV);
        }
        return sortOrder === 'asc' ? cmp : -cmp;
      });
      // re-append in order
      filtered.forEach(r => tbody.appendChild(r));
  
      // 3) trigger pagination to re-render based on this new order
      document.getElementById('pageSizeSelect').dispatchEvent(new Event('change'));
    }
  
    // wire headers
    document.querySelectorAll('#predictionsTable thead th[data-sort-key]')
      .forEach(th => {
        th.style.cursor = 'pointer';
        th.addEventListener('click', () => {
          const key = th.dataset.sortKey;
          if (sortKey === key) {
            sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
          } else {
            sortKey = key;
            sortOrder = 'asc';
          }
          applyFilterSortAndPage();
        });
      });
  
    // also hook up your rarityFilter and searchInput to call applyFilterSortAndPage()
    document.getElementById('rarityFilter').addEventListener('change', applyFilterSortAndPage);
    document.getElementById('searchInput').addEventListener('input', applyFilterSortAndPage);
  
    // initial render
    applyFilterSortAndPage();
  });