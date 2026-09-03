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
      statusText.textContent = 'Mất kết nối Backend';
    }
  }

  // Load transcription history
  async function loadHistory() {
    try {
      const res = await fetch('/api/history?limit=30');
      const data = await res.json();
      const items = data.items || [];

      if (items.length === 0) {
        historyContainer.innerHTML = `
          <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
            Chưa có đoạn ghi âm nào. Hãy bấm phím tắt <code>${inputHotkey.value}</code> để nói thử một câu!
          </div>
        `;
        return;
      }

      historyContainer.innerHTML = items.map(item => `
        <div class="history-item" id="item-${item.id}">
          <div class="item-meta">
            <span>${item.timestamp} • ${item.duration.toFixed(1)}s</span>
            <span class="item-badge ${item.is_reviewed ? 'badge-reviewed' : 'badge-unreviewed'}">
              ${item.is_reviewed ? 'Đã chỉnh sửa (Sẵn sàng LoRA)' : 'Nguyên bản (Chưa soát)'}
            </span>
          </div>

          <div style="margin-bottom: 0.5rem;">
            <label style="font-size: 0.75rem; color: var(--text-muted);">Kết quả ASR nhận dạng ban đầu:</label>
            <div style="font-style: italic; color: var(--text-secondary); margin-bottom: 0.5rem;">
              "${item.raw_text}"
            </div>
          </div>

          <div>
            <label style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-bottom: 0.25rem;">
              Văn bản chuẩn xác (Click để sửa lại các từ sai):
            </label>
            <textarea class="edit-box" id="edit-text-${item.id}" rows="2">${item.corrected_text}</textarea>
          </div>

          <div class="item-actions">
            <audio controls src="/api/audio/${item.id}"></audio>
            <button class="btn btn-primary" onclick="saveCorrection(${item.id})">
              Lưu từ sửa
            </button>
          </div>
        </div>
      `).join('');
    } catch (err) {
      historyContainer.innerHTML = '<p style="color: var(--rose);">Lỗi khi tải lịch sử.</p>';
    }
  }

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
      }
    } catch (err) {
      alert('Không thể lưu từ sửa: ' + err.message);
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
        metricTrainLoss.textContent = data.current_loss > 0 ? data.current_loss : 'Đang tính...';
        const total = (data.total_epochs || 1);
        const current = data.current_epoch || 0;
        const percent = Math.min(100, Math.round((current / total) * 100));
        progressBar.style.width = `${percent}%`;
      } else {
        btnStartTraining.disabled = (data.pending_samples === 0);
        metricTrainLoss.textContent = data.current_loss > 0 ? `${data.current_loss} (Xong)` : '-';
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
        alert(err.detail || 'Không thể bắt đầu train');
        btnStartTraining.disabled = false;
      }
    } catch (err) {
      alert('Lỗi kết nối: ' + err.message);
      btnStartTraining.disabled = false;
    }
  });

  // Settings: Load and Save Hotkey
  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      const data = await res.json();
      if (data.hotkey) {
        inputHotkey.value = data.hotkey;
      }
    } catch (err) {
      console.error(err);
    }
  }

  btnSaveHotkey.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ hotkey: inputHotkey.value })
      });
      if (res.ok) {
        alert('Đã cập nhật phím tắt!');
      }
    } catch (err) {
      alert('Lỗi: ' + err.message);
    }
  });

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
