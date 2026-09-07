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
      const tabBadgeHistory = document.getElementById('tab-badge-history');
      if (tabBadgeHistory) {
        tabBadgeHistory.textContent = totalCount;
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

  const btnExportLora = document.getElementById('btn-export-lora');
  if (btnExportLora) {
    btnExportLora.addEventListener('click', () => {
      const activeProf = selectActiveProfile ? selectActiveProfile.value : 'default';
      window.location.href = `/api/train/export?profile_id=${encodeURIComponent(activeProf)}`;
    });
  }

  // Settings: Load, Record, and Save Hotkey
  const btnRecordHotkey = document.getElementById('btn-record-hotkey');
  const hotkeyHintText = document.getElementById('hotkey-hint-text');
  const presetBadges = document.querySelectorAll('.badge-preset');
  const toggleQwen25Enabled = document.getElementById('toggle-qwen25-enabled');
  const qwenMasterCard = document.getElementById('qwen-master-card');
  const qwenStatusHint = document.getElementById('qwen-status-hint');
  const qwenFeaturesGroup = document.getElementById('qwen-features-group');
  const toggleAddOriginPhrase = document.getElementById('toggle-add-origin-phrase');

  // Translation Provider DOM Elements
  const radioTransProvLocal = document.getElementById('radio-trans-prov-local');
  const radioTransProvRemote = document.getElementById('radio-trans-prov-remote');
  const transLocalContainer = document.getElementById('trans-local-container');
  const transRemoteContainer = document.getElementById('trans-remote-container');
  const inputTransApiUrl = document.getElementById('input-trans-api-url');
  const inputTransModelName = document.getElementById('input-trans-model-name');
  const inputTransApiKey = document.getElementById('input-trans-api-key');
  const btnTestTransApi = document.getElementById('btn-test-trans-api');
  const btnSaveTransApi = document.getElementById('btn-save-trans-api');
  const transApiTestStatus = document.getElementById('trans-api-test-status');

  // ASR Provider DOM Elements (Docker / Remote decoupling)
  const radioAsrProvLocal = document.getElementById('radio-asr-prov-local');
  const radioAsrProvRemote = document.getElementById('radio-asr-prov-remote');
  const asrLocalContainer = document.getElementById('asr-local-container');
  const asrRemoteContainer = document.getElementById('asr-remote-container');
  const inputAsrApiEndpoint = document.getElementById('input-asr-api-endpoint');
  const inputAsrApiKey = document.getElementById('input-asr-api-key');
  const btnTestAsrApi = document.getElementById('btn-test-asr-api');
  const btnSaveAsrApi = document.getElementById('btn-save-asr-api');
  const asrApiTestStatus = document.getElementById('asr-api-test-status');

  const selectOsdPosition = document.getElementById('select-osd-position');
  const inputOsdDuration = document.getElementById('input-osd-duration');
  const toggleOsdAlwaysOn = document.getElementById('toggle-osd-always-on');
  const osdDurationGroup = document.getElementById('osd-duration-group');
  const btnSaveOsd = document.getElementById('btn-save-osd');

  // UX Settings DOM Elements
  const toggleSoundCues = document.getElementById('toggle-sound-cues');
  const selectHotkeyMode = document.getElementById('select-hotkey-mode');
  const toggleVadEnabled = document.getElementById('toggle-vad-enabled');
  const inputVadTimeout = document.getElementById('input-vad-timeout');
  const vadTimeoutGroup = document.getElementById('vad-timeout-group');
  const toggleStreamingTranscription = document.getElementById('toggle-streaming-transcription');
  const webStreamingPlayground = document.getElementById('web-streaming-playground');
  const btnToggleWebStreaming = document.getElementById('btn-toggle-web-streaming');
  const webStreamingMicIcon = document.getElementById('web-streaming-mic-icon');
  const webStreamingBtnLabel = document.getElementById('web-streaming-btn-label');
  const webStreamingLiveBox = document.getElementById('web-streaming-live-box');
  const btnSaveUxSettings = document.getElementById('btn-save-ux-settings');

  let isRecordingHotkey = false;

  function setTransProviderUi(provider) {
    const isRemote = (provider === 'remote_api');
    if (radioTransProvRemote) radioTransProvRemote.checked = isRemote;
    if (radioTransProvLocal) radioTransProvLocal.checked = !isRemote;
    if (transRemoteContainer) transRemoteContainer.style.display = isRemote ? 'block' : 'none';
    if (transLocalContainer) transLocalContainer.style.display = isRemote ? 'none' : 'block';

    if (qwenFeaturesGroup) {
      qwenFeaturesGroup.style.opacity = '1.0';
      qwenFeaturesGroup.style.pointerEvents = 'auto';
    }
  }

  function setAsrProviderUi(provider) {
    const isRemote = (provider === 'remote_api');
    if (radioAsrProvRemote) radioAsrProvRemote.checked = isRemote;
    if (radioAsrProvLocal) radioAsrProvLocal.checked = !isRemote;
    if (asrRemoteContainer) asrRemoteContainer.style.display = isRemote ? 'block' : 'none';
    if (asrLocalContainer) asrLocalContainer.style.display = isRemote ? 'none' : 'block';
  }

  function updateQwenUiState(enabled) {
    if (toggleQwen25Enabled) {
      toggleQwen25Enabled.checked = enabled;
    }
    if (qwenMasterCard) {
      if (enabled) {
        qwenMasterCard.classList.remove('disabled');
      } else {
        qwenMasterCard.classList.add('disabled');
      }
    }
    if (qwenStatusHint) {
      if (enabled) {
        qwenStatusHint.style.color = "var(--emerald)";
        qwenStatusHint.textContent = "Active: Translation & Grammar available locally.";
      } else {
        qwenStatusHint.style.color = "var(--text-muted)";
        qwenStatusHint.textContent = "Disabled: Model not loaded. Saves ~1.0GB memory & boots faster.";
      }
    }
    if (qwenFeaturesGroup && (!radioTransProvRemote || !radioTransProvRemote.checked)) {
      qwenFeaturesGroup.style.opacity = enabled ? "1.0" : "0.4";
      qwenFeaturesGroup.style.pointerEvents = enabled ? "auto" : "none";
    }
  }

  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      if (data.hotkey) {
        inputHotkey.value = data.hotkey;
        updatePresetActiveBadge(data.hotkey);
      }

      // Load ASR Provider Settings (Docker / Local decoupling)
      if (data.asr_provider) {
        setAsrProviderUi(data.asr_provider);
      }
      if (inputAsrApiEndpoint && data.asr_api_endpoint) {
        inputAsrApiEndpoint.value = data.asr_api_endpoint;
      }
      if (inputAsrApiKey && data.asr_api_key) {
        inputAsrApiKey.value = data.asr_api_key;
      }

      // Load Translation Provider Settings
      if (data.translation_provider) {
        setTransProviderUi(data.translation_provider);
      }
      if (inputTransApiUrl && data.translation_api_base_url) {
        inputTransApiUrl.value = data.translation_api_base_url;
      }
      if (inputTransModelName && data.translation_model_name) {
        inputTransModelName.value = data.translation_model_name;
      }
      if (inputTransApiKey && data.translation_api_key) {
        inputTransApiKey.value = data.translation_api_key;
      }

      if (data.qwen25_enabled !== undefined) {
        updateQwenUiState(!!data.qwen25_enabled);
      }
      if (toggleGrammar) {
        toggleGrammar.checked = data.grammar_correction_enabled;
      }
      if (toggleAddOriginPhrase) {
        toggleAddOriginPhrase.checked = !!data.add_origin_phrase;
      }
      if (selectOsdPosition && data.osd_position) {
        selectOsdPosition.value = data.osd_position;
      }
      if (inputOsdDuration && data.osd_duration !== undefined) {
        inputOsdDuration.value = data.osd_duration;
      }
      if (toggleOsdAlwaysOn) {
        toggleOsdAlwaysOn.checked = !!data.osd_always_on;
        if (osdDurationGroup) {
          osdDurationGroup.style.opacity = toggleOsdAlwaysOn.checked ? "0.4" : "1.0";
        }
      }
      // Load UX Settings
      if (toggleSoundCues && data.sound_cues_enabled !== undefined) {
        toggleSoundCues.checked = !!data.sound_cues_enabled;
      }
      if (selectHotkeyMode && data.hotkey_mode) {
        selectHotkeyMode.value = data.hotkey_mode;
      }
      if (toggleVadEnabled && data.vad_enabled !== undefined) {
        toggleVadEnabled.checked = !!data.vad_enabled;
        if (vadTimeoutGroup) {
          vadTimeoutGroup.style.opacity = toggleVadEnabled.checked ? "1.0" : "0.4";
        }
      }
      if (inputVadTimeout && data.vad_silence_timeout !== undefined) {
        inputVadTimeout.value = data.vad_silence_timeout;
      }
      if (toggleStreamingTranscription && data.streaming_transcription_enabled !== undefined) {
        toggleStreamingTranscription.checked = !!data.streaming_transcription_enabled;
        if (webStreamingPlayground) {
          webStreamingPlayground.style.display = toggleStreamingTranscription.checked ? "block" : "none";
        }
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
    hotkeyHintText.textContent = 'Listening: Press your desired key combination now...';
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

  // ASR Provider Switch Events (Local vs Docker/Remote API)
  if (radioAsrProvLocal) {
    radioAsrProvLocal.addEventListener('change', async (e) => {
      if (e.target.checked) {
        setAsrProviderUi('local');
        try {
          await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asr_provider: 'local' })
          });
        } catch (err) {
          console.error('Error switching ASR provider to local:', err);
        }
      }
    });
  }

  if (radioAsrProvRemote) {
    radioAsrProvRemote.addEventListener('change', async (e) => {
      if (e.target.checked) {
        setAsrProviderUi('remote_api');
        try {
          await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asr_provider: 'remote_api' })
          });
        } catch (err) {
          console.error('Error switching ASR provider to remote_api:', err);
        }
      }
    });
  }

  // Test ASR API connection (Docker / Remote endpoint)
  if (btnTestAsrApi) {
    btnTestAsrApi.addEventListener('click', async () => {
      const endpoint = (inputAsrApiEndpoint ? inputAsrApiEndpoint.value : '').trim();
      const apiKey = (inputAsrApiKey ? inputAsrApiKey.value : '').trim();

      if (!endpoint) {
        alert('Please enter an ASR Endpoint URL (e.g. http://127.0.0.1:9001/v1/audio/transcriptions).');
        return;
      }

      btnTestAsrApi.disabled = true;
      btnTestAsrApi.textContent = 'Testing...';
      if (asrApiTestStatus) {
        asrApiTestStatus.style.display = 'block';
        asrApiTestStatus.style.color = 'var(--text-secondary)';
        asrApiTestStatus.textContent = 'Testing connection with Docker/remote ASR endpoint...';
      }

      try {
        const res = await fetch('/api/settings/test-asr-api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            endpoint: endpoint,
            api_key: apiKey
          })
        });
        const data = await res.json();
        if (data.success) {
          asrApiTestStatus.style.color = 'var(--emerald)';
          asrApiTestStatus.innerHTML = `<strong>Connected (${data.latency_ms}ms)!</strong> Docker endpoint is responding.`;
        } else {
          asrApiTestStatus.style.color = 'var(--rose)';
          asrApiTestStatus.innerHTML = `<strong>Failed:</strong> ${escapeHtml(data.message || data.error)}`;
        }
      } catch (err) {
        asrApiTestStatus.style.color = 'var(--rose)';
        asrApiTestStatus.textContent = `Error: ${err.message}`;
      } finally {
        btnTestAsrApi.disabled = false;
        btnTestAsrApi.innerHTML = `
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <span>Test Connection</span>
        `;
      }
    });
  }

  // Save ASR API configuration
  if (btnSaveAsrApi) {
    btnSaveAsrApi.addEventListener('click', async () => {
      const endpoint = (inputAsrApiEndpoint ? inputAsrApiEndpoint.value : '').trim();
      const apiKey = (inputAsrApiKey ? inputAsrApiKey.value : '').trim();

      if (!endpoint) {
        alert('Please enter an ASR Endpoint URL.');
        return;
      }

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            asr_provider: 'remote_api',
            asr_api_endpoint: endpoint,
            asr_api_key: apiKey
          })
        });
        if (res.ok) {
          alert('Docker / Remote ASR Configuration saved successfully!');
        } else {
          alert('Failed to save ASR API Configuration.');
        }
      } catch (err) {
        alert('Error saving ASR API config: ' + err.message);
      }
    });
  }

  // Translation Provider Switch Events
  if (radioTransProvLocal) {
    radioTransProvLocal.addEventListener('change', async (e) => {
      if (e.target.checked) {
        setTransProviderUi('local');
        try {
          await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ translation_provider: 'local' })
          });
        } catch (err) {
          console.error('Error switching translation provider to local:', err);
        }
      }
    });
  }

  if (radioTransProvRemote) {
    radioTransProvRemote.addEventListener('change', async (e) => {
      if (e.target.checked) {
        setTransProviderUi('remote_api');
        try {
          await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ translation_provider: 'remote_api' })
          });
        } catch (err) {
          console.error('Error switching translation provider to remote_api:', err);
        }
      }
    });
  }

  // Test Translation API connection
  if (btnTestTransApi) {
    btnTestTransApi.addEventListener('click', async () => {
      const baseUrl = (inputTransApiUrl ? inputTransApiUrl.value : '').trim();
      const modelName = (inputTransModelName ? inputTransModelName.value : '').trim();
      const apiKey = (inputTransApiKey ? inputTransApiKey.value : '').trim();

      if (!baseUrl) {
        alert('Please enter an API Base URL (e.g. http://localhost:11434/v1).');
        return;
      }
      if (!modelName) {
        alert('Please enter a model name (e.g. qwen2.5:0.5b).');
        return;
      }

      btnTestTransApi.disabled = true;
      btnTestTransApi.textContent = 'Testing...';
      if (transApiTestStatus) {
        transApiTestStatus.style.display = 'block';
        transApiTestStatus.style.color = 'var(--text-secondary)';
        transApiTestStatus.textContent = 'Connecting to endpoint...';
      }

      try {
        const res = await fetch('/api/settings/test-translation-api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            base_url: baseUrl,
            model_name: modelName,
            api_key: apiKey,
            sample_text: "Xin chào!"
          })
        });
        const data = await res.json();
        if (data.success) {
          transApiTestStatus.style.color = 'var(--emerald)';
          transApiTestStatus.innerHTML = `<strong>Connected (${data.latency_ms}ms)!</strong> Sample reply: <em>"${escapeHtml(data.reply)}"</em>`;
        } else {
          transApiTestStatus.style.color = 'var(--rose)';
          transApiTestStatus.innerHTML = `<strong>Failed:</strong> ${escapeHtml(data.message || data.error)}`;
        }
      } catch (err) {
        transApiTestStatus.style.color = 'var(--rose)';
        transApiTestStatus.textContent = `Error: ${err.message}`;
      } finally {
        btnTestTransApi.disabled = false;
        btnTestTransApi.innerHTML = `
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          <span>Test Connection</span>
        `;
      }
    });
  }

  // Save Translation API configuration
  if (btnSaveTransApi) {
    btnSaveTransApi.addEventListener('click', async () => {
      const baseUrl = (inputTransApiUrl ? inputTransApiUrl.value : '').trim();
      const modelName = (inputTransModelName ? inputTransModelName.value : '').trim();
      const apiKey = (inputTransApiKey ? inputTransApiKey.value : '').trim();

      if (!baseUrl) {
        alert('Please enter an API Base URL.');
        return;
      }
      if (!modelName) {
        alert('Please enter a model name.');
        return;
      }

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            translation_provider: 'remote_api',
            translation_api_base_url: baseUrl,
            translation_model_name: modelName,
            translation_api_key: apiKey
          })
        });
        if (res.ok) {
          alert('Remote API Configuration saved successfully!');
        } else {
          alert('Failed to save API Configuration.');
        }
      } catch (err) {
        alert('Error saving API config: ' + err.message);
      }
    });
  }

  if (toggleQwen25Enabled) {
    toggleQwen25Enabled.addEventListener('change', async (e) => {
      const isEnabled = e.target.checked;
      updateQwenUiState(isEnabled);
      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ qwen25_enabled: isEnabled })
        });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
      } catch (err) {
        alert('Error saving Qwen2.5 model setting: ' + err.message);
        // Rollback state
        updateQwenUiState(!isEnabled);
      }
    });
  }

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

  if (toggleOsdAlwaysOn) {
    toggleOsdAlwaysOn.addEventListener('change', (e) => {
      if (osdDurationGroup) {
        osdDurationGroup.style.opacity = e.target.checked ? "0.4" : "1.0";
      }
    });
  }

  if (btnSaveOsd) {
    btnSaveOsd.addEventListener('click', async () => {
      try {
        const payload = {
          osd_position: selectOsdPosition ? selectOsdPosition.value : 'top-left',
          osd_duration: inputOsdDuration ? parseFloat(inputOsdDuration.value) || 2.0 : 2.0,
          osd_always_on: toggleOsdAlwaysOn ? toggleOsdAlwaysOn.checked : false
        };
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          alert('OSD Overlay settings saved successfully!');
        } else {
          alert('Failed to save OSD settings.');
        }
      } catch (err) {
        alert('Error saving OSD settings: ' + err.message);
      }
    });
  }

  // UX Settings Event Handlers
  if (toggleVadEnabled) {
    toggleVadEnabled.addEventListener('change', (e) => {
      if (vadTimeoutGroup) {
        vadTimeoutGroup.style.opacity = e.target.checked ? "1.0" : "0.4";
      }
    });
  }

  if (toggleStreamingTranscription) {
    toggleStreamingTranscription.addEventListener('change', (e) => {
      if (webStreamingPlayground) {
        webStreamingPlayground.style.display = e.target.checked ? "block" : "none";
      }
    });
  }

  // Web Live Dictation (Microphone streaming over WebSocket)
  let webStreamingSocket = null;
  let webAudioContext = null;
  let webAudioStream = null;
  let webAudioProcessor = null;
  let isWebStreaming = false;

  function stopWebStreaming() {
    isWebStreaming = false;
    if (webStreamingBtnLabel) webStreamingBtnLabel.textContent = "Start Speaking";
    if (btnToggleWebStreaming) {
      btnToggleWebStreaming.classList.remove('btn-primary');
      btnToggleWebStreaming.classList.add('btn-secondary');
    }
    if (webStreamingProcessor) {
      try { webStreamingProcessor.disconnect(); } catch (e) {}
      webStreamingProcessor = null;
    }
    if (webAudioStream) {
      webAudioStream.getTracks().forEach(t => t.stop());
      webAudioStream = null;
    }
    if (webAudioContext) {
      try { webAudioContext.close(); } catch (e) {}
      webAudioContext = null;
    }
    if (webStreamingSocket && webStreamingSocket.readyState === WebSocket.OPEN) {
      webStreamingSocket.send(JSON.stringify({ event: "finish" }));
      setTimeout(() => {
        try { webStreamingSocket.close(); } catch (e) {}
        webStreamingSocket = null;
      }, 500);
    }
  }

  async function startWebStreaming() {
    try {
      webStreamingLiveBox.innerHTML = '<span style="color: #38bdf8;">Connecting & listening... Speak into microphone...</span>';
      
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${wsProtocol}//${window.location.host}/api/ws/streaming-transcribe`;
      webStreamingSocket = new WebSocket(wsUrl);
      webStreamingSocket.binaryType = "arraybuffer";

      webStreamingSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === "partial_text") {
            webStreamingLiveBox.innerHTML = `<span style="color: #38bdf8; font-weight: 500;">${escapeHtml(data.text)}</span> <span class="streaming-cursor">|</span>`;
            webStreamingLiveBox.scrollTop = webStreamingLiveBox.scrollHeight;
          } else if (data.event === "final_text") {
            webStreamingLiveBox.innerHTML = `<span style="color: #34d399; font-weight: 600;">${escapeHtml(data.text || "(No speech detected)")}</span>`;
            webStreamingLiveBox.scrollTop = webStreamingLiveBox.scrollHeight;
          }
        } catch (e) {
          console.error("WS Parse error:", e);
        }
      };

      webStreamingSocket.onerror = (e) => {
        console.error("WS Error:", e);
        webStreamingLiveBox.innerHTML = '<span style="color: var(--rose);">WebSocket streaming error. Check console.</span>';
        stopWebStreaming();
      };

      webStreamingSocket.onopen = async () => {
        try {
          webAudioStream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          webAudioContext = new AudioContext({ sampleRate: 16000 });
          const source = webAudioContext.createMediaStreamSource(webAudioStream);

          // ScriptProcessorNode buffers chunks of PCM audio (4096 frames ~ 0.25s at 16kHz)
          webStreamingProcessor = webAudioContext.createScriptProcessor(4096, 1, 1);
          webStreamingProcessor.onaudioprocess = (e) => {
            if (!isWebStreaming || !webStreamingSocket || webStreamingSocket.readyState !== WebSocket.OPEN) return;
            const inputData = e.inputBuffer.getChannelData(0);
            // Send float32 buffer directly over WebSocket
            webStreamingSocket.send(inputData.buffer);
          };

          source.connect(webStreamingProcessor);
          webStreamingProcessor.connect(webAudioContext.destination);

          isWebStreaming = true;
          if (webStreamingBtnLabel) webStreamingBtnLabel.textContent = "Stop Dictation";
          if (btnToggleWebStreaming) {
            btnToggleWebStreaming.classList.remove('btn-secondary');
            btnToggleWebStreaming.classList.add('btn-primary');
          }
        } catch (micErr) {
          console.error("Microphone access error:", micErr);
          alert("Microphone access error: " + micErr.message);
          stopWebStreaming();
        }
      };
    } catch (err) {
      alert("Error starting live dictation: " + err.message);
      stopWebStreaming();
    }
  }

  if (btnToggleWebStreaming) {
    btnToggleWebStreaming.addEventListener('click', () => {
      if (isWebStreaming) {
        stopWebStreaming();
      } else {
        startWebStreaming();
      }
    });
  }

  if (btnSaveUxSettings) {
    btnSaveUxSettings.addEventListener('click', async () => {
      try {
        const payload = {
          sound_cues_enabled: toggleSoundCues ? toggleSoundCues.checked : true,
          hotkey_mode: selectHotkeyMode ? selectHotkeyMode.value : 'toggle',
          vad_enabled: toggleVadEnabled ? toggleVadEnabled.checked : false,
          vad_silence_timeout: inputVadTimeout ? parseFloat(inputVadTimeout.value) || 2.0 : 2.0,
          streaming_transcription_enabled: toggleStreamingTranscription ? toggleStreamingTranscription.checked : false
        };
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          alert('Audio Feedback & Typing Modes saved successfully!');
        } else {
          alert('Failed to save Typing Modes.');
        }
      } catch (err) {
        alert('Error saving settings: ' + err.message);
      }
    });
  }

  btnRefresh.addEventListener('click', loadHistory);

  // ==========================================
  // Custom Vocabulary & Keyword Mapping Logic
  // ==========================================
  const vocabTableBody = document.getElementById('vocab-table-body');
  const vocabTotalBadge = document.getElementById('vocab-total-badge');
  const btnAddVocab = document.getElementById('btn-add-vocab');
  const vocabModal = document.getElementById('vocab-modal');
  const vocabModalTitle = document.getElementById('vocab-modal-title');
  const btnCloseVocabModal = document.getElementById('btn-close-vocab-modal');
  const btnCancelVocabModal = document.getElementById('btn-cancel-vocab-modal');
  const btnSubmitVocabModal = document.getElementById('btn-submit-vocab-modal');
  const vocabInputTarget = document.getElementById('vocab-input-target');
  const vocabInputAliases = document.getElementById('vocab-input-aliases');
  const vocabInputDesc = document.getElementById('vocab-input-desc');

  const btnExportVocab = document.getElementById('btn-export-vocab');
  const btnImportVocabTrigger = document.getElementById('btn-import-vocab-trigger');
  const inputImportVocabFile = document.getElementById('input-import-vocab-file');

  const inputVocabSearch = document.getElementById('input-vocab-search');
  const btnVocabSearchClear = document.getElementById('btn-vocab-search-clear');

  const vocabBadgeCloud = document.getElementById('vocab-badge-cloud');
  const vocabDetailCard = document.getElementById('vocab-detail-card');
  const vocabDetailTargetText = document.getElementById('vocab-detail-target-text');
  const vocabDetailAliasCount = document.getElementById('vocab-detail-alias-count');
  const vocabDetailAliasesList = document.getElementById('vocab-detail-aliases-list');
  const vocabDetailDescText = document.getElementById('vocab-detail-desc-text');
  const vocabDetailDescGroup = document.getElementById('vocab-detail-desc-group');
  const btnVocabDetailEdit = document.getElementById('btn-vocab-detail-edit');
  const btnVocabDetailDelete = document.getElementById('btn-vocab-detail-delete');
  const btnVocabDetailClose = document.getElementById('btn-vocab-detail-close');

  let editingTargetOriginal = null;
  let cachedVocabItems = [];
  let vocabSearchQuery = '';
  let vocabCurrentPage = 1;
  const vocabPageSize = 50; // 50 items per page as requested
  let activeSelectedTarget = null;

  function getFilteredVocabItems() {
    if (!vocabSearchQuery) return cachedVocabItems;
    const q = vocabSearchQuery.toLowerCase();
    return cachedVocabItems.filter(item => {
      const matchTarget = item.target.toLowerCase().includes(q);
      const matchDesc = (item.description || '').toLowerCase().includes(q);
      const matchAlias = (item.aliases || []).some(a => a.toLowerCase().includes(q));
      return matchTarget || matchDesc || matchAlias;
    });
  }

  const vocabPaginationBar = document.getElementById('vocab-pagination-bar');
  const vocabPaginationInfo = document.getElementById('vocab-pagination-info');
  const btnVocabPrevPage = document.getElementById('btn-vocab-prev-page');
  const btnVocabNextPage = document.getElementById('btn-vocab-next-page');
  const vocabPaginationNumbers = document.getElementById('vocab-pagination-numbers');

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function loadVocabulary() {
    try {
      const res = await fetch('/api/vocabulary');
      const data = await res.json();
      cachedVocabItems = data.items || [];
      if (vocabTotalBadge) {
        vocabTotalBadge.textContent = cachedVocabItems.length;
      }
      const tabBadgeVocab = document.getElementById('tab-badge-vocab');
      if (tabBadgeVocab) {
        tabBadgeVocab.textContent = cachedVocabItems.length;
      }
      renderVocabulary();
    } catch (err) {
      console.error('Failed to load vocabulary:', err);
      if (vocabBadgeCloud) {
        vocabBadgeCloud.innerHTML = `
          <div class="vocab-cloud-empty" style="color: var(--rose);">
            Failed to load vocabulary: ${escapeHtml(err.message)}
          </div>
        `;
      }
    }
  }

  function updateVocabPagination() {
    const filtered = getFilteredVocabItems();
    const totalCount = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / vocabPageSize));

    if (vocabCurrentPage > totalPages) vocabCurrentPage = totalPages;
    if (vocabCurrentPage < 1) vocabCurrentPage = 1;

    if (vocabPaginationBar) {
      vocabPaginationBar.style.display = totalCount > 0 ? 'flex' : 'none';
    }

    if (vocabPaginationInfo) {
      const start = totalCount === 0 ? 0 : (vocabCurrentPage - 1) * vocabPageSize + 1;
      const end = Math.min(vocabCurrentPage * vocabPageSize, totalCount);
      const querySuffix = vocabSearchQuery ? ` (filtered from ${cachedVocabItems.length})` : '';
      vocabPaginationInfo.textContent = `Showing ${start}-${end} of ${totalCount} words${querySuffix} (Page ${vocabCurrentPage}/${totalPages})`;
    }

    if (btnVocabPrevPage) btnVocabPrevPage.disabled = (vocabCurrentPage <= 1);
    if (btnVocabNextPage) btnVocabNextPage.disabled = (vocabCurrentPage >= totalPages);

    if (vocabPaginationNumbers) {
      vocabPaginationNumbers.innerHTML = '';
      const maxButtons = 5;
      let startPage = Math.max(1, vocabCurrentPage - Math.floor(maxButtons / 2));
      let endPage = Math.min(totalPages, startPage + maxButtons - 1);
      if (endPage - startPage + 1 < maxButtons) {
        startPage = Math.max(1, endPage - maxButtons + 1);
      }

      for (let p = startPage; p <= endPage; p++) {
        const btn = document.createElement('button');
        btn.className = `page-num-btn ${p === vocabCurrentPage ? 'active' : ''}`;
        btn.textContent = p;
        btn.onclick = () => {
          if (vocabCurrentPage !== p) {
            vocabCurrentPage = p;
            renderVocabulary();
          }
        };
        vocabPaginationNumbers.appendChild(btn);
      }
    }
  }

  if (btnVocabPrevPage) {
    btnVocabPrevPage.addEventListener('click', () => {
      if (vocabCurrentPage > 1) {
        vocabCurrentPage--;
        renderVocabulary();
      }
    });
  }

  if (btnVocabNextPage) {
    btnVocabNextPage.addEventListener('click', () => {
      const filtered = getFilteredVocabItems();
      const totalPages = Math.ceil(filtered.length / vocabPageSize);
      if (vocabCurrentPage < totalPages) {
        vocabCurrentPage++;
        renderVocabulary();
      }
    });
  }

  function showVocabDetail(item) {
    if (!vocabDetailCard || !item) return;
    activeSelectedTarget = item.target;
    
    // Highlight active badge in cloud
    const allBadges = document.querySelectorAll('.vocab-word-badge');
    allBadges.forEach(b => {
      if (b.getAttribute('data-target') === item.target) {
        b.classList.add('selected');
      } else {
        b.classList.remove('selected');
      }
    });

    vocabDetailTargetText.textContent = item.target;
    const aliases = item.aliases || [];
    vocabDetailAliasCount.textContent = `${aliases.length} ${aliases.length === 1 ? 'alias' : 'aliases'}`;
    
    if (aliases.length > 0) {
      vocabDetailAliasesList.innerHTML = aliases.map(a => 
        `<span class="vocab-detail-alias-badge">${escapeHtml(a)}</span>`
      ).join('');
    } else {
      vocabDetailAliasesList.innerHTML = `<span style="font-size: 0.775rem; color: var(--text-muted);">(No spoken aliases configured yet)</span>`;
    }

    if (item.description && item.description.trim()) {
      vocabDetailDescText.textContent = item.description.trim();
      vocabDetailDescGroup.style.display = 'block';
    } else {
      vocabDetailDescGroup.style.display = 'none';
    }

    vocabDetailCard.style.display = 'block';
  }

  function hideVocabDetail() {
    if (!vocabDetailCard) return;
    vocabDetailCard.style.display = 'none';
    activeSelectedTarget = null;
    const allBadges = document.querySelectorAll('.vocab-word-badge');
    allBadges.forEach(b => b.classList.remove('selected'));
  }

  if (btnVocabDetailClose) {
    btnVocabDetailClose.addEventListener('click', hideVocabDetail);
  }

  if (btnVocabDetailEdit) {
    btnVocabDetailEdit.addEventListener('click', () => {
      if (!activeSelectedTarget) return;
      const item = cachedVocabItems.find(i => i.target.toLowerCase() === activeSelectedTarget.toLowerCase());
      if (item) {
        openVocabModal(item);
      }
    });
  }

  if (btnVocabDetailDelete) {
    btnVocabDetailDelete.addEventListener('click', () => {
      if (!activeSelectedTarget) return;
      window.deleteVocabItem(encodeURIComponent(activeSelectedTarget));
    });
  }

  // Quick Search Event Listeners
  if (inputVocabSearch) {
    inputVocabSearch.addEventListener('input', (e) => {
      vocabSearchQuery = (e.target.value || '').trim();
      if (btnVocabSearchClear) {
        btnVocabSearchClear.style.display = vocabSearchQuery ? 'inline-flex' : 'none';
      }
      vocabCurrentPage = 1;
      renderVocabulary();
    });
  }

  if (btnVocabSearchClear) {
    btnVocabSearchClear.addEventListener('click', () => {
      if (inputVocabSearch) {
        inputVocabSearch.value = '';
        inputVocabSearch.focus();
      }
      vocabSearchQuery = '';
      btnVocabSearchClear.style.display = 'none';
      vocabCurrentPage = 1;
      renderVocabulary();
    });
  }

  // Modern Vocabulary Table & Quick Inline Form UI Elements
  const vocabInlineFormPanel = document.getElementById('vocab-inline-form-panel');
  const vocabInlineForm = document.getElementById('vocab-inline-form');
  const vocabInlineTitle = document.getElementById('vocab-inline-title');
  const btnToggleQuickAdd = document.getElementById('btn-toggle-quick-add');
  const btnCloseInlineForm = document.getElementById('btn-close-inline-form');
  const btnCancelInlineForm = document.getElementById('btn-cancel-inline-form');
  const btnSubmitVocabInline = document.getElementById('btn-submit-vocab-inline');

  // Alias Chips UI Elements & State
  const aliasChipsContainer = document.getElementById('alias-chips-container');
  const aliasChipsList = document.getElementById('alias-chips-list');
  const inputAliasChip = document.getElementById('input-alias-chip');
  let currentInlineAliases = [];

  function renderInlineAliasChips() {
    if (!aliasChipsList) return;
    aliasChipsList.innerHTML = currentInlineAliases.map((alias, idx) => `
      <span class="alias-chip-item">
        <span>${escapeHtml(alias)}</span>
        <button type="button" class="alias-chip-del" data-idx="${idx}" title="Remove alias">&times;</button>
      </span>
    `).join('');

    // Attach delete listeners
    aliasChipsList.querySelectorAll('.alias-chip-del').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.getAttribute('data-idx'), 10);
        if (!isNaN(idx)) {
          currentInlineAliases.splice(idx, 1);
          renderInlineAliasChips();
        }
      });
    });
  }

  function addAliasChipFromInput() {
    if (!inputAliasChip) return;
    const raw = inputAliasChip.value.trim();
    if (!raw) return;

    // Support comma or semicolon if pasted
    const parts = raw.split(/[,;]+/).map(p => p.trim()).filter(Boolean);
    parts.forEach(part => {
      if (!currentInlineAliases.some(a => a.toLowerCase() === part.toLowerCase())) {
        currentInlineAliases.push(part);
      }
    });

    inputAliasChip.value = '';
    renderInlineAliasChips();
  }

  if (aliasChipsContainer && inputAliasChip) {
    aliasChipsContainer.addEventListener('click', () => {
      inputAliasChip.focus();
    });

    inputAliasChip.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        addAliasChipFromInput();
      } else if (e.key === 'Backspace' && !inputAliasChip.value && currentInlineAliases.length > 0) {
        currentInlineAliases.pop();
        renderInlineAliasChips();
      }
    });

    inputAliasChip.addEventListener('blur', () => {
      addAliasChipFromInput();
    });
  }

  function openInlineVocabForm(item = null) {
    if (!vocabInlineFormPanel) return;
    if (item) {
      editingTargetOriginal = item.target;
      if (vocabInlineTitle) vocabInlineTitle.textContent = `Edit Target Word: "${item.target}"`;
      vocabInputTarget.value = item.target || '';
      currentInlineAliases = Array.isArray(item.aliases) ? [...item.aliases] : [];
      vocabInputDesc.value = item.description || '';
      if (btnSubmitVocabInline) btnSubmitVocabInline.textContent = 'Update Word';
    } else {
      editingTargetOriginal = null;
      if (vocabInlineTitle) vocabInlineTitle.textContent = 'Add Custom Word / Term';
      vocabInputTarget.value = '';
      currentInlineAliases = [];
      vocabInputDesc.value = '';
      if (btnSubmitVocabInline) btnSubmitVocabInline.textContent = 'Save Word';
    }
    renderInlineAliasChips();
    if (inputAliasChip) inputAliasChip.value = '';
    vocabInlineFormPanel.style.display = 'block';
    vocabInputTarget.focus();
  }

  function closeInlineVocabForm() {
    if (!vocabInlineFormPanel) return;
    vocabInlineFormPanel.style.display = 'none';
    editingTargetOriginal = null;
    currentInlineAliases = [];
    if (inputAliasChip) inputAliasChip.value = '';
  }

  if (btnToggleQuickAdd) {
    btnToggleQuickAdd.addEventListener('click', () => {
      if (vocabInlineFormPanel && vocabInlineFormPanel.style.display === 'block' && !editingTargetOriginal) {
        closeInlineVocabForm();
      } else {
        openInlineVocabForm(null);
      }
    });
  }

  if (btnCloseInlineForm) {
    btnCloseInlineForm.addEventListener('click', closeInlineVocabForm);
  }

  if (btnCancelInlineForm) {
    btnCancelInlineForm.addEventListener('click', closeInlineVocabForm);
  }

  // Handle Quick Inline Form Submit
  if (vocabInlineForm) {
    vocabInlineForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const target = vocabInputTarget.value.trim();
      if (!target) {
        vocabInputTarget.focus();
        return;
      }

      // Commit any pending text in inputAliasChip
      addAliasChipFromInput();
      const aliases = [...currentInlineAliases];
      const desc = vocabInputDesc.value.trim();

      try {
        if (editingTargetOriginal && editingTargetOriginal.toLowerCase() !== target.toLowerCase()) {
          await fetch(`/api/vocabulary/${encodeURIComponent(editingTargetOriginal)}`, {
            method: 'DELETE'
          });
        }

        const res = await fetch('/api/vocabulary', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: target,
            aliases: aliases,
            description: desc
          })
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Failed to save vocabulary word.');
        }

        closeInlineVocabForm();
        await loadVocabulary();
      } catch (err) {
        alert('Error saving word: ' + err.message);
      }
    });
  }

  function renderVocabulary() {
    updateVocabPagination();
    const filtered = getFilteredVocabItems();

    if (!vocabTableBody) return;

    if (cachedVocabItems.length === 0) {
      vocabTableBody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
            No custom vocabulary yet. Click <strong>"+ New Word"</strong> to define keywords and aliases for speech correction.
          </td>
        </tr>
      `;
      return;
    }

    if (filtered.length === 0) {
      vocabTableBody.innerHTML = `
        <tr>
          <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
            No keywords match "<strong>${escapeHtml(vocabSearchQuery)}</strong>".
          </td>
        </tr>
      `;
      return;
    }

    // Slice 50 items for the current page
    const startIdx = (vocabCurrentPage - 1) * vocabPageSize;
    const pageItems = filtered.slice(startIdx, startIdx + vocabPageSize);

    vocabTableBody.innerHTML = pageItems.map(item => {
      const targetSafe = escapeHtml(item.target);
      const aliases = item.aliases || [];
      const descSafe = escapeHtml(item.description || '-');
      const aliasChips = aliases.length > 0 
        ? aliases.map(a => `<span class="vocab-alias-chip">${escapeHtml(a)}</span>`).join('')
        : `<span style="color: var(--text-muted); font-size: 0.75rem; font-style: italic;">No aliases</span>`;

      return `
        <tr id="vocab-row-${encodeURIComponent(item.target)}">
          <td class="vocab-target-cell">
            ${targetSafe}
          </td>
          <td>
            <div class="vocab-alias-chips">
              ${aliasChips}
            </div>
          </td>
          <td class="vocab-desc-cell">
            ${descSafe}
          </td>
          <td class="vocab-action-cell">
            <button class="btn-icon-action" onclick="window.editVocabItem('${encodeURIComponent(item.target)}')" title="Edit Word">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button class="btn-icon-action btn-del" onclick="window.deleteVocabItem('${encodeURIComponent(item.target)}')" title="Delete Word">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Global window functions for edit & delete buttons
  window.editVocabItem = (encodedTarget) => {
    const targetName = decodeURIComponent(encodedTarget);
    const item = cachedVocabItems.find(i => i.target.toLowerCase() === targetName.toLowerCase());
    if (item) {
      openInlineVocabForm(item);
    }
  };

  window.deleteVocabItem = async (encodedTarget) => {
    const targetName = decodeURIComponent(encodedTarget);
    if (!confirm(`Are you sure you want to remove '${targetName}' from custom vocabulary?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/vocabulary/${encodeURIComponent(targetName)}`, {
        method: 'DELETE'
      });
      if (!res.ok) {
        throw new Error('Failed to delete word.');
      }
      if (editingTargetOriginal && editingTargetOriginal.toLowerCase() === targetName.toLowerCase()) {
        closeInlineVocabForm();
      }
      await loadVocabulary();
    } catch (err) {
      alert('Error deleting word: ' + err.message);
    }
  };

  // Export & Import vocabulary.json
  if (btnExportVocab) {
    btnExportVocab.addEventListener('click', () => {
      const activeProf = selectActiveProfile ? selectActiveProfile.value : 'default';
      window.location.href = `/api/vocabulary/export?profile_id=${encodeURIComponent(activeProf)}`;
    });
  }

  if (btnImportVocabTrigger && inputImportVocabFile) {
    btnImportVocabTrigger.addEventListener('click', () => {
      inputImportVocabFile.click();
    });

    inputImportVocabFile.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch('/api/vocabulary/import', {
          method: 'POST',
          body: formData
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Import failed.');
        }
        const data = await res.json();
        alert(`Successfully imported ${data.count} vocabulary items!`);
        await loadVocabulary();
      } catch (err) {
        alert('Error importing file: ' + err.message);
      } finally {
        inputImportVocabFile.value = '';
      }
    });
  }

  // ==========================================
  // Profile Management Logic
  // ==========================================
  const selectActiveProfile = document.getElementById('select-active-profile');
  const btnOpenProfileModal = document.getElementById('btn-open-profile-modal');
  const profileModal = document.getElementById('profile-modal');
  const btnCloseProfileModal = document.getElementById('btn-close-profile-modal');
  const btnDoneProfileModal = document.getElementById('btn-done-profile-modal');
  const profileListContainer = document.getElementById('profile-list-container');
  const inputNewProfileId = document.getElementById('input-new-profile-id');
  const inputNewProfileName = document.getElementById('input-new-profile-name');
  const inputNewProfileDesc = document.getElementById('input-new-profile-desc');
  const btnCreateProfile = document.getElementById('btn-create-profile');

  let activeProfileId = 'default';
  let cachedProfiles = [];

  async function loadProfiles() {
    try {
      const res = await fetch('/api/profiles');
      const data = await res.json();
      cachedProfiles = data.profiles || [];
      const active = data.active_profile || {};
      activeProfileId = active.id || 'default';

      // Render Dropdown in Header
      if (selectActiveProfile) {
        selectActiveProfile.innerHTML = cachedProfiles.map(p => `
          <option value="${escapeHtml(p.id)}" ${p.id === activeProfileId ? 'selected' : ''}>
            ${escapeHtml(p.name || p.id)}
          </option>
        `).join('');
      }

      renderProfileList();
    } catch (err) {
      console.error('Failed to load profiles:', err);
    }
  }

  function renderProfileList() {
    if (!profileListContainer) return;
    profileListContainer.innerHTML = cachedProfiles.map(p => {
      const isCur = (p.id === activeProfileId);
      const isDefault = (p.id === 'default');
      return `
        <div class="profile-item-row ${isCur ? 'active' : ''}">
          <div class="profile-info">
            <div class="profile-name">
              <span>${escapeHtml(p.name || p.id)}</span>
              <code style="font-size: 0.7rem; color: #a5b4fc;">(${escapeHtml(p.id)})</code>
              ${isCur ? '<span class="badge-active-pill">Active</span>' : ''}
            </div>
            <div class="profile-desc">${escapeHtml(p.description || (isDefault ? 'Standard default profile' : 'No description'))}</div>
          </div>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <button class="btn btn-secondary btn-xs" title="Export complete bundle (Vocab + LoRA zip)" onclick="window.exportProfileBundle('${escapeHtml(p.id)}')">
              Export
            </button>
            <button class="btn btn-secondary btn-xs" title="Edit profile name and description" onclick="window.openEditProfileModal('${escapeHtml(p.id)}')">
              Edit
            </button>
            ${!isCur ? `
              <button class="btn btn-secondary btn-xs" onclick="window.switchProfile('${escapeHtml(p.id)}')">
                Select
              </button>
            ` : ''}
            ${!isDefault ? `
              <button class="btn btn-secondary btn-xs btn-delete" onclick="window.deleteProfile('${escapeHtml(p.id)}')">
                Delete
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  async function switchProfile(profileId) {
    if (!profileId) return;
    try {
      const res = await fetch('/api/profiles/active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_id: profileId })
      });
      if (!res.ok) {
        throw new Error('Failed to switch profile');
      }
      activeProfileId = profileId;
      await loadProfiles();
      // Reload history, vocabulary, and training status for newly selected profile
      currentPage = 1;
      await loadHistory();
      await loadVocabulary();
      await checkTrainStatus();
      await checkStatus();
    } catch (err) {
      alert('Error switching profile: ' + err.message);
    }
  }
  window.switchProfile = switchProfile;

  // Export Profile Modal Elements & Logic
  const exportProfileModal = document.getElementById('export-profile-modal');
  const btnCloseExportModal = document.getElementById('btn-close-export-modal');
  const btnCancelExportModal = document.getElementById('btn-cancel-export-modal');
  const btnDoExportBundle = document.getElementById('btn-do-export-bundle');
  const exportTargetProfileId = document.getElementById('export-target-profile-id');
  const exportModalProfileName = document.getElementById('export-modal-profile-name');
  const exportModalProfileId = document.getElementById('export-modal-profile-id');
  const chkExportVocab = document.getElementById('chk-export-vocab');
  const chkExportLora = document.getElementById('chk-export-lora');
  const chkExportTraining = document.getElementById('chk-export-training');

  function closeExportModal() {
    if (exportProfileModal) exportProfileModal.classList.remove('open');
  }

  if (btnCloseExportModal) btnCloseExportModal.addEventListener('click', closeExportModal);
  if (btnCancelExportModal) btnCancelExportModal.addEventListener('click', closeExportModal);
  if (exportProfileModal) {
    exportProfileModal.addEventListener('click', (e) => {
      if (e.target === exportProfileModal) closeExportModal();
    });
  }

  window.exportProfileBundle = (profileId) => {
    const profile = cachedProfiles.find(p => p.id === profileId) || { id: profileId, name: profileId };
    if (exportTargetProfileId) exportTargetProfileId.value = profile.id;
    if (exportModalProfileName) exportModalProfileName.textContent = profile.name || profile.id;
    if (exportModalProfileId) exportModalProfileId.textContent = profile.id;

    // Reset defaults: both vocab and LoRA checked, training un-checked
    if (chkExportVocab) chkExportVocab.checked = true;
    if (chkExportLora) chkExportLora.checked = true;
    if (chkExportTraining) chkExportTraining.checked = false;

    if (exportProfileModal) exportProfileModal.classList.add('open');
  };

  if (btnDoExportBundle) {
    btnDoExportBundle.addEventListener('click', () => {
      const pid = exportTargetProfileId ? exportTargetProfileId.value : 'default';
      const incVocab = chkExportVocab ? chkExportVocab.checked : true;
      const incLora = chkExportLora ? chkExportLora.checked : true;
      const incTrain = chkExportTraining ? chkExportTraining.checked : false;

      if (!incVocab && !incLora && !incTrain) {
        alert('Please select at least one component (Vocabulary, LoRA, or Training Data) to export.');
        return;
      }

      const params = new URLSearchParams({
        profile_id: pid,
        include_vocab: incVocab ? 'true' : 'false',
        include_lora: incLora ? 'true' : 'false',
        include_training_data: incTrain ? 'true' : 'false'
      });

      closeExportModal();
      window.location.href = `/api/profiles/export-bundle?${params.toString()}`;
    });
  }

  // Import Profile Modal Elements & Logic
  const importProfileModal = document.getElementById('import-profile-modal');
  const btnOpenImportProfile = document.getElementById('btn-open-import-profile');
  const btnCloseImportModal = document.getElementById('btn-close-import-modal');
  const btnCancelImportModal = document.getElementById('btn-cancel-import-modal');
  const btnSubmitImportBundle = document.getElementById('btn-submit-import-bundle');
  const inputImportFile = document.getElementById('input-import-file');
  const importInspectPreview = document.getElementById('import-inspect-preview');
  const importPreviewName = document.getElementById('import-preview-name');
  const importPreviewBadges = document.getElementById('import-preview-badges');
  const importPreviewDesc = document.getElementById('import-preview-desc');
  const importFieldsContainer = document.getElementById('import-fields-container');
  const inputImportProfileId = document.getElementById('input-import-profile-id');
  const inputImportProfileName = document.getElementById('input-import-profile-name');
  const inputImportProfileDesc = document.getElementById('input-import-profile-desc');
  const chkImportOverwrite = document.getElementById('chk-import-overwrite');
  const chkImportSetActive = document.getElementById('chk-import-set-active');

  let inspectedBundleFile = null;

  function closeImportModal() {
    if (importProfileModal) importProfileModal.classList.remove('open');
    if (inputImportFile) inputImportFile.value = '';
    if (importInspectPreview) importInspectPreview.style.display = 'none';
    if (importFieldsContainer) importFieldsContainer.style.display = 'none';
    if (btnSubmitImportBundle) btnSubmitImportBundle.disabled = true;
    inspectedBundleFile = null;
  }

  if (btnOpenImportProfile) {
    btnOpenImportProfile.addEventListener('click', () => {
      closeProfileModal();
      if (importProfileModal) importProfileModal.classList.add('open');
    });
  }

  if (btnCloseImportModal) btnCloseImportModal.addEventListener('click', closeImportModal);
  if (btnCancelImportModal) btnCancelImportModal.addEventListener('click', closeImportModal);
  if (importProfileModal) {
    importProfileModal.addEventListener('click', (e) => {
      if (e.target === importProfileModal) closeImportModal();
    });
  }

  // Inspect zip file on file selection
  if (inputImportFile) {
    inputImportFile.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      inspectedBundleFile = file;
      const formData = new FormData();
      formData.append('file', file);

      try {
        if (btnSubmitImportBundle) {
          btnSubmitImportBundle.disabled = true;
          btnSubmitImportBundle.textContent = 'Inspecting Archive...';
        }

        const res = await fetch('/api/profiles/inspect-bundle', {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to inspect bundle.');
        }

        const info = await res.json();

        // Populate preview
        if (importPreviewName) {
          importPreviewName.textContent = info.profile_name || info.profile_id;
        }

        let badgesHtml = `
          <span style="font-size: 0.725rem; font-weight: 600; padding: 0.2rem 0.45rem; border-radius: 4px; background: #e0f2fe; color: #0369a1;">
            ID: ${escapeHtml(info.profile_id)}
          </span>
        `;
        if (info.has_vocabulary) {
          badgesHtml += `
            <span style="font-size: 0.725rem; font-weight: 600; padding: 0.2rem 0.45rem; border-radius: 4px; background: #dcfce7; color: #15803d;">
              ✓ Vocab: ${info.vocabulary_count || 'Included'}
            </span>
          `;
        }
        if (info.has_lora) {
          badgesHtml += `
            <span style="font-size: 0.725rem; font-weight: 600; padding: 0.2rem 0.45rem; border-radius: 4px; background: #f3e8ff; color: #7e22ce;">
              ✓ LoRA Weights
            </span>
          `;
        }
        if (info.has_training_samples) {
          badgesHtml += `
            <span style="font-size: 0.725rem; font-weight: 600; padding: 0.2rem 0.45rem; border-radius: 4px; background: #ffedd5; color: #c2410c;">
              ✓ Samples: ${info.training_sample_count}
            </span>
          `;
        }
        if (info.is_conflict) {
          badgesHtml += `
            <span style="font-size: 0.725rem; font-weight: 600; padding: 0.2rem 0.45rem; border-radius: 4px; background: #fee2e2; color: #b91c1c;">
              ⚠ ID Already Exists
            </span>
          `;
        }

        if (importPreviewBadges) importPreviewBadges.innerHTML = badgesHtml;
        if (importPreviewDesc) {
          importPreviewDesc.textContent = info.profile_description || (info.is_conflict ? 'Note: This ID is already registered. Check overwrite or specify a new ID.' : 'Ready to import.');
        }

        // Fill form fields
        if (inputImportProfileId) inputImportProfileId.value = info.profile_id;
        if (inputImportProfileName) inputImportProfileName.value = info.profile_name || info.profile_id;
        if (inputImportProfileDesc) inputImportProfileDesc.value = info.profile_description || '';
        if (chkImportOverwrite) chkImportOverwrite.checked = info.is_conflict;

        if (importInspectPreview) importInspectPreview.style.display = 'block';
        if (importFieldsContainer) importFieldsContainer.style.display = 'block';
        if (btnSubmitImportBundle) {
          btnSubmitImportBundle.disabled = false;
          btnSubmitImportBundle.textContent = 'Import & Apply';
        }
      } catch (err) {
        alert('Error inspecting archive: ' + err.message);
        if (btnSubmitImportBundle) {
          btnSubmitImportBundle.disabled = true;
          btnSubmitImportBundle.textContent = 'Import & Apply';
        }
      }
    });
  }

  // Handle Import Submit
  if (btnSubmitImportBundle) {
    btnSubmitImportBundle.addEventListener('click', async () => {
      if (!inspectedBundleFile) {
        alert('Please choose a valid .zip file first.');
        return;
      }

      const targetId = inputImportProfileId ? inputImportProfileId.value.trim().toLowerCase() : '';
      const targetName = inputImportProfileName ? inputImportProfileName.value.trim() : '';
      const targetDesc = inputImportProfileDesc ? inputImportProfileDesc.value.trim() : '';
      const overwrite = chkImportOverwrite ? chkImportOverwrite.checked : false;
      const setActive = chkImportSetActive ? chkImportSetActive.checked : true;

      if (!targetId) {
        alert('Target Profile ID cannot be empty.');
        inputImportProfileId.focus();
        return;
      }

      const formData = new FormData();
      formData.append('file', inspectedBundleFile);
      formData.append('target_profile_id', targetId);
      formData.append('target_profile_name', targetName || targetId);
      formData.append('target_profile_desc', targetDesc);
      formData.append('overwrite', overwrite ? 'true' : 'false');
      formData.append('set_active', setActive ? 'true' : 'false');

      try {
        btnSubmitImportBundle.disabled = true;
        btnSubmitImportBundle.textContent = 'Importing...';

        const res = await fetch('/api/profiles/import-bundle', {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to import profile bundle.');
        }

        const data = await res.json();
        closeImportModal();

        alert(`Profile '${data.profile_name}' imported successfully!\n• Vocabularies: ${data.imported_vocabulary_count}\n• LoRA: ${data.imported_lora ? 'Loaded' : 'None'}\n• Samples: ${data.imported_samples_count}`);

        await loadProfiles();
        if (setActive) {
          activeProfileId = targetId;
          currentPage = 1;
          await loadHistory();
          await loadVocabulary();
          await checkTrainStatus();
        }
      } catch (err) {
        alert('Error importing profile: ' + err.message);
      } finally {
        if (btnSubmitImportBundle) {
          btnSubmitImportBundle.disabled = false;
          btnSubmitImportBundle.textContent = 'Import & Apply';
        }
      }
    });
  }

  window.deleteProfile = async (profileId) => {
    if (!confirm(`Are you sure you want to delete profile '${profileId}'?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/profiles/${encodeURIComponent(profileId)}`, {
        method: 'DELETE'
      });
      if (!res.ok) {
        throw new Error('Failed to delete profile');
      }
      await loadProfiles();
      await loadHistory();
      await loadVocabulary();
      await checkTrainStatus();
    } catch (err) {
      alert('Error deleting profile: ' + err.message);
    }
  };

  if (selectActiveProfile) {
    selectActiveProfile.addEventListener('change', (e) => {
      switchProfile(e.target.value);
    });
  }

  if (btnOpenProfileModal) {
    btnOpenProfileModal.addEventListener('click', () => {
      if (profileModal) profileModal.classList.add('open');
    });
  }

  function closeProfileModal() {
    if (profileModal) profileModal.classList.remove('open');
  }

  if (btnCloseProfileModal) btnCloseProfileModal.addEventListener('click', closeProfileModal);
  if (btnDoneProfileModal) btnDoneProfileModal.addEventListener('click', closeProfileModal);
  if (profileModal) {
    profileModal.addEventListener('click', (e) => {
      if (e.target === profileModal) closeProfileModal();
    });
  }

  // Edit Profile Modal Logic
  const editProfileModal = document.getElementById('edit-profile-modal');
  const btnCloseEditProfileModal = document.getElementById('btn-close-edit-profile-modal');
  const btnCancelEditProfileModal = document.getElementById('btn-cancel-edit-profile-modal');
  const btnSaveEditProfile = document.getElementById('btn-save-edit-profile');
  const inputEditProfileId = document.getElementById('input-edit-profile-id');
  const displayEditProfileId = document.getElementById('display-edit-profile-id');
  const inputEditProfileName = document.getElementById('input-edit-profile-name');
  const inputEditProfileDesc = document.getElementById('input-edit-profile-desc');

  function closeEditProfileModal() {
    if (editProfileModal) editProfileModal.classList.remove('open');
  }

  if (btnCloseEditProfileModal) btnCloseEditProfileModal.addEventListener('click', closeEditProfileModal);
  if (btnCancelEditProfileModal) btnCancelEditProfileModal.addEventListener('click', closeEditProfileModal);
  if (editProfileModal) {
    editProfileModal.addEventListener('click', (e) => {
      if (e.target === editProfileModal) closeEditProfileModal();
    });
  }

  window.openEditProfileModal = (profileId) => {
    const profile = cachedProfiles.find(p => p.id === profileId);
    if (!profile) return;
    if (inputEditProfileId) inputEditProfileId.value = profile.id;
    if (displayEditProfileId) displayEditProfileId.value = profile.id;
    if (inputEditProfileName) inputEditProfileName.value = profile.name || '';
    if (inputEditProfileDesc) inputEditProfileDesc.value = profile.description || '';
    if (editProfileModal) editProfileModal.classList.add('open');
    if (inputEditProfileName) inputEditProfileName.focus();
  };

  if (btnSaveEditProfile) {
    btnSaveEditProfile.addEventListener('click', async () => {
      const id = inputEditProfileId ? inputEditProfileId.value.trim() : '';
      const name = inputEditProfileName ? inputEditProfileName.value.trim() : '';
      const desc = inputEditProfileDesc ? inputEditProfileDesc.value.trim() : '';

      if (!id || !name) {
        alert('Display Name cannot be empty.');
        return;
      }

      try {
        const res = await fetch(`/api/profiles/${encodeURIComponent(id)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, description: desc })
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Failed to update profile');
        }
        closeEditProfileModal();
        await loadProfiles();
      } catch (err) {
        alert('Error updating profile: ' + err.message);
      }
    });
  }

  // About Modal Handlers
  const aboutModal = document.getElementById('about-modal');
  const btnOpenAboutModal = document.getElementById('btn-open-about-modal');
  const btnCloseAboutModal = document.getElementById('btn-close-about-modal');
  const btnDoneAboutModal = document.getElementById('btn-done-about-modal');

  function closeAboutModal() {
    if (aboutModal) aboutModal.classList.remove('open');
  }

  if (btnOpenAboutModal) {
    btnOpenAboutModal.addEventListener('click', () => {
      if (aboutModal) aboutModal.classList.add('open');
    });
  }
  if (btnCloseAboutModal) btnCloseAboutModal.addEventListener('click', closeAboutModal);
  if (btnDoneAboutModal) btnDoneAboutModal.addEventListener('click', closeAboutModal);
  if (aboutModal) {
    aboutModal.addEventListener('click', (e) => {
      if (e.target === aboutModal) closeAboutModal();
    });
  }

  if (btnCreateProfile) {
    btnCreateProfile.addEventListener('click', async () => {
      const id = inputNewProfileId.value.trim().toLowerCase();
      const name = inputNewProfileName.value.trim();
      const desc = inputNewProfileDesc.value.trim();

      if (!id || !name) {
        alert('Please provide both a Profile ID and a Display Name.');
        return;
      }

      if (!/^[a-z0-9_-]+$/.test(id)) {
        alert('Profile ID must only contain lowercase alphanumeric characters, dashes, or underscores (e.g. triet, alex_it).');
        return;
      }

      try {
        const res = await fetch('/api/profiles', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id, name, description: desc })
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Failed to create profile');
        }

        // Switch to newly created profile
        inputNewProfileId.value = '';
        inputNewProfileName.value = '';
        inputNewProfileDesc.value = '';
        await switchProfile(id);
      } catch (err) {
        alert('Error creating profile: ' + err.message);
      }
    });
  }

  // Corporate Workspace Tabs Navigation
  const tabButtons = document.querySelectorAll('.corporate-tab-bar .tab-nav-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  function activateTab(tabId) {
    if (!tabId) return;
    const targetPane = document.getElementById(tabId);
    if (!targetPane) return;

    tabPanes.forEach(pane => pane.classList.remove('active'));
    tabButtons.forEach(btn => {
      if (btn.getAttribute('data-tab') === tabId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
    targetPane.classList.add('active');
    try {
      localStorage.setItem('active_studio_tab', tabId);
    } catch (e) {}
  }

  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      activateTab(tabId);
    });
  });

  // Restore saved tab or default to Speech Records
  try {
    let savedTab = localStorage.getItem('active_studio_tab');
    if (savedTab === 'pane-training') {
      savedTab = 'pane-vocabulary';
    }
    if (savedTab && document.getElementById(savedTab)) {
      activateTab(savedTab);
    }
  } catch (e) {}

  // Initialize
  checkStatus();
  loadProfiles();
  loadSettings();
  loadHistory();
  loadVocabulary();
  checkTrainStatus();

  // Periodic status poll
  setInterval(() => {
    checkTrainStatus();
  }, 2000);
});



