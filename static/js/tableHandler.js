document.addEventListener('DOMContentLoaded', () => {
  const tbody       = document.querySelector('#predictionsTable tbody');
  const theadRow    = document.querySelector('#predictionsTable thead tr');
  const nameInput   = document.getElementById('searchInput');
  const rarityInput = document.getElementById('rarityFilter');
  const pageSizeSel = document.getElementById('pageSizeSelect');
  const prevBtn     = document.getElementById('prevPage');
  const nextBtn     = document.getElementById('nextPage');
  const pageInfo    = document.getElementById('pageInfo');

  // Helper to get all <th> that have data-sort-key (i.e. all sortable columns)
  const sortableHeaders = () =>
    Array.from(document.querySelectorAll('#predictionsTable thead th[data-sort-key]'));

  let sortKey     = 'ovr';      // default sort column
  let sortOrder   = 'desc';     // default descending
  let pageSize    = +pageSizeSel.value;
  let currentPage = 1;

  // ——— Utility: get all <tr> rows inside <tbody> ———
  function getAllRows() {
    return Array.from(tbody.querySelectorAll('tr'));
  }

  // ——— Filtering by name + rarity ———
  function matchesFilter(row) {
    const nameMatch   = row.dataset.name.toLowerCase().includes(nameInput.value.toLowerCase());
    const rarityMatch = (rarityInput.value === 'all' || row.dataset.rarity === rarityInput.value);
    return nameMatch && rarityMatch;
  }

  // ——— Sorting helper ———
  function applySort(rows) {
    return rows.sort((a, b) => {
      const aV = a.dataset[sortKey] || '';
      const bV = b.dataset[sortKey] || '';
      const aN = parseFloat(aV), bN = parseFloat(bV);
      let cmp;
      if (!isNaN(aN) && !isNaN(bN)) {
        cmp = aN - bN;
      } else {
        cmp = aV.localeCompare(bV);
      }
      return (sortOrder === 'asc' ? cmp : -cmp);
    });
  }

  async function fillPrices() {
    // only grab the rows that are currently visible
    const rows = getAllRows().filter(r => r.style.display === '');
    // 1) build an array of “fetch+update” promises, one per row
    const allPromises = rows.map(row => {
      const uuid    = row.dataset.uuid;
      const priceTd = row.querySelector('.market-price');
      // if that row was already fetched, skip it immediately
      if (priceTd && priceTd.dataset.fetched) {
        return Promise.resolve();
      }

      // otherwise, do one fetch() for this uuid and then update that single row
      return fetch(`/api/market_price/${uuid}`)
        .then(res => res.json())
        .then(data => {
          // Profit %
          const pctTd = row.querySelector('.pred-profit-pct');
          if (pctTd) {
            const pctVal = (typeof data.predicted_profit_pct !== 'undefined')
                         ? data.predicted_profit_pct
                         : '–';
            pctTd.textContent = pctVal;
            row.dataset.predicted_profit_pct = pctVal.toString();
          }

          // Price
          const priceTd = row.querySelector('.market-price');
          if (priceTd) {
            const displayPrice = (data.buy && data.buy !== '-')
                               ? data.buy
                               : (data.sell || '–');
            priceTd.textContent = displayPrice;
            row.dataset.market_price = (data.buy != null)
                                     ? data.buy
                                     : (data.sell != null ? data.sell : '0');
          }

          // QS Actual
          const qsActTd = row.querySelector('.qs-actual');
          if (qsActTd) {
            const val = (data.qs_actual != null) ? data.qs_actual : '–';
            qsActTd.textContent = val;
            row.dataset.qs_actual = (data.qs_actual != null)
                                  ? data.qs_actual.toString()
                                  : '0';
          }

          // QS Pred Low
          const qsLowTd = row.querySelector('.qs-pred-low');
          if (qsLowTd) {
            const val = (data.qs_pred_low != null) ? data.qs_pred_low : '–';
            qsLowTd.textContent = val;
            row.dataset.qs_pred_low = (data.qs_pred_low != null)
                                    ? data.qs_pred_low.toString()
                                    : '0';
          }

          // QS Avg
          const qsAvgTd = row.querySelector('.qs-pred');
          if (qsAvgTd) {
            const val = (data.qs_pred != null) ? data.qs_pred : '–';
            qsAvgTd.textContent = val;
            row.dataset.qs_pred = (data.qs_pred != null)
                                ? data.qs_pred.toString()
                                : '0';
          }

          // QS Pred High
          const qsHighTd = row.querySelector('.qs-pred-high');
          if (qsHighTd) {
            const val = (data.qs_pred_high != null) ? data.qs_pred_high : '–';
            qsHighTd.textContent = val;
            row.dataset.qs_pred_high = (data.qs_pred_high != null)
                                     ? data.qs_pred_high.toString()
                                     : '0';
          }

          // Predicted Profit
          const profTd = row.querySelector('.pred-profit');
          if (profTd) {
            const val = (data.predicted_profit != null) ? data.predicted_profit : '–';
            profTd.textContent = val;
            row.dataset.predicted_profit = (data.predicted_profit != null)
                                         ? data.predicted_profit.toString()
                                         : '0';
          }

          // Predicted Profit Low
          const profLowTd = row.querySelector('.pred-profit-low');
          if (profLowTd) {
            const val = (data.predicted_profit_low != null) ? data.predicted_profit_low : '–';
            profLowTd.textContent = val;
            row.dataset.predicted_profit_low = (data.predicted_profit_low != null)
                                             ? data.predicted_profit_low.toString()
                                             : '0';
          }

          // Predicted Profit High
          const profHighTd = row.querySelector('.pred-profit-high');
          if (profHighTd) {
            const val = (data.predicted_profit_high != null) ? data.predicted_profit_high : '–';
            profHighTd.textContent = val;
            row.dataset.predicted_profit_high = (data.predicted_profit_high != null)
                                              ? data.predicted_profit_high.toString()
                                              : '0';
          }

          // EV Profit
          const evProfitTd = row.querySelector('.pred-ev-profit');
          if (evProfitTd) {
            const val = (data.predicted_ev_profit != null) ? data.predicted_ev_profit : '–';
            evProfitTd.textContent = val;
            row.dataset.predicted_ev_profit = (data.predicted_ev_profit != null)
                                            ? data.predicted_ev_profit.toString()
                                            : '0';
          }

          // finally mark them as fetched
          [
            priceTd, qsActTd, qsLowTd, qsAvgTd, qsHighTd,
            profTd, profLowTd, profHighTd, evProfitTd, pctTd
          ].forEach(td => {
            if (td) td.dataset.fetched = '1';
          });
        })
        .catch(() => {
          // on any error, write “Err”
          [
            row.querySelector('.market-price'),
            row.querySelector('.qs-actual'),
            row.querySelector('.qs-pred-low'),
            row.querySelector('.qs-pred'),
            row.querySelector('.qs-pred-high'),
            row.querySelector('.pred-profit'),
            row.querySelector('.pred-profit-low'),
            row.querySelector('.pred-profit-high'),
            row.querySelector('.pred-ev-profit'),
            row.querySelector('.pred-profit-pct')
          ].forEach(td => {
            if (td) td.textContent = 'Err';
          });
        });
    });

    // 2) wait until all of them finish (in parallel)
    await Promise.all(allPromises);
  }

  // ——— Main “render” function: filter → sort → paginate → show → fillPrices ———
  function render() {
    const allRows = getAllRows();
    const filtered = allRows.filter(matchesFilter);
    const sorted   = applySort(filtered);

    // Reorder DOM to match sorted
    sorted.forEach(row => tbody.appendChild(row));

    // Pagination
    const totalRows  = sorted.length;
    const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
    currentPage = Math.min(currentPage, totalPages);

    const start = (currentPage - 1) * pageSize;
    const end   = start + pageSize;
    const pageRows = sorted.slice(start, end);

    // Hide all, then show only current page
    allRows.forEach(r => r.style.display = 'none');
    pageRows.forEach(r => r.style.display = '');

    // Update nav
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    prevBtn.disabled = (currentPage === 1);
    nextBtn.disabled = (currentPage === totalPages);

    // Fill prices/qs/profit for visible rows
    fillPrices();
  }

  // ——— Attach sorting listeners to any <th data-sort-key> ———
  function attachSortingListeners() {
    sortableHeaders().forEach(th => {
      th.style.cursor = 'pointer';
      th.addEventListener('click', () => {
        const key = th.dataset.sortKey;
        if (sortKey === key) {
          sortOrder = (sortOrder === 'asc' ? 'desc' : 'asc');
        } else {
          sortKey   = key;
          sortOrder = 'asc';
        }
        currentPage = 1;
        render();
      });
    });
  }

  // ——— Filtering inputs ———
  [nameInput, rarityInput].forEach(ctrl =>
    ctrl.addEventListener(nameInput === ctrl ? 'input' : 'change', () => {
      currentPage = 1;
      render();
    })
  );

  // ——— Pagination controls ———
  pageSizeSel.addEventListener('change', () => {
    pageSize = +pageSizeSel.value;
    currentPage = 1;
    render();
  });
  prevBtn.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      render();
    }
  });
  nextBtn.addEventListener('click', () => {
    currentPage++;
    render();
  });

  // ========== DYNAMIC COLUMN TOGGLE LOGIC ==========

  // 1) Build a map from uuid → player object for O(1) lookup
  const playerByUuid = {};
  allData.forEach(player => {
    playerByUuid[player.uuid] = player;
  });

  // 2) Helper to get the label text of a checkbox by its data-key
  function getLabelForKey(key) {
    const checkbox = document.querySelector(`.column-group input[data-key="${key}"]`);
    if (!checkbox) return key;
    return checkbox.parentElement.textContent.trim();
  }

  // 3) Add a column: create <th> and <td>s, and store values in row.dataset
  function addColumn(key) {
    const labelText = getLabelForKey(key) || key;

    // 1) Create and append the new <th>
    const th = document.createElement('th');
    th.setAttribute('data-key', key);
    th.setAttribute('data-sort-key', key);
    th.innerHTML = `${labelText} ⇅`;
    th.style.cursor = 'pointer';
    theadRow.appendChild(th);

    // Attach a sorting listener to that <th>
    th.addEventListener('click', () => {
      if (sortKey === key) {
        sortOrder = (sortOrder === 'asc' ? 'desc' : 'asc');
      } else {
        sortKey = key;
        sortOrder = 'asc';
      }
      currentPage = 1;
      render();
    });

    // 2) For every single row (visible or not), append a <td> and set row.dataset[key]
    getAllRows().forEach(row => {
      const uuid = row.dataset.uuid;
      const player = playerByUuid[uuid] || {};
      let value = player[key];

      if (value === undefined || value === null) {
        value = '–';
      }

      // Store it in dataset so sorting works later
      row.dataset[key] = value.toString();

      // Create the actual <td> cell, even if row is currently hidden
      const td = document.createElement('td');
      td.setAttribute('data-key', key);
      td.innerText = value;
      row.appendChild(td);
    });
  }

  // 4) Remove a column: delete its <th>, all <td>, and remove row.dataset
  function removeColumn(key) {
    // 4a) Remove <th>
    const th = document.querySelector(`#predictionsTable thead th[data-key="${key}"]`);
    if (th) th.remove();

    // 4b) For every row, remove <td> and dataset
    getAllRows().forEach(row => {
      const td = row.querySelector(`td[data-key="${key}"]`);
      if (td) td.remove();
      delete row.dataset[key];
    });
  }

  // 5) Attach listeners to all checkboxes in column‐groups
  document.querySelectorAll('.column-group input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', () => {
      const key = cb.dataset.key;
      if (cb.checked) {
        addColumn(key);
      } else {
        removeColumn(key);
      }
      // Reset to page 1 after toggling a column
      currentPage = 1;
      render();
    });
  });

  // After wiring toggles, initialize sorting for whatever <th> exist initially
  attachSortingListeners();

  // 6) Initial render
  render();

  // Show any non-default columns that were already checked on page load
  document.querySelectorAll('.column-group input[type="checkbox"]').forEach(cb => {
    if (cb.checked) {
      const key = cb.dataset.key;
      const isDefault = [
        'card','name','ovr','delta_rank_pred','confidence_percentage',
        'market_price','qs_pred','predicted_profit','predicted_profit_pct'
      ].includes(key);
      if (!isDefault) addColumn(key);
    }
  });

  // ========== “Search within dropdown” logic ==========

  document.querySelectorAll('.column-search').forEach(search => {
    search.addEventListener('input', function() {
      const group = this.dataset.group;
      const term = this.value.toLowerCase();
      // The .column-group container is the next sibling of this input
      const container = this.parentElement.querySelector(`.column-group[data-group="${group}"]`);
      if (!container) return;
      container.querySelectorAll('label').forEach(label => {
        const text = label.textContent.toLowerCase();
        label.style.display = text.includes(term) ? 'flex' : 'none';
      });
    });
  });

  // ========== Close any open dropdown when clicking outside ==========
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.column-dropdown')) {
      document.querySelectorAll('.column-dropdown').forEach(details => {
        details.open = false;
      });
    }
  });

  // ▼▼▼ ADD THIS “clear-filters” LOGIC ▼▼▼
  // Whenever the user clicks “× Clear All” in a dropdown,
  // uncheck every checkbox in that group and fire its change event.
  document.querySelectorAll('.clear-filters').forEach(btn => {
    btn.addEventListener('click', () => {
      // 1) Which group (details/attributes/predictions/market/…)
      const groupName = btn.dataset.group;
      // 2) Find all checkboxes in that .column-group[data-group="…"]
      const boxes = document.querySelectorAll(
        `.column-group[data-group="${groupName}"] input[type="checkbox"]`
      );
      boxes.forEach(cb => {
        if (cb.checked) {
          // If it’s currently checked, uncheck it
          cb.checked = false;
          // Dispatch a “change” so your existing add/remove‐column logic runs
          const ev = new Event('change', { bubbles: true });
          cb.dispatchEvent(ev);
        }
      });
      // 3) Remove the green “filter-active” class from the <summary>
      const detailsElem = document.querySelector(
        `.column-toggle[data-group="${groupName}"]`
      );
      if (detailsElem) {
        const summaryBtn = detailsElem.querySelector('summary');
        summaryBtn.classList.remove('filter-active');
      }
    });
  });
  // ▲▲▲ END OF “clear-filters” LOGIC ▲▲▲

  // ========== Highlight filter buttons when any box is checked ==========
  document.querySelectorAll('.column-toggle').forEach(detailsElem => {
    const groupName  = detailsElem.getAttribute('data-group');
    const summaryBtn = detailsElem.querySelector('summary');
    const checkboxes = Array.from(
      document.querySelectorAll(`.column-group[data-group="${groupName}"] input[type="checkbox"]`)
    );

    const refreshButtonState = () => {
      const anyChecked = checkboxes.some(cb => cb.checked);
      if (anyChecked) {
        summaryBtn.classList.add('filter-active');
      } else {
        summaryBtn.classList.remove('filter-active');
      }
    };

    checkboxes.forEach(cb => {
      cb.addEventListener('change', () => {
        refreshButtonState();
      });
    });

    // On initial page load, highlight if any box is already checked
    refreshButtonState();
  });
  // ─────────────────────────────────────────────────────────────────────────────
});  // ←← closes DOMContentLoaded
