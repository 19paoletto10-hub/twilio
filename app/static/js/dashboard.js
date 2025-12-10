'use strict';

(function () {
  const root = document.getElementById('dashboard-root');
  const appContext = root
    ? {
        env: root.dataset.appEnv || 'dev',
        debug: (root.dataset.appDebug || '').toLowerCase() === 'true'
      }
    : { env: 'dev', debug: false };
  window.APP_CONTEXT = appContext;

  const form = document.getElementById('send-message-form');
  const sendButton = document.getElementById('send-message-btn');
  const buttonSpinner = sendButton.querySelector('.spinner-border');
  const tableBody = document.querySelector('#messages-table tbody');
  const toastWrapper = document.getElementById('toast-wrapper');
  const filterButtons = document.querySelectorAll('[data-filter]');

  const autoReplyForm = document.getElementById('auto-reply-form');
  const autoReplyToggle = document.getElementById('auto-reply-enabled');
  const autoReplyMessage = document.getElementById('auto-reply-message');
  const autoReplySaveButton = document.getElementById('auto-reply-save-btn');
  const autoReplySpinner = autoReplySaveButton?.querySelector('.spinner-border');
  const autoReplyBadge = document.getElementById('auto-reply-status-badge');
  const autoReplyLastUpdated = document.getElementById('auto-reply-last-updated');

  // Reminders tab
  const reminderForm = document.getElementById('reminder-form');
  const reminderTo = document.getElementById('reminder-to');
  const reminderBody = document.getElementById('reminder-body');
  const reminderInterval = document.getElementById('reminder-interval');
  const reminderSaveBtn = document.getElementById('reminder-save-btn');
  const reminderSaveSpinner = reminderSaveBtn?.querySelector('.spinner-border');
  const remindersTableBody = document.querySelector('#reminders-table tbody');
  const reminderCountBadge = document.getElementById('reminder-count-badge');

  // AI tab
  const aiForm = document.getElementById('ai-config-form');
  const aiEnabled = document.getElementById('ai-enabled');
  const aiTargetNumber = document.getElementById('ai-target-number');
  const aiSystemPrompt = document.getElementById('ai-system-prompt');
  const aiModel = document.getElementById('ai-model');
  const aiTemperature = document.getElementById('ai-temperature');
  const aiApiKey = document.getElementById('ai-api-key');
  const aiSaveBtn = document.getElementById('ai-save-btn');
  const aiSaveSpinner = aiSaveBtn?.querySelector('.spinner-border');
  const aiStatusBadge = document.getElementById('ai-status-badge');
  const aiUpdatedAt = document.getElementById('ai-updated-at');
  const aiApiKeyPreview = document.getElementById('ai-api-key-preview');
  const aiConversationContainer = document.getElementById('ai-conversation');
    const aiConversationParticipant = document.getElementById('ai-conversation-participant');
  const aiTestMessage = document.getElementById('ai-test-message');
  const aiTestBtn = document.getElementById('ai-test-btn');
  const aiTestSpinner = aiTestBtn?.querySelector('.spinner-border');
  const aiTestStatus = document.getElementById('ai-test-status');
  const aiTestResult = document.getElementById('ai-test-result');

  let currentFilter = 'all';
  let refreshTimer = null;

  const fetchJSON = async (url, options = {}) => {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      ...options
    });

    if (!response.ok) {
      let errorMessage = `Nie udało się pobrać danych (${response.status})`;
      try {
        const payload = await response.json();
        if (payload && payload.error) {
          errorMessage = payload.error;
        }
      } catch (parseError) {
        console.debug('Nie można sparsować odpowiedzi błędu', parseError);
      }
      throw new Error(errorMessage);
    }

    return response.json();
  };

  const showToast = ({ title, message, type = 'success' }) => {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-light border-0 shadow toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <strong class="d-block mb-1">${title}</strong>
          <span>${message}</span>
        </div>
        <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;

    toastWrapper.appendChild(toast);
    const toastInstance = bootstrap.Toast.getOrCreateInstance(toast, { delay: 5000 });
    toastInstance.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
  };

  const escapeHtml = (value = '') =>
    String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

  // Reminders helpers
  const setReminderSaving = (isSaving) => {
    if (!reminderSaveBtn) return;
    if (isSaving) {
      reminderSaveBtn.setAttribute('disabled', 'true');
      reminderSaveSpinner?.classList.remove('d-none');
    } else {
      reminderSaveBtn.removeAttribute('disabled');
      reminderSaveSpinner?.classList.add('d-none');
    }
  };

  const setAiSaving = (isSaving) => {
    if (!aiSaveBtn) return;
    if (isSaving) {
      aiSaveBtn.setAttribute('disabled', 'true');
      aiSaveSpinner?.classList.remove('d-none');
    } else {
      aiSaveBtn.removeAttribute('disabled');
      aiSaveSpinner?.classList.add('d-none');
    }
  };

  const setAiTestLoading = (isLoading) => {
    if (!aiTestBtn) return;
    if (isLoading) {
      aiTestBtn.setAttribute('disabled', 'true');
      aiTestSpinner?.classList.remove('d-none');
    } else {
      aiTestBtn.removeAttribute('disabled');
      aiTestSpinner?.classList.add('d-none');
    }
  };

  const renderReminders = (items = []) => {
    if (!remindersTableBody) return;

    if (!items.length) {
      remindersTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Brak danych.</td></tr>';
      reminderCountBadge && (reminderCountBadge.textContent = '0');
      return;
    }

    const rows = items.map((item) => {
      const enabled = Boolean(item.enabled);
      const badge = enabled
        ? '<span class="badge bg-success-subtle text-success-emphasis">aktywne</span>'
        : '<span class="badge bg-secondary-subtle text-secondary-emphasis">wstrzymane</span>';
      const intervalMinutes = Math.round((item.interval_seconds || 0) / 60);
      const lastSent = item.last_sent_at || '—';
      const nextRun = item.next_run_at || '—';

      return `
        <tr data-id="${item.id}">
          <td class="text-nowrap">${item.to_number || '—'}</td>
          <td class="text-truncate-2">${item.body || ''}</td>
          <td class="text-nowrap">${intervalMinutes} min<br><small class="text-muted">nast.: ${nextRun}</small></td>
          <td class="text-nowrap">${badge}<br><small class="text-muted">ostatnio: ${lastSent}</small></td>
          <td class="text-nowrap d-flex gap-2">
            <button class="btn btn-sm ${enabled ? 'btn-outline-warning' : 'btn-outline-success'}" data-action="toggle">
              ${enabled ? 'Wstrzymaj' : 'Wznów'}
            </button>
            <button class="btn btn-sm btn-outline-danger" data-action="delete">Usuń</button>
          </td>
        </tr>
      `;
    });

    remindersTableBody.innerHTML = rows.join('');
    reminderCountBadge && (reminderCountBadge.textContent = String(items.length));
  };

  const renderRemindersSkeleton = () => {
    if (!remindersTableBody) return;
    const row = `
      <tr>
        <td colspan="5">
          <div class="skeleton skeleton-row">
            <div class="skeleton-line skeleton-line--short mb-2"></div>
            <div class="skeleton-line skeleton-line--full mb-1"></div>
            <div class="skeleton-line skeleton-line--medium"></div>
          </div>
        </td>
      </tr>
    `;
    remindersTableBody.innerHTML = row + row;
    reminderCountBadge && (reminderCountBadge.textContent = '—');
  };

  const renderAiConfig = (config) => {
    if (!config) return;

    if (aiEnabled) aiEnabled.checked = !!config.enabled;
    if (aiTargetNumber) aiTargetNumber.value = config.target_number || '';
    if (aiSystemPrompt) aiSystemPrompt.value = config.system_prompt || '';
    if (aiModel) aiModel.value = config.model || '';
    if (aiTemperature) {
      aiTemperature.value =
        typeof config.temperature === 'number' ? config.temperature : '';
    }

    if (aiStatusBadge) {
      const enabled = !!config.enabled;
      aiStatusBadge.textContent = enabled ? 'Włączone' : 'Wyłączone';
      aiStatusBadge.className = enabled
        ? 'badge bg-success-subtle text-success-emphasis'
        : 'badge bg-secondary-subtle text-secondary-emphasis';
    }

    if (aiApiKeyPreview) {
      if (config.api_key_preview) {
        aiApiKeyPreview.textContent = `Zapisany klucz: ${config.api_key_preview}`;
      } else if (config.has_api_key) {
        aiApiKeyPreview.textContent = 'Zapisany jest klucz API.';
      } else {
        aiApiKeyPreview.textContent = 'Brak zapisanego klucza.';
      }
    }

    if (aiUpdatedAt) {
      aiUpdatedAt.textContent = config.updated_at
        ? `Ostatnia aktualizacja: ${config.updated_at}`
        : '';
    }

    if (aiConversationParticipant) {
      aiConversationParticipant.textContent = config.target_number || 'Brak skonfigurowanego numeru';
    }
  };

  const renderAiConversation = (items = []) => {
    if (!aiConversationContainer) return;

    if (!items.length) {
      aiConversationContainer.innerHTML = '<div class="text-center text-muted py-4">Brak wiadomości w rozmowie z wybranym numerem.</div>';
      return;
    }

    let lastDateKey = null;
    const parts = [];

    for (const msg of items) {
      const createdRaw = msg.created_at || '';
      const createdDate = createdRaw ? new Date(createdRaw.endsWith('Z') ? createdRaw : `${createdRaw}Z`) : null;
      const dateKey = createdDate && !Number.isNaN(createdDate.getTime())
        ? createdDate.toISOString().substring(0, 10)
        : null;

      if (dateKey && dateKey !== lastDateKey) {
        const label = createdDate.toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: '2-digit'
        });
        parts.push(`<div class="ai-date-divider"><span>${escapeHtml(label)}</span></div>`);
        lastDateKey = dateKey;
      }

      const isInbound = msg.direction === 'inbound';
      const bubbleClass = isInbound ? 'chat-bubble chat-bubble--inbound' : 'chat-bubble chat-bubble--outbound';
      const author = isInbound ? 'Użytkownik' : 'AI';
      const timestamp = formatDateTime(createdRaw);
      const status = msg.status
        ? msg.status
        : isInbound
          ? 'odebrano'
          : 'wysłano';
      const body = escapeHtml(msg.body || '');
      const errorLine = msg.error ? `<div class="chat-bubble__error">${escapeHtml(msg.error)}</div>` : '';

      parts.push(`
        <div class="${bubbleClass}">
          <div class="chat-bubble__meta">
            <span>${author}</span>
            <span>${timestamp}</span>
          </div>
          <div class="chat-bubble__body">${body.replace(/\n/g, '<br>')}</div>
          <div class="chat-bubble__status">Status: ${escapeHtml(status)}</div>
          ${errorLine}
        </div>
      `);
    }

    aiConversationContainer.innerHTML = parts.join('');

    requestAnimationFrame(() => {
      aiConversationContainer.scrollTop = aiConversationContainer.scrollHeight;
    });
  };

  const renderAiConversationSkeleton = () => {
    if (!aiConversationContainer) return;
    aiConversationContainer.innerHTML = `
      <div class="chat-bubble chat-bubble--inbound skeleton skeleton-chat-bubble">
        <div class="d-flex justify-content-between mb-2">
          <div class="skeleton-line skeleton-line--short"></div>
          <div class="skeleton-line skeleton-line--medium"></div>
        </div>
        <div class="skeleton-line skeleton-line--full mb-1"></div>
        <div class="skeleton-line skeleton-line--medium"></div>
      </div>
      <div class="chat-bubble chat-bubble--outbound skeleton skeleton-chat-bubble">
        <div class="d-flex justify-content-between mb-2">
          <div class="skeleton-line skeleton-line--short"></div>
          <div class="skeleton-line skeleton-line--medium"></div>
        </div>
        <div class="skeleton-line skeleton-line--full mb-1"></div>
        <div class="skeleton-line skeleton-line--medium"></div>
      </div>
    `;
  };

  const renderAiTestResult = (payload) => {
    if (!aiTestResult) return;

    if (!payload) {
      aiTestResult.classList.add('d-none');
      aiTestResult.innerHTML = '';
      return;
    }

    const reply = escapeHtml(payload.reply || '');
    const input = escapeHtml(payload.input || '');
    const modelParts = [];
    if (payload.model) {
      modelParts.push(String(payload.model));
    }
    if (typeof payload.temperature === 'number') {
      modelParts.push(`temp ${payload.temperature}`);
    }
    const modelInfo = escapeHtml(modelParts.join(' • '));

    const sourceType = payload.used_latest_message
      ? 'Ostatnia wiadomość z historii'
      : payload.fallback_used
        ? 'Domyślny prompt testowy'
        : 'Własna wiadomość testowa';
    const sourceBadgeClass = payload.used_latest_message
      ? 'bg-primary-subtle text-primary-emphasis'
      : payload.fallback_used
        ? 'bg-secondary-subtle text-secondary-emphasis'
        : 'bg-info-subtle text-info-emphasis';
    const latest = payload.latest_message || null;
    const latestPreview = latest
      ? `
        <div class="small text-muted mt-2">
          Ostatnia wiadomość (${escapeHtml(latest.created_at || '')}):
          <span class="d-block">${escapeHtml(latest.body || '')}</span>
        </div>
      `
      : '';

    aiTestResult.innerHTML = `
      <p class="small text-muted mb-2">Model: ${modelInfo || 'nieznany'}</p>
      <div class="mb-2">
        <span class="badge ${sourceBadgeClass}">${escapeHtml(sourceType)}</span>
      </div>
      <div class="mb-2">
        <div class="fw-semibold small text-muted text-uppercase mb-1">Wiadomość testowa</div>
        <div class="p-2 bg-white border rounded">${input || '<span class="text-muted">—</span>'}</div>
        ${latestPreview}
      </div>
      <div>
        <div class="fw-semibold small text-muted text-uppercase mb-1">Odpowiedź AI</div>
        <div class="p-2 bg-white border rounded">${reply}</div>
      </div>
    `;
    aiTestResult.classList.remove('d-none');
  };

  const loadReminders = async () => {
    try {
      renderRemindersSkeleton();
      const data = await fetchJSON('/api/reminders');
      renderReminders(data.items || []);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać przypomnień.', type: 'error' });
    }
  };

  const loadAiConfig = async () => {
    if (!aiForm) return;
    try {
      const data = await fetchJSON('/api/ai/config');
      renderAiConfig(data);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać konfiguracji AI.', type: 'error' });
    }
  };

  const loadAiConversation = async () => {
    if (!aiConversationContainer) return;
    try {
      renderAiConversationSkeleton();
      const data = await fetchJSON('/api/ai/conversation');
      renderAiConversation(data.items || []);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać historii rozmowy AI.', type: 'error' });
    }
  };
  let aiRefreshTimer = null;

  const submitReminder = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!reminderForm) return;
    if (!reminderForm.checkValidity()) {
      reminderForm.classList.add('was-validated');
      return;
    }

    const to = reminderTo?.value.trim();
    const body = reminderBody?.value.trim();
    const intervalMinutes = Number(reminderInterval?.value || 0);

    if (!to || !body || intervalMinutes < 1) {
      reminderForm.classList.add('was-validated');
      return;
    }

    setReminderSaving(true);

    try {
      const res = await fetchJSON('/api/reminders', {
        method: 'POST',
        body: JSON.stringify({ to, body, interval_minutes: intervalMinutes })
      });
      renderReminders(res.items || []);
      reminderForm.reset();
      reminderForm.classList.remove('was-validated');
      showToast({ title: 'Zapisano', message: 'Przypomnienie dodane.', type: 'success' });
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się zapisać przypomnienia.', type: 'error' });
    } finally {
      setReminderSaving(false);
    }
  };

  const submitAiConfig = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!aiForm) return;

    const enabled = !!aiEnabled?.checked;
    const targetNumber = aiTargetNumber?.value.trim() || '';
    const systemPrompt = aiSystemPrompt?.value.trim() || '';
    const model = aiModel?.value.trim() || '';
    const temperatureRaw = aiTemperature?.value.trim() || '';
    const apiKeyRaw = aiApiKey?.value.trim() || '';

    const payload = {
      enabled,
      target_number: targetNumber || null,
      system_prompt: systemPrompt || null,
      model: model || null
    };

    if (temperatureRaw !== '') {
      const t = parseFloat(temperatureRaw);
      if (!Number.isNaN(t)) {
        payload.temperature = t;
      }
    }

    if (apiKeyRaw) {
      payload.api_key = apiKeyRaw;
    }

    try {
      setAiSaving(true);
      const data = await fetchJSON('/api/ai/config', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      renderAiConfig(data);
      if (aiApiKey) aiApiKey.value = '';
      showToast({ title: 'Zapisano', message: 'Konfiguracja AI została zapisana.', type: 'success' });
      await loadAiConversation();
    } catch (error) {
      console.error(error);
      const msg = error.message || '';
      if (msg.includes('Target number is required')) {
        showToast({ title: 'Błąd', message: 'Podaj numer rozmówcy, aby włączyć AI.', type: 'error' });
      } else if (msg.includes('API key is required')) {
        showToast({ title: 'Błąd', message: 'Podaj klucz API OpenAI, aby włączyć AI.', type: 'error' });
      } else if (msg.includes('Temperature must be')) {
        showToast({ title: 'Błąd', message: 'Temperatura musi być liczbą z zakresu 0–2.', type: 'error' });
      } else {
        showToast({ title: 'Błąd', message: msg || 'Nie udało się zapisać konfiguracji AI.', type: 'error' });
      }
    } finally {
      setAiSaving(false);
    }
  };

  const runAiTest = async () => {
    if (!aiTestBtn) return;
    const message = aiTestMessage?.value.trim();
    const apiKeyOverride = aiApiKey?.value.trim();
    const participantOverride = aiTargetNumber?.value.trim();
    setAiTestLoading(true);
    renderAiTestResult(null);
    if (aiTestStatus) {
      aiTestStatus.textContent = 'Łączenie z OpenAI...';
    }

    try {
      const payload = {
        use_latest_message: true
      };
      if (message) {
        payload.message = message;
      }
      if (apiKeyOverride) {
        payload.api_key = apiKeyOverride;
      }
      if (participantOverride) {
        payload.participant = participantOverride;
      }

      const data = await fetchJSON('/api/ai/test', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      renderAiTestResult(data);
      if (aiTestStatus) {
        aiTestStatus.textContent = data.used_latest_message
          ? 'Połączenie OK — użyto ostatniej wiadomości z historii.'
          : 'Połączenie OK — odpowiedź wygenerowana na podstawie tekstu testowego.';
      }
    } catch (error) {
      console.error(error);
      if (aiTestStatus) {
        aiTestStatus.textContent = error.message || 'Błąd połączenia z OpenAI.';
      }
      renderAiTestResult(null);
    } finally {
      setAiTestLoading(false);
    }
  };

  const handleReminderAction = async (event) => {
    const actionBtn = event.target.closest('button[data-action]');
    if (!actionBtn) return;
    const row = actionBtn.closest('tr[data-id]');
    if (!row) return;
    const id = row.getAttribute('data-id');
    const action = actionBtn.dataset.action;

    try {
      if (action === 'delete') {
        const res = await fetchJSON(`/api/reminders/${id}`, { method: 'DELETE' });
        renderReminders(res.items || []);
        showToast({ title: 'Usunięto', message: 'Przypomnienie usunięte.', type: 'success' });
      }

      if (action === 'toggle') {
        const isEnabled = actionBtn.textContent.includes('Wstrzymaj');
        const res = await fetchJSON(`/api/reminders/${id}/toggle`, {
          method: 'POST',
          body: JSON.stringify({ enabled: !isEnabled })
        });
        renderReminders(res.items || []);
        showToast({ title: 'Zapisano', message: !isEnabled ? 'Przypomnienie włączone.' : 'Przypomnienie wstrzymane.', type: 'success' });
      }
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Operacja nieudana.', type: 'error' });
    }
  };

  const setAutoReplyBadge = (enabled) => {
    if (!autoReplyBadge) {
      return;
    }
    autoReplyBadge.className = enabled
      ? 'badge bg-success-subtle text-success-emphasis'
      : 'badge bg-secondary-subtle text-secondary-emphasis';
    autoReplyBadge.textContent = enabled ? 'Auto-odpowiedź włączona' : 'Auto-odpowiedź wyłączona';
  };

  const setAutoReplyLoading = (isLoading) => {
    if (!autoReplySaveButton) {
      return;
    }
    if (isLoading) {
      autoReplySaveButton.setAttribute('disabled', 'true');
      autoReplyToggle?.setAttribute('disabled', 'true');
      autoReplyMessage?.setAttribute('disabled', 'true');
      autoReplySpinner?.classList.remove('d-none');
    } else {
      autoReplySaveButton.removeAttribute('disabled');
      autoReplyToggle?.removeAttribute('disabled');
      autoReplyMessage?.removeAttribute('disabled');
      autoReplySpinner?.classList.add('d-none');
    }
  };

  const syncAutoReplyMessageRequirement = () => {
    if (!autoReplyMessage || !autoReplyToggle) {
      return;
    }
    const enabled = autoReplyToggle.checked;
    autoReplyMessage.required = enabled;
    if (enabled) {
      autoReplyMessage.setAttribute('aria-required', 'true');
    } else {
      autoReplyMessage.removeAttribute('aria-required');
    }
  };

  const renderAutoReplyConfig = (config) => {
    if (!autoReplyForm || !autoReplyToggle || !autoReplyMessage) {
      return;
    }

    const enabled = Boolean(config?.enabled);
    autoReplyToggle.checked = enabled;
    autoReplyMessage.value = config?.message || '';
    setAutoReplyBadge(enabled);
    syncAutoReplyMessageRequirement();

    if (autoReplyLastUpdated) {
      autoReplyLastUpdated.textContent = `Ostatnia aktualizacja: ${new Date().toLocaleString()}`;
    }
  };

  const loadAutoReplyConfig = async () => {
    if (!autoReplyForm) {
      return;
    }
    setAutoReplyLoading(true);
    try {
      const config = await fetchJSON('/api/auto-reply/config');
      renderAutoReplyConfig(config);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać konfiguracji.', type: 'error' });
    } finally {
      setAutoReplyLoading(false);
    }
  };

  const submitAutoReplyConfig = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!autoReplyForm) {
      return;
    }

    const enabled = !!autoReplyToggle?.checked;
    const message = (autoReplyMessage?.value || '').trim();

    if (enabled && !message) {
      autoReplyForm.classList.add('was-validated');
      return;
    }

    setAutoReplyLoading(true);

    try {
      const config = await fetchJSON('/api/auto-reply/config', {
        method: 'POST',
        body: JSON.stringify({ enabled, message })
      });
      renderAutoReplyConfig(config);
      autoReplyForm.classList.remove('was-validated');
      showToast({
        title: 'Zapisano',
        message: enabled ? 'Auto-odpowiedź włączona.' : 'Auto-odpowiedź wyłączona.',
        type: 'success'
      });
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się zapisać ustawień.', type: 'error' });
    } finally {
      setAutoReplyLoading(false);
    }
  };

  const formatDirectionBadge = (direction) => {
    const normalized = direction === 'inbound' ? 'inbound' : 'outbound';
    const label = normalized === 'inbound' ? 'Przychodząca' : 'Wychodząca';
    const badgeClass = normalized === 'inbound' ? 'bg-success-subtle text-success-emphasis' : 'bg-info-subtle text-info-emphasis';
    return `<span class="badge ${badgeClass} text-uppercase fw-semibold">${label}</span>`;
  };

  const encodeParticipantForUrl = (value) => encodeURIComponent(value || '');

  const buildChatLink = (participant) => {
    if (!participant) {
      return null;
    }
    return `/chat/${encodeParticipantForUrl(participant)}`;
  };

  const formatStatusBadge = (status) => {
    if (!status) {
      return '<span class="badge bg-secondary-subtle text-secondary-emphasis">brak danych</span>';
    }

    const statusMap = {
      queued: 'bg-warning-subtle text-warning-emphasis',
      sending: 'bg-warning-subtle text-warning-emphasis',
      sent: 'bg-info-subtle text-info-emphasis',
      delivered: 'bg-success-subtle text-success-emphasis',
      received: 'bg-success-subtle text-success-emphasis',
      read: 'bg-success-subtle text-success-emphasis',
      failed: 'bg-danger-subtle text-danger-emphasis',
      undelivered: 'bg-danger-subtle text-danger-emphasis',
      generated: 'bg-secondary-subtle text-secondary-emphasis'
    };

    const normalized = status.toLowerCase();
    const badgeClass = statusMap[normalized] || 'bg-secondary-subtle text-secondary-emphasis';
    return `<span class="badge ${badgeClass}">${status}</span>`;
  };

  const formatDateTime = (value) => {
    if (!value) {
      return '—';
    }

    const iso = value.endsWith('Z') ? value : `${value}Z`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  };

  const buildMessagePreview = (body) => {
    const text = (body || '').trim();
    if (!text) return '';
    if (text.length <= 100) return text;
    return `${text.slice(0, 97)}…`;
  };

  const buildParticipantDisplay = (raw, direction) => {
    const value = (raw || '').trim();
    if (!value) {
      return {
        main: '—',
        meta: direction === 'inbound' ? 'nieznany nadawca' : 'nieznany odbiorca'
      };
    }

    let channel = 'SMS';
    let normalized = value;

    if (value.toLowerCase().startsWith('whatsapp:')) {
      channel = 'WhatsApp';
      normalized = value.slice('whatsapp:'.length);
    } else if (value.toLowerCase().startsWith('mms:')) {
      channel = 'MMS';
      normalized = value.slice('mms:'.length);
    } else if (value.toLowerCase().startsWith('sms:')) {
      channel = 'SMS';
      normalized = value.slice('sms:'.length);
    }

    const role = direction === 'inbound' ? 'od klienta' : 'do klienta';
    return {
      main: normalized || value,
      meta: `${channel} • ${role}`
    };
  };

  const buildDateTimeParts = (value) => {
    const fullLabel = formatDateTime(value);
    if (!value) {
      return { dateLabel: '—', timeLabel: '', fullLabel };
    }

    const iso = value.endsWith('Z') ? value : `${value}Z`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) {
      return { dateLabel: fullLabel, timeLabel: '', fullLabel };
    }

    const dateLabel = date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
    const timeLabel = date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit'
    });

    return { dateLabel, timeLabel, fullLabel };
  };

  const renderMessagesSkeleton = () => {
    if (!tableBody) return;
    const skeletonRow = (idx) => `
      <tr>
        <td colspan="6">
          <div class="skeleton skeleton-row">
            <div class="d-flex justify-content-between mb-2">
              <div class="skeleton-line skeleton-line--short me-2"></div>
              <div class="skeleton-line skeleton-line--medium"></div>
            </div>
            <div class="skeleton-line skeleton-line--full mb-1"></div>
            <div class="skeleton-line skeleton-line--medium"></div>
          </div>
        </td>
      </tr>
    `;
    tableBody.innerHTML = [0, 1, 2].map(skeletonRow).join('');
  };

  const renderMessages = (items) => {
    if (!items.length) {
      tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Brak wiadomości do wyświetlenia.</td></tr>';
      return;
    }

    const rows = items.map((item) => {
      const directionCell = formatDirectionBadge(item.direction);
      const participantRaw = item.direction === 'inbound' ? item.from_number : item.to_number;
      const participant = buildParticipantDisplay(participantRaw, item.direction);
      const statusCell = formatStatusBadge(item.status);
      const { dateLabel, timeLabel, fullLabel } = buildDateTimeParts(item.created_at);
      const errorLine = item.error ? `<div class="text-danger small mt-1 text-truncate-2">${escapeHtml(item.error)}</div>` : '';
      const chatUrl = buildChatLink(participantRaw);
      const chatCell = chatUrl
        ? `<a class="btn btn-outline-primary btn-sm" href="${chatUrl}">Otwórz</a>`
        : '—';
      const bodyPreview = escapeHtml(buildMessagePreview(item.body));
      const rowClasses = ['messages-row'];
      if (chatUrl) {
        rowClasses.push('messages-row--clickable');
      }
      const rowAttrs = [
        `class="${rowClasses.join(' ')}"`,
        chatUrl ? `data-chat-url="${chatUrl}"` : ''
      ].filter(Boolean).join(' ');

      return `
        <tr ${rowAttrs}>
          <td class="text-nowrap">${directionCell}</td>
          <td class="text-nowrap" title="${escapeHtml(participant.main)}">
            <div class="messages-participant">
              <span class="messages-participant__number text-truncate-1">${escapeHtml(participant.main)}</span>
              <span class="messages-participant__meta text-truncate-1">${escapeHtml(participant.meta)}</span>
            </div>
          </td>
          <td>
            <div class="text-truncate-1" title="${bodyPreview}">${bodyPreview}</div>
          </td>
          <td class="text-nowrap">
            ${statusCell}
            ${errorLine}
          </td>
          <td class="text-nowrap">${chatCell}</td>
          <td class="text-nowrap">
            <div class="messages-datetime" title="${escapeHtml(fullLabel)}">
              <span class="messages-datetime__time">${escapeHtml(timeLabel)}</span>
              <span class="messages-datetime__date">${escapeHtml(dateLabel)}</span>
            </div>
          </td>
        </tr>
      `;
    });

    tableBody.innerHTML = rows.join('');
  };

  const handleMessagesRowClick = (event) => {
    const interactiveTarget = event.target.closest('a, button, input, textarea, select, label');
    if (interactiveTarget) {
      return;
    }

    const row = event.target.closest('tr[data-chat-url]');
    if (!row) return;

    const url = row.getAttribute('data-chat-url');
    if (!url) return;

    window.location.href = url;
  };

  const refreshMessages = async () => {
    try {
      renderMessagesSkeleton();
      const directionParam = currentFilter === 'all' ? '' : `&direction=${currentFilter}`;
      const data = await fetchJSON(`/api/messages?limit=50${directionParam}`);
      renderMessages(data.items || []);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: 'Nie udało się odświeżyć listy wiadomości.', type: 'error' });
    }
  };

  const refreshStats = async () => {
    try {
      const stats = await fetchJSON('/api/messages/stats');
      document.getElementById('stat-total').textContent = stats.total ?? 0;
      document.getElementById('stat-inbound').textContent = stats.inbound ?? 0;
      document.getElementById('stat-outbound').textContent = stats.outbound ?? 0;

      if (appContext.debug) {
        console.debug('Stats updated', stats);
      }
    } catch (error) {
      console.error(error);
    }
  };

  const startAutoRefresh = () => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(() => {
      refreshMessages();
      refreshStats();
    }, 15000);
  };

  const setLoadingState = (isLoading) => {
    if (isLoading) {
      sendButton.setAttribute('disabled', 'true');
      buttonSpinner.classList.remove('d-none');
    } else {
      sendButton.removeAttribute('disabled');
      buttonSpinner.classList.add('d-none');
    }
  };

  const resetForm = () => {
    form.reset();
    form.classList.remove('was-validated');
  };

  const submitForm = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!form.checkValidity()) {
      form.classList.add('was-validated');
      return;
    }

    setLoadingState(true);

    const normalizedRecipient = document.getElementById('recipient-input').value.trim();

    const payload = {
      to: normalizedRecipient,
      body: document.getElementById('message-body').value.trim()
    };

    try {
      const response = await fetchJSON('/api/send-message', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      showToast({
        title: 'Sukces',
        message: `Wiadomość została wysłana. SID: ${response.sid}`,
        type: 'success'
      });

      resetForm();
      await refreshMessages();
      await refreshStats();
    } catch (error) {
      console.error(error);
      showToast({
        title: 'Błąd',
        message: 'Nie udało się wysłać wiadomości. Sprawdź konfigurację Twilio.',
        type: 'error'
      });
    } finally {
      setLoadingState(false);
    }
  };

  const handleFilterClick = (event) => {
    const { filter } = event.currentTarget.dataset;
    if (!filter || filter === currentFilter) {
      return;
    }

    currentFilter = filter;
    filterButtons.forEach((button) => {
      if (button.dataset.filter === filter) {
        button.classList.add('active');
      } else {
        button.classList.remove('active');
      }
    });

    refreshMessages();
  };

  const init = () => {
    if (form && sendButton && tableBody) {
      form.addEventListener('submit', submitForm);
      filterButtons.forEach((button) => button.addEventListener('click', handleFilterClick));
      tableBody.addEventListener('click', handleMessagesRowClick);
      refreshMessages();
      refreshStats();
      startAutoRefresh();
    }

    if (autoReplyForm) {
      syncAutoReplyMessageRequirement();
      autoReplyForm.addEventListener('submit', submitAutoReplyConfig);
      autoReplyToggle?.addEventListener('change', syncAutoReplyMessageRequirement);
      loadAutoReplyConfig();
    }

    if (reminderForm) {
      reminderForm.addEventListener('submit', submitReminder);
      remindersTableBody?.addEventListener('click', handleReminderAction);
      loadReminders();
    }

    if (aiForm) {
      aiForm.addEventListener('submit', submitAiConfig);
      loadAiConfig();
      loadAiConversation();
      if (!aiRefreshTimer) {
        aiRefreshTimer = setInterval(() => {
          loadAiConversation();
        }, 20000);
      }
    }

    aiTestBtn?.addEventListener('click', runAiTest);
  };

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (refreshTimer) {
        clearInterval(refreshTimer);
      }
      if (aiRefreshTimer) {
        clearInterval(aiRefreshTimer);
        aiRefreshTimer = null;
      }
    } else {
      refreshMessages();
      refreshStats();
      startAutoRefresh();
      if (aiForm && !aiRefreshTimer) {
        aiRefreshTimer = setInterval(() => {
          loadAiConversation();
        }, 20000);
      }
    }
  });

  document.addEventListener('DOMContentLoaded', init);
})();
