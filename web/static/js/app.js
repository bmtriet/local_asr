document.addEventListener('DOMContentLoaded', () => {
  const statusDot = document.getElementById('system-status-dot');
  const statusText = document.getElementById('system-status-text');
  const historyContainer = document.getElementById('history-container');
  const btnRefresh = document.getElementById('btn-refresh-history');
  
  const metricPendingSamples = document.getElementById('metric-pending-samples');
  const metricTrainStatus = document.getElementById('metric-train-status');
  const metricTrainLoss = document.getElementById('metric-train-loss');
  const progressBar = document.getElementById('training-progress-bar');
  const btnStartTraining = document.getElementById('btn-start-training');
  
  const inputHotkey = document.getElementById('input-hotkey');
  const btnSaveHotkey = document.getElementById('btn-save-hotkey');
  const toggleGrammar = document.getElementById('toggle-grammar');

  // Check system status
  async function checkStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.status === 'ok') {
        statusDot.style.background = 'var(--emerald)';
        statusDot.style.boxShadow = '0 0 8px var(--emerald)';
        statusText.textContent = `Online • ${data.device.toUpperCase()} • ${data.model.split('/').pop()}`;
      }
    } catch (err) {
      statusDot.style.background = 'var(--rose)';
      statusDot.style.boxShadow = '0 0 8px var(--rose)';
      statusText.textContent = 'Backend Disconnected';
    }
  }

  // Pagination & Filter State
  let currentPage = 1;
  let pageSize = 10;
  let currentFilter = 'all';
  let searchQuery = '';
  let totalCount = 0;
  let totalPages = 1;
  let allCollapsed = true;

  const historyTotalBadge = document.getElementById('history-total-badge');
  const btnCollapseAll = document.getElementById('btn-collapse-all');
  const inputSearchHistory = document.getElementById('input-search-history');
  const filterBtns = document.querySelectorAll('.filter-btn');
  const selectPageSize = document.getElementById('select-page-size');
  const paginationInfo = document.getElementById('pagination-info');
  const paginationNumbers = document.getElementById('pagination-numbers');
  const btnPrevPage = document.getElementById('btn-prev-page');
  const btnNextPage = document.getElementById('btn-next-page');

  function truncateWords(text, maxWords = 20) {
    if (!text) return '(Empty)';
    const words = text.trim().split(/\s+/);
    if (words.length <= maxWords) return text;
    return words.slice(0, maxWords).join(' ') + '...';
  }

  // Load transcription history with pagination and search
  async function loadHistory() {
    try {
      const url = `/api/history?page=${currentPage}&limit=${pageSize}&filter_type=${currentFilter}&search=${encodeURIComponent(searchQuery)}`;
      const res = await fetch(url);
      const data = await res.json();
      const items = data.items || [];
      totalCount = data.total || 0;
      totalPages = data.total_pages || 1;
      currentPage = data.page || 1;

      if (historyTotalBadge) {
        historyTotalBadge.textContent = totalCount;
      }

      renderPagination();

      if (items.length === 0) {
        historyContainer.innerHTML = `
          <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
            ${searchQuery || currentFilter !== 'all' ? 'No spoken records matching your filter.' : `No recordings yet. Press hotkey <code>${inputHotkey.value}</code> to record your first utterance!`}
          </div>
        `;
        return;
      }

      historyContainer.innerHTML = items.map(item => {
        const fullText = (item.corrected_text || item.raw_text || '').trim();
        const preview = truncateWords(fullText, 20).replace(/"/g, '&quot;');
        const safeFull = fullText.replace(/"/g, '&quot;');
        return `
        <div class="history-item ${allCollapsed ? '' : 'open'}" id="item-${item.id}">
          <div class="history-item-header" onclick="toggleItemAccordion(${item.id})">
            <div class="item-summary">
              <svg class="item-arrow" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6-1.41-1.41z"/>
              </svg>
              <span class="item-preview-text" title="${safeFull}">${preview}</span>
            </div>
            <div class="item-header-meta">
              <span>${item.duration.toFixed(1)}s</span>
              <span class="item-badge ${item.is_reviewed ? 'badge-reviewed' : 'badge-unreviewed'}">
                ${item.is_reviewed ? 'Reviewed' : 'Raw'}
              </span>
            </div>
          </div>

          <div class="history-item-body">
            <div class="item-meta">
              <span>${item.timestamp} • Duration: ${item.duration.toFixed(1)}s</span>
              <span style="font-size: 0.75rem; color: var(--text-muted);">ID: #${item.id}</span>
            </div>

            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.75rem; color: var(--text-muted);">Original ASR Recognition (Source Spoken Text):</label>
              <div style="font-style: italic; color: var(--text-secondary); margin-top: 0.2rem; background: rgba(0,0,0,0.25); padding: 0.4rem 0.6rem; border-radius: 4px;">
                "${item.raw_text}"
              </div>
            </div>

            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-bottom: 0.25rem;">
                Ground Truth Text (Review & correct to train LoRA adapter):
              </label>
              <textarea class="edit-box" id="edit-text-${item.id}" rows="2">${item.corrected_text}</textarea>
            </div>

            <div class="item-actions">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                <audio controls preload="none" src="/api/audio/${item.id}"></audio>
                <button class="btn btn-danger" onclick="deleteItem(${item.id})" title="Delete recording">
                  Delete
                </button>
              </div>
              <button class="btn btn-primary" onclick="saveCorrection(${item.id})">
                Save Review
              </button>
            </div>
          </div>
        </div>
      `;
      }).join('');
    } catch (err) {
      historyContainer.innerHTML = '<p style="color: var(--rose); text-align: center; padding: 1.5rem;">Error loading history: ' + err.message + '</p>';
    }
  }

  // Toggle item accordion
  window.toggleItemAccordion = function(id) {
    const itemEl = document.getElementById(`item-${id}`);
    if (itemEl) {
      itemEl.classList.toggle('open');
    }
  };

  // Toggle Collapse/Expand all
  if (btnCollapseAll) {
    btnCollapseAll.addEventListener('click', () => {
      allCollapsed = !allCollapsed;
      btnCollapseAll.textContent = allCollapsed ? 'Collapse All' : 'Expand All';
      document.querySelectorAll('.history-item').forEach(el => {
        if (allCollapsed) el.classList.remove('open');
        else el.classList.add('open');
      });
    });
  }

  // Render pagination bar
  function renderPagination() {
    if (paginationInfo) {
      const start = totalCount === 0 ? 0 : (currentPage - 1) * pageSize + 1;
      const end = Math.min(currentPage * pageSize, totalCount);
      paginationInfo.textContent = `${start}-${end} of ${totalCount} records (Page ${currentPage}/${totalPages})`;
    }

    if (btnPrevPage) btnPrevPage.disabled = (currentPage <= 1);
    if (btnNextPage) btnNextPage.disabled = (currentPage >= totalPages);

    if (paginationNumbers) {
      paginationNumbers.innerHTML = '';
      const maxButtons = 5;
      let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
      let endPage = Math.min(totalPages, startPage + maxButtons - 1);
      if (endPage - startPage + 1 < maxButtons) {
        startPage = Math.max(1, endPage - maxButtons + 1);
      }

      for (let p = startPage; p <= endPage; p++) {
        const btn = document.createElement('button');
        btn.className = `page-num-btn ${p === currentPage ? 'active' : ''}`;
        btn.textContent = p;
        btn.onclick = () => {
          if (currentPage !== p) {
            currentPage = p;
            loadHistory();
          }
        };
        paginationNumbers.appendChild(btn);
      }
    }
  }

  // Prev / Next page handlers
  if (btnPrevPage) {
    btnPrevPage.addEventListener('click', () => {
      if (currentPage > 1) {
        currentPage--;
        loadHistory();
      }
    });
  }

  if (btnNextPage) {
    btnNextPage.addEventListener('click', () => {
      if (currentPage < totalPages) {
        currentPage++;
        loadHistory();
      }
    });
  }

  // Filter click handlers
  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      currentPage = 1;
      loadHistory();
    });
  });

  // Page size dropdown
  if (selectPageSize) {
    selectPageSize.addEventListener('change', (e) => {
      pageSize = parseInt(e.target.value, 10);
      currentPage = 1;
      loadHistory();
    });
  }

  // Search input debounced
  let searchTimer = null;
  if (inputSearchHistory) {
    inputSearchHistory.addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        searchQuery = e.target.value.trim();
        currentPage = 1;
        loadHistory();
      }, 300);
    });
  }

  // Delete item
  window.deleteItem = async function(id) {
    if (!confirm('Are you sure you want to delete this record and its audio file?')) return;
    try {
      const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
      if (res.ok) {
        loadHistory();
        checkTrainStatus();
      } else {
        alert('Could not delete record.');
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

  // Save correction
  window.saveCorrection = async function(id) {
    const textarea = document.getElementById(`edit-text-${id}`);
    const newText = textarea.value.trim();
    if (!newText) return;

    try {
      const res = await fetch(`/api/history/${id}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ corrected_text: newText })
      });
      if (res.ok) {
        loadHistory();
        checkTrainStatus();
      } else {
        alert('Could not save correction: ' + err.message);
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

  // Check LoRA Trainer status
  async function checkTrainStatus() {
    try {
      const res = await fetch('/api/train/status');
      const data = await res.json();
      metricPendingSamples.textContent = data.pending_samples || 0;
      metricTrainStatus.textContent = data.status.toUpperCase();
      
      if (data.is_training) {
        btnStartTraining.disabled = true;
        metricTrainLoss.textContent = data.current_loss > 0 ? data.current_loss : 'Calculating...';
        const total = (data.total_epochs || 1);
        const current = data.current_epoch || 0;
        const percent = Math.min(100, Math.round((current / total) * 100));
        progressBar.style.width = `${percent}%`;
      } else {
        btnStartTraining.disabled = (data.pending_samples === 0);
        metricTrainLoss.textContent = data.current_loss > 0 ? `${data.current_loss} (Completed)` : '-';
        if (data.status === 'completed') {
          progressBar.style.width = '100%';
        }
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Start LoRA training
  btnStartTraining.addEventListener('click', async () => {
    try {
      btnStartTraining.disabled = true;
      const res = await fetch('/api/train/start', { method: 'POST' });
      if (res.ok) {
        checkTrainStatus();
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to start training');
        btnStartTraining.disabled = false;
      }
    } catch (err) {
      alert('Connection error: ' + err.message);
      btnStartTraining.disabled = false;
    }
  });

  // Settings: Load, Record, and Save Hotkey
  const btnRecordHotkey = document.getElementById('btn-record-hotkey');
  const hotkeyHintText = document.getElementById('hotkey-hint-text');
  const presetBadges = document.querySelectorAll('.badge-preset');
  const toggleAddOriginPhrase = document.getElementById('toggle-add-origin-phrase');
  let isRecordingHotkey = false;

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      if (data.hotkey) {
        inputHotkey.value = data.hotkey;
        updatePresetActiveBadge(data.hotkey);
      }
      if (toggleGrammar) {
        toggleGrammar.checked = data.grammar_correction_enabled;
      }
      if (toggleAddOriginPhrase) {
        toggleAddOriginPhrase.checked = !!data.add_origin_phrase;
      }
    } catch (err) {
      console.error(err);
    }
  }

  function updatePresetActiveBadge(hotkeyVal) {
    presetBadges.forEach(badge => {
      if (badge.dataset.keys.toLowerCase() === hotkeyVal.toLowerCase()) {
        badge.classList.add('active');
      } else {
        badge.classList.remove('active');
      }
    });
  }

  // Preset badge click handlers
  presetBadges.forEach(badge => {
    badge.addEventListener('click', () => {
      const selectedKey = badge.dataset.keys;
      inputHotkey.value = selectedKey;
      updatePresetActiveBadge(selectedKey);
      if (isRecordingHotkey) stopHotkeyRecording();
    });
  });

  // Start / Stop Hotkey Recording
  function startHotkeyRecording() {
    isRecordingHotkey = true;
    inputHotkey.classList.add('recording');
    btnRecordHotkey.textContent = 'Recording...';
    btnRecordHotkey.classList.add('btn-primary');
    btnRecordHotkey.classList.remove('btn-secondary');
    hotkeyHintText.textContent = '🔴 Press your desired key combination now...';
    hotkeyHintText.classList.add('recording');
  }

  function stopHotkeyRecording() {
    isRecordingHotkey = false;
    inputHotkey.classList.remove('recording');
    btnRecordHotkey.textContent = 'Record Key';
    btnRecordHotkey.classList.remove('btn-primary');
    btnRecordHotkey.classList.add('btn-secondary');
    hotkeyHintText.textContent = 'Click "Record Key" and press your shortcut combination.';
    hotkeyHintText.classList.remove('recording');
  }

  if (btnRecordHotkey) {
    btnRecordHotkey.addEventListener('click', () => {
      if (!isRecordingHotkey) {
        startHotkeyRecording();
      } else {
        stopHotkeyRecording();
      }
    });
  }

  // Capture keyboard events when recording
  window.addEventListener('keydown', (e) => {
    if (!isRecordingHotkey) return;

    // Prevent default browser shortcuts while capturing
    e.preventDefault();
    e.stopPropagation();

    // Ignore standalone modifier presses
    const modifierKeys = ['Control', 'Alt', 'Shift', 'Meta'];
    if (modifierKeys.includes(e.key)) {
      return;
    }

    const parts = [];
    if (e.ctrlKey) parts.push('ctrl');
    if (e.altKey) parts.push('alt');
    if (e.shiftKey) parts.push('shift');

    let keyName = e.key.toLowerCase();
    if (e.code === 'Space') keyName = 'space';
    else if (keyName.startsWith('arrow')) keyName = keyName.replace('arrow', '');
    
    parts.push(keyName);

    const combo = parts.join('+');
    inputHotkey.value = combo;
    updatePresetActiveBadge(combo);
    stopHotkeyRecording();
  });

  btnSaveHotkey.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hotkey: inputHotkey.value.trim() })
      });
      if (res.ok) {
        alert(`Shortcut saved successfully: ${inputHotkey.value.trim()}\nSystem is ready to transcribe!`);
      }
    } catch (err) {
      alert('Error: ' + err.message);
    }
  });

  if (toggleGrammar) {
    toggleGrammar.addEventListener('change', async (e) => {
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ grammar_correction_enabled: e.target.checked })
        });
      } catch (err) {
        alert('Error saving grammar correction setting: ' + err.message);
      }
    });
  }

  if (toggleAddOriginPhrase) {
    toggleAddOriginPhrase.addEventListener('change', async (e) => {
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ add_origin_phrase: e.target.checked })
        });
      } catch (err) {
        alert('Error saving Add origin phrase setting: ' + err.message);
      }
    });
  }

  btnRefresh.addEventListener('click', loadHistory);

  // Initialize
  checkStatus();
  loadSettings();
  loadHistory();
  checkTrainStatus();

  // Periodic status poll
  setInterval(() => {
    checkTrainStatus();
  }, 2000);
});
