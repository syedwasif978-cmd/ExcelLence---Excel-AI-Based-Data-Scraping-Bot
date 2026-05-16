(function () {
  function groupButton(action, icon, label, active = false, disabled = false) {
    return `
      <button class="toolbar-button ${active ? 'active' : ''}" data-action="${action}" ${disabled ? 'disabled' : ''}>
        <span class="state-dot"></span>
        <span class="icon">${icon}</span>
        <span class="label">${label}</span>
      </button>`;
  }

  function renderToolbar(container, state) {
    container.innerHTML = `
      <div class="toolbar-group">
        ${groupButton('new-session', '📁', 'New Session')}
        ${groupButton('export-xlsx', '💾', 'Export to Excel', false, !state.hasData)}
        ${groupButton('export-csv', '🗂️', 'Export as CSV', false, !state.hasData)}
      </div>
      <div class="toolbar-group">
        ${groupButton('mode-text', '🔤', 'Text Input', state.mode === 'text')}
        ${groupButton('mode-image', '🖼️', 'Upload Image', state.mode === 'image')}
        ${groupButton('mode-url', '🔗', 'From URL', state.mode === 'url')}
      </div>
      <div class="toolbar-group">
        ${groupButton('edit-mode', '✏️', 'Edit Mode', state.editMode)}
        ${groupButton('reextract', '🔄', 'Refresh', false, !state.canReextract)}
        ${groupButton('clear-table', '🗑️', 'Clear Table', false, !state.hasData)}
      </div>
      <div class="toolbar-group">
        ${groupButton('raw-json', '👁️', 'Raw JSON', state.showRawJson, !state.hasData)}
        ${groupButton('column-stats', '📊', 'Column Stats', state.showStats, !state.hasData)}
      </div>
      <div class="account-chip">
        <div class="account-avatar">${(state.user?.name || 'E').slice(0, 1).toUpperCase()}</div>
        <div class="account-copy">
          <strong>${state.user?.name || 'ExcelAI User'}</strong>
          <span>${state.user?.email || ''}</span>
        </div>
        ${groupButton('logout', '🔓', 'Logout')}
      </div>`;
  }

  window.ExcelAI = window.ExcelAI || {};
  window.ExcelAI.Toolbar = { renderToolbar };
})();
