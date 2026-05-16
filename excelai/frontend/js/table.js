(function () {
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function inferIcon(type) {
    switch ((type || '').toLowerCase()) {
      case 'date': return '📅';
      case 'currency': return '💲';
      case 'number': return '🔢';
      default: return '🔤';
    }
  }

  function looksLowConfidence(value, row, columnType, sourceType) {
    if (sourceType !== 'IMAGE') return false;
    const text = String(value ?? '');
    if (!text) return false;
    if (/^[A-Za-z0-9]+$/.test(text) && /[S5IlO0]/.test(text) && /\d/.test(text)) return true;
    if ((columnType || '').toLowerCase() === 'number' && /[ilOOsS]/.test(text)) return true;
    return false;
  }

  function getNumericStats(values) {
    const nums = values.map((value) => Number(String(value).replace(/[^\d.-]/g, ''))).filter((value) => Number.isFinite(value));
    if (!nums.length) return null;
    const sum = nums.reduce((acc, value) => acc + value, 0);
    return {
      min: Math.min(...nums),
      max: Math.max(...nums),
      avg: sum / nums.length,
      count: nums.length,
    };
  }

  function formatStats(stats) {
    if (!stats) return 'No numeric values';
    return `min ${stats.min.toFixed(2)} · max ${stats.max.toFixed(2)} · avg ${stats.avg.toFixed(2)} · count ${stats.count}`;
  }

  function sortData(columns, rows, sortState) {
    if (!sortState || sortState.index == null) return rows.slice();
    const { index, direction } = sortState;
    return rows.slice().sort((a, b) => {
      const left = a[index];
      const right = b[index];
      const leftValue = left == null ? '' : left;
      const rightValue = right == null ? '' : right;
      const leftNumber = Number(String(leftValue).replace(/[^\d.-]/g, ''));
      const rightNumber = Number(String(rightValue).replace(/[^\d.-]/g, ''));
      let comparison = 0;
      if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber)) {
        comparison = leftNumber - rightNumber;
      } else {
        comparison = String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' });
      }
      return direction === 'asc' ? comparison : -comparison;
    });
  }

  function renderSkeleton(container) {
    container.innerHTML = '<div class="skeleton">' + Array.from({ length: 8 }, () => '<div class="skeleton-row"></div>').join('') + '</div>';
  }

  function renderEmpty(container) {
    container.innerHTML = '<div class="empty-screen">No table data loaded yet.</div>';
  }

  function renderRawJson(container, data) {
    container.textContent = JSON.stringify(data, null, 2);
  }

  function renderTable(container, data, options = {}) {
    const state = {
      columns: data.columns || [],
      rows: data.rows || [],
      sourceType: data.source_type || 'TEXT',
      editMode: Boolean(options.editMode),
      sortState: options.sortState || null,
      page: options.page || 1,
      pageSize: options.pageSize || 50,
    };
    const sortedRows = sortData(state.columns, state.rows, state.sortState);
    const totalRows = sortedRows.length;
    const start = (state.page - 1) * state.pageSize;
    const visibleRows = sortedRows.slice(start, start + state.pageSize);

    if (!state.columns.length) {
      renderEmpty(container);
      return { totalRows: 0, totalColumns: 0, visibleRows: [] };
    }

    const table = document.createElement('table');
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    state.columns.forEach((column, index) => {
      const th = document.createElement('th');
      th.dataset.index = String(index);
      const indicator = state.sortState && state.sortState.index === index ? (state.sortState.direction === 'asc' ? '▲' : '▼') : '';
      th.innerHTML = `<span class="col-icon">${inferIcon(column.type)}</span> ${escapeHtml(column.name)} <span class="sort-indicator">${indicator}</span>`;
      if (typeof options.onSort === 'function') {
        th.addEventListener('click', () => options.onSort(index));
      }
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    const tbody = document.createElement('tbody');
    visibleRows.forEach((row, rowIndex) => {
      const tr = document.createElement('tr');
      tr.style.animation = `fadeUp 240ms ease ${rowIndex * 45}ms both`;
      state.columns.forEach((column, columnIndex) => {
        const td = document.createElement('td');
        const value = row[columnIndex];
        const flagged = looksLowConfidence(value, row, column.type, state.sourceType);
        td.innerHTML = escapeHtml(value);
        td.dataset.rowIndex = String(start + rowIndex);
        td.dataset.columnIndex = String(columnIndex);
        if (flagged) {
          td.classList.add('low-confidence');
          td.title = 'Low confidence — please verify';
        }
        if (state.editMode) {
          td.contentEditable = 'true';
          td.spellcheck = false;
          td.addEventListener('focus', () => td.classList.add('editing'));
          td.addEventListener('blur', () => td.classList.remove('editing'));
          td.addEventListener('input', () => {
            if (typeof options.onCellEdit === 'function') {
              options.onCellEdit(start + rowIndex, columnIndex, td.textContent);
            }
          });
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    table.appendChild(thead);
    table.appendChild(tbody);

    const scroll = document.createElement('div');
    scroll.className = 'table-scroll';
    scroll.appendChild(table);
    container.innerHTML = '';
    container.appendChild(scroll);

    const stats = state.columns.map((column, index) => getNumericStats(sortedRows.map((row) => row[index])));
    return {
      totalRows,
      totalColumns: state.columns.length,
      visibleRows,
      stats,
      pageCount: Math.max(1, Math.ceil(totalRows / state.pageSize)),
      start,
      end: Math.min(start + state.pageSize, totalRows),
      sortedRows,
    };
  }

  function renderStatsPanel(container, data) {
    if (!data || !data.columns || !data.rows) {
      container.innerHTML = '<div class="empty-screen">No column stats available.</div>';
      return;
    }
    const rows = data.rows || [];
    const cards = data.columns.map((column, index) => {
      const numericStats = getNumericStats(rows.map((row) => row[index]));
      return `<div class="stat-card"><strong>${escapeHtml(column.name)}</strong><span>${escapeHtml(formatStats(numericStats))}</span></div>`;
    }).join('');
    container.innerHTML = `<div class="stats-grid">${cards}</div>`;
  }

  window.ExcelAI = window.ExcelAI || {};
  window.ExcelAI.Table = {
    renderTable,
    renderSkeleton,
    renderRawJson,
    renderStatsPanel,
    sortData,
  };
})();
