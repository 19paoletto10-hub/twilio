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

  // News tab  
  const newsAddRecipientForm = document.getElementById('news-add-recipient-form');
  const newsRecipientPhone = document.getElementById('news-recipient-phone');
  const newsRecipientTime = document.getElementById('news-recipient-time');
  const newsRecipientPrompt = document.getElementById('news-recipient-prompt');
  const newsRecipientAllCat = document.getElementById('news-recipient-allcat');
  const newsAddSpinner = document.getElementById('news-add-spinner');
  const newsRecipientsList = document.getElementById('news-recipients-list');
  const newsRecipientsCount = document.getElementById('news-recipients-count');
  const newsRecipientsRefreshBtn = document.getElementById('news-recipients-refresh-btn');
  const newsForm = document.getElementById('news-config-form');
  const newsNotificationEnabled = document.getElementById('news-notification-enabled');
  const newsTargetNumber = document.getElementById('news-target-number');
  const newsNotificationTime = document.getElementById('news-notification-time');
  const newsNotificationPrompt = document.getElementById('news-notification-prompt');
  const newsSaveBtn = document.getElementById('news-save-btn');
  const newsSaveSpinner = newsSaveBtn?.querySelector('.spinner-border');
  const newsStatusBadge = document.getElementById('news-status-badge');
  const newsUpdatedAt = document.getElementById('news-updated-at');
  const newsTestBtn = document.getElementById('news-test-btn');
  const newsTestSpinner = newsTestBtn?.querySelector('.spinner-border');
  const newsTestStatus = document.getElementById('news-test-status');
  const newsLastTest = document.getElementById('news-last-test');
  const newsTestTarget = document.getElementById('news-test-target');
  const newsTestResult = document.getElementById('news-test-result');
  const newsFaissQuery = document.getElementById('news-faiss-query');
  const newsFaissTestBtn = document.getElementById('news-faiss-test-btn');
  const newsFaissTestSpinner = newsFaissTestBtn?.querySelector('.spinner-border');
  const newsFaissResult = document.getElementById('news-faiss-result');
  const newsFaissAnswer = document.getElementById('news-faiss-answer');
  const newsFaissMeta = document.getElementById('news-faiss-meta');
  const newsFaissAllCat = document.getElementById('news-faiss-allcat');
  const newsLastBuild = document.getElementById('news-last-build');
  const newsLastNotification = document.getElementById('news-last-notification');
  const newsIndicesTableBody = document.querySelector('#news-indices-table tbody');
  const newsIndicesError = document.getElementById('news-indices-error');
  const newsIndicesCount = document.getElementById('news-indices-count');
  const newsRefreshIndicesBtn = document.getElementById('news-refresh-indices-btn');
  const newsScrapeBtn = document.getElementById('news-scrape-btn');
  const newsScrapeSpinner = document.getElementById('news-scrape-spinner');
  const newsScrapeStatus = document.getElementById('news-scrape-status');
  const newsScrapeLog = document.getElementById('news-scrape-log');
  const newsFilesGrid = document.getElementById('news-files-grid');
  const newsFilesEmpty = document.getElementById('news-files-empty');
  const newsFilesRefreshBtn = document.getElementById('news-files-refresh-btn');
  const newsBuildIndexBtn = document.getElementById('news-build-index-btn');
  const newsBuildIndexSpinner = document.getElementById('news-build-index-spinner');
  const newsFileOverlay = document.getElementById('news-file-overlay');
  const newsOverlayTitle = document.getElementById('news-overlay-title');
  const newsOverlayMeta = document.getElementById('news-overlay-meta');
  const newsOverlayContent = document.getElementById('news-overlay-content');
  const newsOverlayCloseBtn = document.getElementById('news-overlay-close-btn');
  const newsFaissStatusPill = document.getElementById('news-faiss-status-pill');
  const newsFaissStatusUpdated = document.getElementById('news-faiss-status-updated');
  const newsFaissStatusMeta = document.getElementById('news-faiss-status-meta');
  const newsFaissStatusSize = document.getElementById('news-faiss-status-size');
  const newsFaissEmbedding = document.getElementById('news-faiss-embedding');
  const newsFaissChat = document.getElementById('news-faiss-chat');
  const newsFaissVectors = document.getElementById('news-faiss-vectors');
  const newsFaissIndexPath = document.getElementById('news-faiss-index-path');
  const newsFaissSnapshot = document.getElementById('news-faiss-snapshot');
  const newsFaissStatusError = document.getElementById('news-faiss-status-error');
  const newsFaissStatusRefreshBtn = document.getElementById('news-faiss-status-refresh-btn');
  const newsFaissQuickTestBtn = document.getElementById('news-faiss-quick-test-btn');
  const newsFaissSnippets = document.getElementById('news-faiss-snippets');
  const newsFaissSnippetsList = document.getElementById('news-faiss-snippets-list');
  const newsFaissBackupBtn = document.getElementById('news-faiss-backup-btn');
  const newsFaissRestoreBtn = document.getElementById('news-faiss-restore-btn');
  const newsFaissRestoreInput = document.getElementById('news-faiss-restore-input');
  const newsFaissBackupStatus = document.getElementById('news-faiss-backup-status');

  // Multi-SMS tab
  const multiSmsForm = document.getElementById('multi-sms-form');
  const multiSmsRecipientsField = document.getElementById('multi-sms-recipients');
  const multiSmsBodyField = document.getElementById('multi-sms-body');
  const multiSmsSubmitBtn = document.getElementById('multi-sms-submit-btn');
  const multiSmsSubmitSpinner = multiSmsSubmitBtn?.querySelector('.spinner-border');
  const multiSmsHistory = document.getElementById('multi-sms-history');
  const multiSmsHistoryEmpty = document.getElementById('multi-sms-history-empty');
  const multiSmsRefreshBtn = document.getElementById('multi-sms-refresh-btn');
  const multiSmsBatchCount = document.getElementById('multi-sms-batch-count');

  const DEFAULT_NEWS_PROMPT = window.NEWS_DEFAULT_PROMPT || 'Stwórz krótkie podsumowanie najważniejszych newsów biznesowych z ostatnich godzin.';
  const ALL_CATEGORIES_PROMPT = window.NEWS_ALL_CATEGORIES_PROMPT || (
    'Przygotuj profesjonalne streszczenie wszystkich kategorii newsów. ' +
    'Dla każdej kategorii wypisz nagłówek i 2-3 wypunktowania z konkretami. ' +
    'Jeśli brakuje danych, dopisz informację "brak danych".'
  );
  const DEFAULT_FAISS_PROMPT = DEFAULT_NEWS_PROMPT;
  const FAISS_BACKUP_MAX_BYTES = 250 * 1024 * 1024; // 250 MB limit zgodny z backendem

  let currentFilter = 'all';
  let refreshTimer = null;
  let lastFaissStatus = null;
  let isFaissBackupBusy = false;

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

  const formatBytes = (bytes = 0) => {
    if (!Number.isFinite(bytes) || bytes <= 0) {
      return '0 B';
    }
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / 1024 ** index;
    return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`;
  };

  const parseContentDispositionFilename = (headerValue) => {
    if (!headerValue) return null;

    const encodedMatch = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch && encodedMatch[1]) {
      try {
        return decodeURIComponent(encodedMatch[1]);
      } catch (error) {
        console.debug('Nie można zdekodować nazwy pliku z nagłówka', error);
        return encodedMatch[1];
      }
    }

    const simpleMatch = headerValue.match(/filename="?([^";]+)"?/i);
    if (simpleMatch && simpleMatch[1]) {
      return simpleMatch[1];
    }
    return null;
  };

  const readErrorMessage = async (response, fallbackMessage = 'Wystąpił błąd.') => {
    let message = fallbackMessage;
    if (!response) {
      return message;
    }

    try {
      const raw = await response.text();
      if (!raw) {
        return message;
      }

      try {
        const payload = JSON.parse(raw);
        if (payload && (payload.error || payload.message)) {
          message = payload.error || payload.message;
        } else {
          message = raw;
        }
      } catch (parseError) {
        message = raw;
      }
    } catch (error) {
      console.debug('Nie można odczytać treści błędu', error);
    }

    return message;
  };

  const lockTextareaPrompt = (textarea, lock, forcedValue, fallbackValue = '') => {
    if (!textarea) return;
    if (lock) {
      if (textarea.dataset.previousValue === undefined && textarea.value !== forcedValue) {
        textarea.dataset.previousValue = textarea.value;
      }
      textarea.value = forcedValue;
      textarea.setAttribute('readonly', 'true');
      textarea.classList.add('bg-light', 'text-muted');
    } else {
      const restore = textarea.dataset.previousValue;
      textarea.value = restore !== undefined ? restore : fallbackValue;
      textarea.removeAttribute('readonly');
      textarea.classList.remove('bg-light', 'text-muted');
      delete textarea.dataset.previousValue;
    }
  };

  const syncRecipientPromptMode = () => {
    const lock = !!newsRecipientAllCat?.checked;
    lockTextareaPrompt(newsRecipientPrompt, lock, ALL_CATEGORIES_PROMPT, DEFAULT_NEWS_PROMPT);
  };

  const syncFaissPromptMode = () => {
    if (!newsFaissQuery) return;
    const lock = !!newsFaissAllCat?.checked;
    const fallbackValue = newsFaissQuery.dataset.previousValue ?? newsFaissQuery.value;
    lockTextareaPrompt(newsFaissQuery, lock, ALL_CATEGORIES_PROMPT, fallbackValue);
  };

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

  const setNewsSaving = (isSaving) => {
    if (!newsSaveBtn) return;
    if (isSaving) {
      newsSaveBtn.setAttribute('disabled', 'true');
      newsSaveSpinner?.classList.remove('d-none');
    } else {
      newsSaveBtn.removeAttribute('disabled');
      newsSaveSpinner?.classList.add('d-none');
    }
  };

  const setNewsTesting = (isLoading) => {
    if (!newsTestBtn) return;
    if (isLoading) {
      newsTestBtn.setAttribute('disabled', 'true');
      newsTestSpinner?.classList.remove('d-none');
    } else {
      newsTestBtn.removeAttribute('disabled');
      newsTestSpinner?.classList.add('d-none');
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
      const modeBadge = item.use_all_categories
        ? '<span class="badge bg-primary-subtle text-primary-emphasis ms-2">wszystkie kategorie</span>'
        : '<span class="badge bg-info-subtle text-info-emphasis ms-2">prompt niestandardowy</span>';
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

  const renderNewsConfig = (config) => {
    if (!newsForm) return;

    const notificationEnabled = !!config?.notification_enabled;
    if (newsNotificationEnabled) newsNotificationEnabled.checked = notificationEnabled;
    if (newsTargetNumber) newsTargetNumber.value = config?.target_number || '';

    const notificationTime = config?.notification_time || '08:00';
    if (newsNotificationTime) newsNotificationTime.value = notificationTime;

    const notificationPrompt = config?.notification_prompt || DEFAULT_NEWS_PROMPT;
    if (newsNotificationPrompt) newsNotificationPrompt.value = notificationPrompt;

    if (newsStatusBadge) {
      newsStatusBadge.textContent = notificationEnabled ? 'Włączone' : 'Wyłączone';
      newsStatusBadge.className = notificationEnabled
        ? 'badge bg-success-subtle text-success-emphasis'
        : 'badge bg-secondary-subtle text-secondary-emphasis';
    }

    if (newsUpdatedAt) {
      newsUpdatedAt.textContent = config?.updated_at ? `Ostatnia aktualizacja: ${config.updated_at}` : '';
    }

    if (newsLastBuild) {
      newsLastBuild.textContent = config?.last_build_at || '—';
    }

    if (newsLastNotification) {
      newsLastNotification.textContent = config?.last_notification_at || '—';
    }
  };

  const renderNewsTestResult = (payload) => {
    if (!newsTestResult) return;
    if (!payload) {
      newsTestResult.classList.add('d-none');
      newsTestResult.innerHTML = '';
      return;
    }

    const ok = payload.success !== false;
    const statusClass = ok ? 'alert-success' : 'alert-danger';
    const details = escapeHtml(payload.details || payload.error || 'Brak szczegółów');
    const latency = payload.latency_ms ? ` • ${payload.latency_ms} ms` : '';
    const source = payload.source || 'API';
    newsTestResult.innerHTML = `
      <div class="fw-semibold mb-1">${ok ? 'Połączenie OK' : 'Błąd połączenia'}</div>
      <div class="small text-muted">Źródło: ${escapeHtml(source)}${latency}</div>
      <div class="mt-2">${details}</div>
    `;
    newsTestResult.className = `alert ${statusClass} border`;
    newsTestResult.classList.remove('d-none');
  };

  const renderFaissSnippets = (items = []) => {
    if (!newsFaissSnippets || !newsFaissSnippetsList) return;

    if (!Array.isArray(items) || !items.length) {
      newsFaissSnippets.classList.add('d-none');
      newsFaissSnippetsList.innerHTML = '';
      return;
    }

    const html = items.slice(0, 5).map((item, idx) => {
      const category = escapeHtml(item.category || `Fragment ${idx + 1}`);
      const content = escapeHtml(item.content || '').replace(/\n/g, '<br>');
      return `
        <div class="list-group-item">
          <div class="fw-semibold mb-1">${category}</div>
          <div>${content}</div>
        </div>
      `;
    }).join('');

    newsFaissSnippetsList.innerHTML = html;
    newsFaissSnippets.classList.remove('d-none');
  };

  const setFaissBackupStatus = (message, variant = 'muted') => {
    if (!newsFaissBackupStatus) return;
    const variants = {
      muted: 'text-muted',
      success: 'text-success',
      warning: 'text-warning',
      danger: 'text-danger'
    };
    Object.values(variants).forEach((cls) => newsFaissBackupStatus.classList.remove(cls));
    newsFaissBackupStatus.classList.add(variants[variant] || variants.muted);
    newsFaissBackupStatus.textContent = message;
  };

  const syncFaissBackupButtons = () => {
    const ready = Boolean(lastFaissStatus?.backup_ready);
    if (newsFaissBackupBtn) {
      newsFaissBackupBtn.disabled = isFaissBackupBusy || !ready;
      newsFaissBackupBtn.title = ready
        ? 'Pobierz aktualny backup plików FAISS'
        : 'Brakuje wymaganych plików. Odśwież status przed eksportem.';
    }
    if (newsFaissRestoreBtn) {
      newsFaissRestoreBtn.disabled = isFaissBackupBusy;
    }
    if (newsFaissRestoreInput) {
      newsFaissRestoreInput.disabled = isFaissBackupBusy;
    }
  };

  const renderFaissBackupInfo = (status = lastFaissStatus) => {
    if (!newsFaissBackupStatus) return;
    if (isFaissBackupBusy) return;

    const files = status?.backup_files;
    if (!Array.isArray(files) || !files.length) {
      setFaissBackupStatus('Backup: brak danych o plikach.', 'warning');
      return;
    }

    const total = files.length;
    const available = files.filter((file) => file.exists).length;
    const missingRequired = files.filter((file) => file.required && !file.exists);
    const missingOptional = files.filter((file) => !file.required && !file.exists);

    if (missingRequired.length) {
      const missingList = missingRequired.map((file) => file.name).join(', ');
      setFaissBackupStatus(`Backup niekompletny – brak: ${missingList}`, 'danger');
      return;
    }

    if (missingOptional.length) {
      const optionalList = missingOptional.map((file) => file.name).join(', ');
      setFaissBackupStatus(
        `Backup gotowy (${available}/${total}). Brak opcjonalnych: ${optionalList}`,
        'warning'
      );
      return;
    }

    setFaissBackupStatus(`Backup gotowy (${available}/${total}). Wszystkie pliki obecne.`, 'success');
  };

  const setFaissBackupBusy = (busy) => {
    isFaissBackupBusy = Boolean(busy);
    syncFaissBackupButtons();
    if (!isFaissBackupBusy) {
      renderFaissBackupInfo(lastFaissStatus);
    }
  };

  syncFaissBackupButtons();

  const renderFaissStatus = (status) => {
    lastFaissStatus = status || null;
    if (!newsFaissStatusPill) return;

    if (!status) {
      newsFaissStatusPill.textContent = 'Brak danych';
      newsFaissStatusPill.className = 'badge bg-secondary-subtle text-secondary-emphasis';
      newsFaissStatusMeta && (newsFaissStatusMeta.textContent = 'Ścieżka: —');
      newsFaissStatusSize && (newsFaissStatusSize.textContent = 'Rozmiar: —');
      newsFaissEmbedding && (newsFaissEmbedding.textContent = '—');
      newsFaissChat && (newsFaissChat.textContent = '—');
      newsFaissVectors && (newsFaissVectors.textContent = '0');
      newsFaissIndexPath && (newsFaissIndexPath.textContent = '—');
      newsFaissSnapshot && (newsFaissSnapshot.textContent = '—');
      renderFaissBackupInfo(null);
      syncFaissBackupButtons();
      return;
    }

    const exists = Boolean(status.exists);
    const loaded = Boolean(status.loaded);
    let badgeClass = 'badge bg-danger-subtle text-danger-emphasis';
    let label = 'Brak indeksu';

    if (loaded) {
      badgeClass = 'badge bg-success-subtle text-success-emphasis';
      label = 'Indeks gotowy';
    } else if (exists) {
      badgeClass = 'badge bg-warning-subtle text-warning-emphasis';
      label = 'Pliki do załadowania';
    }

    newsFaissStatusPill.className = badgeClass;
    newsFaissStatusPill.textContent = label;

    if (newsFaissStatusMeta) {
      newsFaissStatusMeta.textContent = status.index_path ? `Ścieżka: ${status.index_path}` : 'Ścieżka: —';
    }
    if (newsFaissStatusSize) {
      newsFaissStatusSize.textContent = `Rozmiar: ${formatBytes(status.size_bytes || 0)}`;
    }
    if (newsFaissEmbedding) {
      newsFaissEmbedding.textContent = status.embedding_model || '—';
    }
    if (newsFaissChat) {
      newsFaissChat.textContent = status.chat_model || '—';
    }
    if (newsFaissVectors) {
      newsFaissVectors.textContent = status.vector_count != null ? status.vector_count : '0';
    }
    if (newsFaissIndexPath) {
      newsFaissIndexPath.textContent = status.index_file || '—';
    }
    if (newsFaissSnapshot) {
      newsFaissSnapshot.textContent = status.docs_snapshot_exists ? 'Tak' : 'Nie';
    }
    if (newsFaissStatusUpdated) {
      const now = new Date();
      newsFaissStatusUpdated.textContent = `odświeżono ${now.toLocaleString('pl-PL')}`;
    }

    newsFaissStatusError?.classList.add('d-none');
    renderFaissBackupInfo(status);
    syncFaissBackupButtons();
  };

  const loadFaissStatus = async () => {
    if (!newsFaissStatusPill) return;
    if (!isFaissBackupBusy) {
      setFaissBackupStatus('Backup: sprawdzanie statusu...', 'muted');
    }
    try {
      const data = await fetchJSON('/api/news/faiss/status');
      if (data.success) {
        renderFaissStatus(data.status);
      } else {
        throw new Error(data.error || 'Nie udało się pobrać statusu FAISS.');
      }
    } catch (error) {
      console.error(error);
      lastFaissStatus = null;
      renderFaissBackupInfo(null);
      syncFaissBackupButtons();
      if (newsFaissStatusError) {
        newsFaissStatusError.textContent = error.message || 'Nie udało się pobrać statusu FAISS.';
        newsFaissStatusError.classList.remove('d-none');
      }
      if (!isFaissBackupBusy) {
        setFaissBackupStatus('Backup: status niedostępny. Spróbuj ponownie.', 'danger');
      }
    }
  };

  const loadNewsConfig = async () => {
    if (!newsForm) return;
    try {
      const data = await fetchJSON('/api/news/config');
      renderNewsConfig(data);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać konfiguracji News.', type: 'error' });
    }
  };

  const testNewsFAISS = async (customQuery = null) => {
    const useAllCategories = !!newsFaissAllCat?.checked;
    let querySource = typeof customQuery === 'string' ? customQuery.trim() : (newsFaissQuery?.value.trim() || '');

    if (useAllCategories) {
      querySource = querySource || ALL_CATEGORIES_PROMPT;
    } else if (!querySource) {
      showToast({ title: 'Błąd', message: 'Wpisz zapytanie testowe.', type: 'error' });
      return;
    }

    if (typeof customQuery === 'string' && newsFaissQuery) {
      newsFaissQuery.value = customQuery;
    }

    if (newsFaissTestSpinner) newsFaissTestSpinner.classList.remove('d-none');
    if (newsFaissTestBtn) newsFaissTestBtn.setAttribute('disabled', 'true');
    if (newsFaissResult) newsFaissResult.classList.add('d-none');
    renderFaissSnippets([]);

    try {
      const payload = { query: querySource };
      if (useAllCategories) {
        payload.mode = 'all_categories';
      }
      const data = await fetchJSON('/api/news/test-faiss', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      if (data.success) {
        if (newsFaissAnswer) newsFaissAnswer.textContent = data.answer || '(brak odpowiedzi)';
        if (newsFaissMeta) {
          const llmLabel = data.llm_used ? 'tak' : 'nie';
          const fragments = data.count ?? 0;
          const chatModel = data.chat_model || 'n/d';
          const modeLabel = data.mode === 'all_categories' ? 'wszystkie kategorie' : 'standard';
          newsFaissMeta.textContent = `Model: ${chatModel} • Tryb: ${modeLabel} • LLM: ${llmLabel} • Fragmenty: ${fragments}`;
        }
        renderFaissSnippets(data.results || []);
        if (newsFaissResult) newsFaissResult.classList.remove('d-none');
        showToast({ title: 'Test FAISS', message: 'Zapytanie wykonane pomyślnie.', type: 'success' });
      } else {
        showToast({ title: 'Błąd', message: data.error || 'Nie udało się wykonać zapytania.', type: 'error' });
      }
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się wykonać zapytania FAISS.', type: 'error' });
    } finally {
      if (newsFaissTestSpinner) newsFaissTestSpinner.classList.add('d-none');
      if (newsFaissTestBtn) newsFaissTestBtn.removeAttribute('disabled');
    }
  };

  const downloadFaissBackup = async (event) => {
    event?.preventDefault();
    if (!newsFaissBackupBtn || newsFaissBackupBtn.disabled) return;

    setFaissBackupBusy(true);
    setFaissBackupStatus('Backup: przygotowywanie archiwum...', 'warning');

    try {
      const response = await fetch('/api/news/faiss/export');
      if (!response.ok) {
        const message = await readErrorMessage(response, 'Nie udało się pobrać backupu.');
        throw new Error(message);
      }

      const blob = await response.blob();
      const disposition = response.headers.get('Content-Disposition');
      const fallbackName = `faiss_backup_${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
      const filename = parseContentDispositionFilename(disposition) || fallbackName;

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setFaissBackupStatus(`Backup: zapisano ${filename}`, 'success');
      showToast({ title: 'Backup FAISS', message: 'Archiwum zostało pobrane.', type: 'success' });
    } catch (error) {
      console.error(error);
      setFaissBackupStatus(`Backup: ${error.message || 'nie udało się pobrać archiwum.'}`, 'danger');
      showToast({ title: 'Backup FAISS', message: error.message || 'Nie udało się pobrać backupu.', type: 'error' });
    } finally {
      setFaissBackupBusy(false);
    }
  };

  const triggerFaissRestoreDialog = (event) => {
    event?.preventDefault();
    if (isFaissBackupBusy) return;
    newsFaissRestoreInput?.click();
  };

  const handleFaissRestoreInputChange = (event) => {
    const file = event?.target?.files?.[0];
    if (!file) return;
    uploadFaissBackup(file);
  };

  const uploadFaissBackup = async (file) => {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.zip')) {
      setFaissBackupStatus('Backup: wybierz archiwum .zip.', 'danger');
      showToast({ title: 'Backup FAISS', message: 'Obsługiwane są tylko pliki ZIP.', type: 'error' });
      if (newsFaissRestoreInput) newsFaissRestoreInput.value = '';
      return;
    }

    if (file.size > FAISS_BACKUP_MAX_BYTES) {
      const limit = formatBytes(FAISS_BACKUP_MAX_BYTES);
      setFaissBackupStatus(`Backup: plik jest zbyt duży (limit ${limit}).`, 'danger');
      showToast({ title: 'Backup FAISS', message: `Plik przekracza limit ${limit}.`, type: 'error' });
      if (newsFaissRestoreInput) newsFaissRestoreInput.value = '';
      return;
    }

    const formData = new FormData();
    formData.append('archive', file);

    let shouldRefreshStatus = false;

    setFaissBackupBusy(true);
    setFaissBackupStatus(`Backup: wgrywanie ${file.name}...`, 'warning');

    try {
      const response = await fetch('/api/news/faiss/import', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const message = await readErrorMessage(response, 'Nie udało się wczytać backupu.');
        throw new Error(message);
      }

      const payload = await response.json();
      const restored = Array.isArray(payload.restored) ? payload.restored : [];
      const restoredLabel = restored.length ? restored.join(', ') : 'brak szczegółów';

      setFaissBackupStatus(`Backup: przywrócono ${restored.length} plików.`, 'success');
      showToast({
        title: 'Backup FAISS',
        message: restored.length ? `Przywrócono: ${restoredLabel}` : 'Archiwum zostało wczytane.',
        type: 'success'
      });
      shouldRefreshStatus = true;
    } catch (error) {
      console.error(error);
      setFaissBackupStatus(`Backup: ${error.message || 'nie udało się przywrócić plików.'}`, 'danger');
      showToast({ title: 'Backup FAISS', message: error.message || 'Nie udało się wczytać archiwum.', type: 'error' });
    } finally {
      if (newsFaissRestoreInput) {
        newsFaissRestoreInput.value = '';
      }
      setFaissBackupBusy(false);
      if (shouldRefreshStatus) {
        await loadFaissStatus();
      }
    }
  };

  const addNewsRecipient = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!newsAddRecipientForm) return;

    const phone = newsRecipientPhone?.value.trim();
    const time = newsRecipientTime?.value || '08:00';
    const prompt = newsRecipientPrompt?.value.trim();
    const useAllCategories = !!newsRecipientAllCat?.checked;

    if (!phone || !prompt) {
      newsAddRecipientForm.classList.add('was-validated');
      return;
    }

    newsAddSpinner?.classList.remove('d-none');
    try {
      const data = await fetchJSON('/api/news/recipients', {
        method: 'POST',
        body: JSON.stringify({ phone, time, prompt, use_all_categories: useAllCategories })
      });
      
      renderNewsRecipients(data.recipients || []);
      newsAddRecipientForm.reset();
      if (newsRecipientPrompt) {
        delete newsRecipientPrompt.dataset.previousValue;
      }
      syncRecipientPromptMode();
      newsAddRecipientForm.classList.remove('was-validated');
      showToast({ title: 'Dodano', message: 'Odbiorca został dodany do listy powiadomień.', type: 'success' });
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się dodać odbiorcy.', type: 'error' });
    } finally {
      newsAddSpinner?.classList.add('d-none');
    }
  };

  const renderNewsRecipients = (recipients = []) => {
    if (!newsRecipientsList) return;

    newsRecipientsCount && (newsRecipientsCount.textContent = recipients.length);

    if (!recipients.length) {
      newsRecipientsList.innerHTML = '<p class="text-muted text-center py-4">Brak odbiorców</p>';
      return;
    }

    const items = recipients.map((r) => {
      const id = r.id;
      const phone = escapeHtml(r.phone || '');
      const time = escapeHtml(r.time || '08:00');
      const promptRaw = escapeHtml(r.prompt || '');
      const prompt = promptRaw.length > 60 ? `${promptRaw.substring(0, 60)}...` : promptRaw;
      const promptLine = r.use_all_categories
        ? 'Profesjonalny raport dla wszystkich kategorii'
        : prompt;
      const enabled = Boolean(r.enabled);
      const lastSent = r.last_sent_at ? new Date(r.last_sent_at).toLocaleString('pl-PL') : 'Nigdy';
      const badge = enabled
        ? '<span class="badge bg-success-subtle text-success-emphasis">Aktywny</span>'
        : '<span class="badge bg-secondary-subtle text-secondary-emphasis">Wyłączony</span>';
      const modeBadge = r.use_all_categories
        ? '<span class="badge bg-primary-subtle text-primary-emphasis ms-2">Wszystkie kategorie</span>'
        : '<span class="badge bg-info-subtle text-info-emphasis ms-2">Własny prompt</span>';
      const toggleLabel = enabled ? 'Off' : 'On';

      return `
        <div class="card mb-2 border">
          <div class="card-body p-3">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <div class="flex-grow-1">
                <strong>${phone}</strong> ${badge}${modeBadge}
                <div class="small text-muted">Godzina: ${time}</div>
                <div class="small text-muted">Ostatnio: ${lastSent}</div>
                <div class="small text-muted mt-1" title="${escapeHtml(r.prompt || '')}">${promptLine}</div>
              </div>
            </div>
            <div class="btn-group btn-group-sm" role="group">
              <button class="btn btn-outline-success" onclick="sendNewsRecipient(${id})">
                <i class="bi bi-send"></i> Wyślij
              </button>
              <button class="btn btn-outline-secondary" onclick="toggleNewsRecipient(${id})">${toggleLabel}</button>
              <button class="btn btn-outline-danger" onclick="deleteNewsRecipient(${id})">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    newsRecipientsList.innerHTML = items;
  };

  const loadNewsRecipients = async () => {
    try {
      const data = await fetchJSON('/api/news/recipients');
      renderNewsRecipients(data.recipients || []);
    } catch (error) {
      console.error(error);
    }
  };

  window.testNewsRecipient = async (id) => {
    try {
      const data = await fetchJSON(`/api/news/recipients/${id}/test`, { method: 'POST' });
      if (data.success) {
        alert(`Test (bez SMS):\n\n${data.message}`);
      } else {
        showToast({ title: 'Błąd', message: data.error, type: 'error' });
      }
    } catch (error) {
      showToast({ title: 'Błąd', message: error.message, type: 'error' });
    }
  };

  window.sendNewsRecipient = async (id) => {
    if (!confirm('Czy na pewno chcesz wysłać powiadomienie teraz?')) return;
    
    try {
      const data = await fetchJSON(`/api/news/recipients/${id}/send`, { method: 'POST' });
      if (data.success) {
        showToast({ title: 'Wysłano', message: `Powiadomienie wysłane do ${data.phone}`, type: 'success' });
        loadNewsRecipients();
      } else {
        showToast({ title: 'Błąd', message: data.error, type: 'error' });
      }
    } catch (error) {
      showToast({ title: 'Błąd', message: error.message, type: 'error' });
    }
  };

  window.toggleNewsRecipient = async (id) => {
    try {
      const data = await fetchJSON(`/api/news/recipients/${id}/toggle`, { method: 'POST' });
      if (data.success) {
        renderNewsRecipients(data.recipients || []);
        showToast({ title: 'Zaktualizowano', message: 'Status odbiorcy został zmieniony', type: 'success' });
      }
    } catch (error) {
      showToast({ title: 'Błąd', message: error.message, type: 'error' });
    }
  };

  window.deleteNewsRecipient = async (id) => {
    if (!confirm('Czy na pewno chcesz usunąć tego odbiorce?')) return;
    
    try {
      const data = await fetchJSON(`/api/news/recipients/${id}`, { method: 'DELETE' });
      if (data.success) {
        renderNewsRecipients(data.recipients || []);
        showToast({ title: 'Usunięto', message: 'Odbiorca został usunięty', type: 'success' });
      }
    } catch (error) {
      showToast({ title: 'Błąd', message: error.message, type: 'error' });
    }
  };

  const renderNewsIndices = (items = []) => {
    if (!newsIndicesTableBody) return;

    if (!items.length) {
      newsIndicesTableBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Brak danych.</td></tr>';
      newsIndicesCount && (newsIndicesCount.textContent = '0');
      return;
    }

    const rows = items.map((item) => {
      const nameRaw = item.name || '—';
      const name = escapeHtml(nameRaw);
      const nameAttr = escapeHtml(nameRaw);

      const { dateLabel, timeLabel, fullLabel } = buildDateTimeParts(item.created_at);
      const datePart = escapeHtml(dateLabel || fullLabel || '—');
      const timePart = timeLabel ? `<div class="small text-muted">${escapeHtml(timeLabel)}</div>` : '';
      const createdAt = `${datePart}${timePart ? `<br>${timePart}` : ''}`;

      const size = typeof item.size === 'number' ? `${item.size} vekt.` : escapeHtml(item.size || '—');
      const status = escapeHtml(item.status || (item.active ? 'aktywny' : 'gotowy'));
      const badge = item.active
        ? '<span class="badge bg-success-subtle text-success-emphasis">aktywna</span>'
        : '<span class="badge bg-secondary-subtle text-secondary-emphasis">dostępna</span>';
      const disabled = item.active ? 'disabled' : '';

      const deleteBtn = item.exists
        ? `<button class="btn btn-sm btn-outline-danger ms-2" data-action="news-delete-index">Usuń</button>`
        : '';

      return `
        <tr data-name="${nameAttr}">
          <td class="text-nowrap">${name}</td>
          <td class="text-nowrap">${createdAt}</td>
          <td class="text-nowrap">${size}</td>
          <td class="text-nowrap">${badge}<br><small class="text-muted">${status}</small></td>
          <td class="text-nowrap d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary" data-action="news-set-active" ${disabled}>Ustaw aktywną</button>
            ${deleteBtn}
          </td>
        </tr>
      `;
    });

    newsIndicesTableBody.innerHTML = rows.join('');
    newsIndicesCount && (newsIndicesCount.textContent = String(items.length));
  };

  const renderNewsIndicesSkeleton = () => {
    if (!newsIndicesTableBody) return;
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
    newsIndicesTableBody.innerHTML = row + row;
    newsIndicesCount && (newsIndicesCount.textContent = '—');
  };

  const showNewsIndicesError = (message) => {
    if (!newsIndicesError) return;
    newsIndicesError.textContent = message;
    newsIndicesError.classList.remove('d-none');
  };

  const clearNewsIndicesError = () => {
    if (!newsIndicesError) return;
    newsIndicesError.classList.add('d-none');
    newsIndicesError.textContent = '';
  };

  const loadNewsIndices = async () => {
    if (!newsIndicesTableBody) return;
    clearNewsIndicesError();
    renderNewsIndicesSkeleton();
    try {
      const data = await fetchJSON('/api/news/indices');
      renderNewsIndices(data.items || []);
    } catch (error) {
      console.error(error);
      renderNewsIndices([]);
      showNewsIndicesError(error.message || 'Nie udało się pobrać listy indeksów.');
    }
  };

  const setActiveNewsIndex = async (name) => {
    if (!name) return;
    try {
      await fetchJSON('/api/news/indices/active', {
        method: 'POST',
        body: JSON.stringify({ name })
      });
      showToast({ title: 'Zmieniono', message: `Aktywowano bazę: ${name}`, type: 'success' });
      await loadNewsIndices();
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się ustawić aktywnej bazy.', type: 'error' });
    }
  };

  const handleNewsIndicesAction = async (event) => {
    const actionBtn = event.target.closest('button[data-action]');
    if (!actionBtn) return;
    const row = actionBtn.closest('tr[data-name]');
    if (!row) return;
    const name = row.getAttribute('data-name');
    const action = actionBtn.dataset.action;

    if (action === 'news-set-active') {
      await setActiveNewsIndex(name);
    }

    if (action === 'news-delete-index') {
      await deleteNewsIndex(name);
    }
  };

  const deleteNewsIndex = async (name) => {
    if (!name) return;
    const ok = confirm(
      `Usunąć bazę ${name}? Ta operacja skasuje wszystkie pliki FAISS (indeks, snapshoty, articles.jsonl).`
    );
    if (!ok) return;
    try {
      const res = await fetchJSON(`/api/news/indices/${encodeURIComponent(name)}`, { method: 'DELETE' });
      if (res.success) {
        const removedCount = Array.isArray(res.removed) ? res.removed.length : 0;
        const missingCount = Array.isArray(res.missing) ? res.missing.length : 0;
        const failedCount = Array.isArray(res.failed) ? res.failed.length : 0;
        const fragments = [];
        if (removedCount) fragments.push(`usunięto ${removedCount} plików`);
        if (missingCount) fragments.push(`${missingCount} już nie było`);
        if (failedCount) fragments.push(`${failedCount} błędów`);
        const details = fragments.length ? ` (${fragments.join(', ')})` : '';
        showToast({ title: 'Usunięto', message: `Indeks ${name} został skasowany${details}.`, type: 'success' });
        if (failedCount && res.failed?.length) {
          const failedList = res.failed
            .slice(0, 3)
            .map((item) => item.path?.split(/[\\/]/).pop() || 'plik')
            .join(', ');
          showToast({
            title: 'Uwaga',
            message: `Nie udało się skasować: ${failedList}${res.failed.length > 3 ? '…' : ''}`,
            type: 'error'
          });
        }
        await loadNewsIndices();
        await loadFaissStatus();
      } else {
        showToast({ title: 'Błąd', message: res.error || 'Nie udało się usunąć indeksu.', type: 'error' });
      }
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Operacja nieudana.', type: 'error' });
    }
  };

  const renderNewsFiles = (items = []) => {
    if (!newsFilesGrid) return;

    if (!items.length) {
      newsFilesGrid.innerHTML = '<div class="col-12 text-center text-muted py-4">Brak plików. Uruchom skrapowanie, aby zobaczyć kafelki.</div>';
      return;
    }

    const cards = items.map((file) => {
      const category = escapeHtml(file.category || file.name || '—');
      const size = file.size_bytes ? `${(file.size_bytes / 1024).toFixed(1)} KB` : '—';
      const updated = file.updated_at ? new Date(file.updated_at).toLocaleString() : '—';
      const format = escapeHtml(file.format || 'txt');
      const fileName = escapeHtml(file.name || '');

      return `
        <div class="col-lg-4 col-md-6">
          <div class="card shadow-sm border-0 news-file-card position-relative" data-filename="${fileName}">
            <button class="btn btn-sm btn-outline-danger position-absolute top-0 end-0 m-2" data-action="delete-file" data-filename="${fileName}">
              <i class="bi bi-trash"></i>
            </button>
            <div class="card-body">
              <div class="d-flex justify-content-between align-items-start mb-2">
                <h6 class="mb-0 text-truncate flex-grow-1">${category}</h6>
                <span class="badge bg-primary-subtle text-primary-emphasis ms-2">${format}</span>
              </div>
              <div class="small text-muted">
                <div class="text-truncate" title="${fileName}">${fileName}</div>
                <div class="d-flex justify-content-between mt-1">
                  <span>${size}</span>
                  <span>${updated.split(',')[0]}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;
    });

    newsFilesGrid.innerHTML = cards.join('');
  };

  const loadNewsFiles = async () => {
    if (!newsFilesGrid) return;
    try {
      const data = await fetchJSON('/api/news/files');
      renderNewsFiles(data.items || []);
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać listy plików.', type: 'error' });
    }
  };

  const openNewsFileOverlay = async (filename) => {
    if (!newsFileOverlay || !filename) return;

    try {
      const data = await fetchJSON(`/api/news/files/${encodeURIComponent(filename)}`);
      if (data.error) {
        showToast({ title: 'Błąd', message: data.error, type: 'error' });
        return;
      }

      const category = filename.replace(/\.(txt|json)$/i, '').replace(/_/g, ' ');
      if (newsOverlayTitle) newsOverlayTitle.textContent = category;
      if (newsOverlayMeta) {
        const size = data.size_bytes ? `${(data.size_bytes / 1024).toFixed(1)} KB` : '—';
        const updated = data.updated_at ? new Date(data.updated_at).toLocaleString() : '—';
        newsOverlayMeta.textContent = `${size} • ${updated}`;
      }
      if (newsOverlayContent) {
        const content = escapeHtml(data.content || '(pusty plik)');
        newsOverlayContent.innerHTML = `<pre class="mb-0">${content}</pre>`;
      }

      newsFileOverlay.classList.remove('d-none');
      newsFileOverlay.classList.add('news-overlay--visible');
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się wczytać pliku.', type: 'error' });
    }
  };

  const closeNewsFileOverlay = () => {
    if (!newsFileOverlay) return;
    newsFileOverlay.classList.remove('news-overlay--visible');
    setTimeout(() => {
      newsFileOverlay.classList.add('d-none');
    }, 300);
  };

  const handleNewsFileCardClick = (event) => {
    const deleteBtn = event.target.closest('button[data-action="delete-file"]');
    if (deleteBtn) {
      const fname = deleteBtn.getAttribute('data-filename');
      if (fname) deleteNewsFile(fname);
      event.stopPropagation();
      return;
    }

    const card = event.target.closest('.news-file-card');
    if (!card) return;
    const filename = card.getAttribute('data-filename');
    if (filename) openNewsFileOverlay(filename);
  };

  const deleteNewsFile = async (filename) => {
    if (!filename) return;
    const confirmDelete = confirm(`Usunąć plik ${filename}?`);
    if (!confirmDelete) return;

    try {
      const res = await fetchJSON(`/api/news/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.success) {
        showToast({ title: 'Usunięto', message: `Plik ${filename} został usunięty.`, type: 'success' });
        await loadNewsFiles();
      } else {
        showToast({ title: 'Błąd', message: res.error || 'Nie udało się usunąć pliku.', type: 'error' });
      }
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się usunąć pliku.', type: 'error' });
    }
  };

  // Multi-SMS helpers
  const setMultiSmsSubmitting = (isSubmitting) => {
    if (!multiSmsSubmitBtn) return;
    if (isSubmitting) {
      multiSmsSubmitBtn.setAttribute('disabled', 'true');
      multiSmsSubmitSpinner?.classList.remove('d-none');
    } else {
      multiSmsSubmitBtn.removeAttribute('disabled');
      multiSmsSubmitSpinner?.classList.add('d-none');
    }
  };

  const multiSmsStatusBadge = (status) => {
    const normalized = (status || '').toLowerCase();
    const map = {
      pending: 'bg-warning-subtle text-warning-emphasis',
      processing: 'bg-info-subtle text-info-emphasis',
      completed: 'bg-success-subtle text-success-emphasis',
      completed_with_errors: 'bg-danger-subtle text-danger-emphasis',
      failed: 'bg-danger-subtle text-danger-emphasis'
    };
    const labelMap = {
      pending: 'oczekuje',
      processing: 'w trakcie',
      completed: 'zakończone',
      completed_with_errors: 'zakończone z błędami',
      failed: 'niepowodzenie'
    };
    const cls = map[normalized] || 'bg-secondary-subtle text-secondary-emphasis';
    const label = labelMap[normalized] || normalized || 'nieznany';
    return `<span class="badge ${cls}">${escapeHtml(label)}</span>`;
  };

  const renderMultiSmsRecipients = (recipients = []) => {
    if (!recipients.length) {
      return '<p class="text-muted small mb-0">Brak odbiorców.</p>';
    }

    const statusIcons = {
      sent: '✅',
      failed: '⚠️',
      invalid: '🚫',
      pending: '⏳',
      processing: '⏳'
    };

    return `
      <ul class="list-group multi-sms-recipient-list">
        ${recipients
          .map((r) => {
            const status = (r.status || '').toLowerCase();
            const icon = statusIcons[status] || '•';
            const number = escapeHtml(r.number_normalized || r.number_raw || '—');
            const err = r.error ? `<div class="small text-danger mt-1">${escapeHtml(r.error)}</div>` : '';
            const sentAt = r.sent_at ? `<div class="small text-muted">${escapeHtml(formatDateTime(r.sent_at))}</div>` : '';
            return `
              <li class="list-group-item d-flex justify-content-between align-items-start flex-wrap gap-2">
                <div class="multi-sms-recipient-main">
                  <div class="fw-semibold">${icon} ${number}</div>
                  ${sentAt}
                  ${err}
                </div>
                <span class="badge bg-light text-muted border">${escapeHtml(status || '—')}</span>
              </li>
            `;
          })
          .join('')}
      </ul>
    `;
  };

  const renderMultiSmsHistory = (items = []) => {
    if (!multiSmsHistory) return;

    if (!items.length) {
      multiSmsHistory.innerHTML = '<div class="text-center text-muted py-4">Brak wysyłek Multi-SMS.</div>';
      multiSmsBatchCount && (multiSmsBatchCount.textContent = '0');
      return;
    }

    multiSmsBatchCount && (multiSmsBatchCount.textContent = String(items.length));

    const cards = items.map((batch) => {
      const createdAt = formatDateTime(batch.created_at);
      const status = multiSmsStatusBadge(batch.status);
      const bodyPreview = escapeHtml(batch.body || '');
      const total = batch.total_recipients ?? 0;
      const sent = batch.success_count ?? 0;
      const failed = batch.failure_count ?? 0;
      const invalid = batch.invalid_count ?? 0;
      const pending = batch.pending_count ?? Math.max(total - sent - failed - invalid, 0);
      const errorLine = batch.error ? `<div class="text-danger small mt-1">${escapeHtml(batch.error)}</div>` : '';
      const recipients = Array.isArray(batch.recipients) ? batch.recipients : [];
      const batchId = batch.id;

      return `
        <div class="card border mb-3 multi-sms-card" data-batch-id="${batchId}">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start gap-2 mb-2 flex-wrap">
              <div>
                <div class="text-uppercase text-muted small mb-1">Wiadomość</div>
                <div class="fw-semibold">${bodyPreview || '<span class="text-muted">(pusta treść)</span>'}</div>
                ${errorLine}
              </div>
              <div class="text-end">
                ${status}
                <div class="small text-muted">${escapeHtml(createdAt)}</div>
                <div class="small text-muted">${escapeHtml(batch.sender_identity || '')}</div>
              </div>
            </div>
            <div class="d-flex flex-wrap gap-2 mb-2">
              <span class="badge bg-light text-muted border">Łącznie: ${total}</span>
              <span class="badge bg-success-subtle text-success-emphasis">Wysłane: ${sent}</span>
              <span class="badge bg-warning-subtle text-warning-emphasis">Oczekujące: ${pending}</span>
              <span class="badge bg-danger-subtle text-danger-emphasis">Błędy: ${failed}</span>
              <span class="badge bg-secondary-subtle text-secondary-emphasis">Niepoprawne: ${invalid}</span>
            </div>
            <button class="btn btn-sm btn-outline-primary" data-action="toggle-recipients" data-target="recipients-${batchId}">
              Odbiorcy (${recipients.length || total})
            </button>
            <div class="multi-sms-recipients collapse" id="recipients-${batchId}">
              ${renderMultiSmsRecipients(recipients)}
            </div>
          </div>
        </div>
      `;
    });

    multiSmsHistory.innerHTML = cards.join('');
  };

  const handleMultiSmsToggleClick = (event) => {
    const toggleBtn = event.target.closest('button[data-action="toggle-recipients"]');
    if (!toggleBtn) return;
    const targetId = toggleBtn.getAttribute('data-target');
    if (!targetId) return;
    const panel = document.getElementById(targetId);
    if (!panel) return;
    panel.classList.toggle('show');
  };

  const loadMultiSmsBatches = async () => {
    if (!multiSmsHistory) return;
    try {
      multiSmsHistory.innerHTML = '<div class="text-muted py-3">Ładowanie...</div>';
      const data = await fetchJSON('/api/multi-sms/batches?limit=20&include_recipients=1');
      renderMultiSmsHistory(data.items || []);
    } catch (error) {
      console.error(error);
      multiSmsHistory.innerHTML = `<div class="text-danger">${escapeHtml(error.message || 'Nie udało się pobrać historii Multi-SMS.')}</div>`;
    }
  };

  const submitMultiSms = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!multiSmsForm) return;
    if (!multiSmsForm.checkValidity()) {
      multiSmsForm.classList.add('was-validated');
      return;
    }

    const recipientsText = multiSmsRecipientsField?.value || '';
    const body = multiSmsBodyField?.value.trim() || '';

    if (!recipientsText.trim() || !body) {
      multiSmsForm.classList.add('was-validated');
      return;
    }

    setMultiSmsSubmitting(true);

    try {
      const res = await fetchJSON('/api/multi-sms/batches', {
        method: 'POST',
        body: JSON.stringify({
          recipients: recipientsText,
          body
        })
      });

      const batch = res.batch;
      const total = batch?.total_recipients ?? 0;
      const invalid = batch?.invalid_count ?? 0;
      showToast({
        title: 'Zadanie utworzone',
        message: `Multi-SMS zapisane. Odbiorców: ${total}${invalid ? `, niepoprawne: ${invalid}` : ''}.`,
        type: 'success'
      });

      multiSmsForm.reset();
      multiSmsForm.classList.remove('was-validated');
      await loadMultiSmsBatches();
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się utworzyć zadania Multi-SMS.', type: 'error' });
    } finally {
      setMultiSmsSubmitting(false);
    }
  };

  const buildNewsIndex = async () => {
    if (!newsBuildIndexBtn) return;
    if (newsBuildIndexBtn.hasAttribute('disabled')) return;

    newsBuildIndexBtn.setAttribute('disabled', 'true');
    newsBuildIndexSpinner?.classList.remove('d-none');

    try {
      const data = await fetchJSON('/api/news/indices/build', { method: 'POST' });

      if (!data.success) {
        showToast({ title: 'Błąd', message: data.error || 'Nie udało się zbudować indeksu.', type: 'error' });
        return;
      }

      showToast({ title: 'Sukces', message: data.message || 'Indeks FAISS został zbudowany.', type: 'success' });
      
      if (newsLastBuild && data.built_at) newsLastBuild.textContent = data.built_at;
      
      await loadNewsIndices();
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się zbudować indeksu.', type: 'error' });
    } finally {
      newsBuildIndexBtn.removeAttribute('disabled');
      newsBuildIndexSpinner?.classList.add('d-none');
    }
  };

  const runNewsScrape = async () => {
    if (!newsScrapeBtn) return;

    if (newsScrapeBtn.hasAttribute('disabled')) return;

    newsScrapeBtn.setAttribute('disabled', 'true');
    newsScrapeSpinner?.classList.remove('d-none');
    if (newsScrapeStatus) newsScrapeStatus.textContent = 'Pobieranie...';
    if (newsScrapeLog) {
      newsScrapeLog.classList.remove('d-none');
      newsScrapeLog.textContent = 'Rozpoczynam skrapowanie kategorii...';
    }

    try {
      const data = await fetchJSON('/api/news/scrape', { method: 'POST' });

      if (!data.success) {
        if (newsScrapeStatus) newsScrapeStatus.textContent = 'Błąd';
        if (newsScrapeLog) newsScrapeLog.textContent = data.error || 'Skrapowanie nie powiodło się.';
        showToast({ title: 'Błąd', message: data.error || 'Skrapowanie nie powiodło się.', type: 'error' });
        return;
      }

      if (newsScrapeStatus) newsScrapeStatus.textContent = 'Zakończono';
      const summary = `Pobrano ${data.items?.length || 0} kategorii. FAISS odbudowany.`;
      if (newsScrapeLog) newsScrapeLog.textContent = summary;
      showToast({ title: 'Sukces', message: summary, type: 'success' });

      if (newsLastBuild && data.completed_at) newsLastBuild.textContent = data.completed_at;

      await Promise.all([loadNewsFiles(), loadNewsIndices()]);
    } catch (error) {
      console.error(error);
      if (newsScrapeStatus) newsScrapeStatus.textContent = 'Błąd';
      if (newsScrapeLog) newsScrapeLog.textContent = error.message || 'Błąd serwera.';
      showToast({ title: 'Błąd', message: error.message || 'Skrapowanie nie powiodło się.', type: 'error' });
    } finally {
      newsScrapeBtn.removeAttribute('disabled');
      newsScrapeSpinner?.classList.add('d-none');
    }
  };

  const runNewsTest = async () => {
    if (!newsTestBtn) return;
    setNewsTesting(true);
    renderNewsTestResult(null);
    if (newsTestStatus) newsTestStatus.textContent = 'Łączenie z API...';

    try {
      const payload = {};
      const overrideTarget = newsTestTarget?.value.trim();
      if (overrideTarget) payload.target_number = overrideTarget;
      const data = await fetchJSON('/api/news/test', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      renderNewsTestResult(data);
      if (newsTestStatus) newsTestStatus.textContent = data?.success === false ? 'Błąd połączenia.' : 'Połączenie OK';
      if (newsLastTest && data?.tested_at) newsLastTest.textContent = data.tested_at;
    } catch (error) {
      console.error(error);
      renderNewsTestResult({ success: false, error: error.message || 'Błąd połączenia.' });
      if (newsTestStatus) newsTestStatus.textContent = error.message || 'Błąd połączenia.';
    } finally {
      setNewsTesting(false);
    }
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
    const skeletonRow = () => `
      <tr>
        <td colspan="7">
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
      tableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-4">Brak wiadomości do wyświetlenia.</td></tr>';
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
      const rawBody = (item.body || '').trim();
      const bodyTitle = rawBody || 'Brak treści';
      const bodyHtml = rawBody ? escapeHtml(rawBody).replace(/\n/g, '<br>') : '<span class="text-muted">Brak treści</span>';
      const rowClasses = ['messages-row'];
      if (chatUrl) {
        rowClasses.push('messages-row--clickable');
      }
      const sid = (item.sid || '').trim();
      const actionsCell = sid
        ? `<div class="messages-actions">
            <button type="button" class="btn btn-sm btn-outline-danger" data-action="delete-message" data-sid="${sid}">Usuń</button>
          </div>`
        : '<span class="text-muted small">Brak SID</span>';
      const rowAttrs = [
        `class="${rowClasses.join(' ')}"`,
        chatUrl ? `data-chat-url="${chatUrl}"` : '',
        sid ? `data-message-sid="${sid}"` : ''
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
            <div class="messages-body" title="${escapeHtml(bodyTitle)}">${bodyHtml}</div>
          </td>
          <td class="text-nowrap">
            ${statusCell}
            ${errorLine}
          </td>
          <td>${actionsCell}</td>
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

  const handleMessagesActionClick = async (event) => {
    const trigger = event.target.closest('[data-action="delete-message"]');
    if (!trigger) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const sid = trigger.dataset.sid;
    if (!sid) {
      showToast({ title: 'Błąd', message: 'Brak identyfikatora wiadomości do usunięcia.', type: 'error' });
      return;
    }

    const confirmed = window.confirm('Czy na pewno chcesz usunąć tę wiadomość? Operacja jest trwała i obejmuje również Twilio.');
    if (!confirmed) {
      return;
    }

    trigger.setAttribute('disabled', 'true');
    try {
      await fetchJSON(`/api/messages/${encodeURIComponent(sid)}`, { method: 'DELETE' });
      showToast({ title: 'Usunięto', message: 'Wiadomość została skasowana.', type: 'success' });
      await refreshMessages();
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error?.message || 'Nie udało się usunąć wiadomości.', type: 'error' });
    } finally {
      trigger.removeAttribute('disabled');
    }
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
      tableBody.addEventListener('click', handleMessagesActionClick);
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

    if (newsAddRecipientForm) {
      newsAddRecipientForm.addEventListener('submit', addNewsRecipient);
      newsRecipientAllCat?.addEventListener('change', syncRecipientPromptMode);
      newsRecipientsRefreshBtn?.addEventListener('click', loadNewsRecipients);
      newsFaissTestBtn?.addEventListener('click', () => testNewsFAISS());
      newsFaissStatusRefreshBtn?.addEventListener('click', loadFaissStatus);
      newsFaissQuickTestBtn?.addEventListener('click', () => {
        if (newsFaissAllCat) {
          newsFaissAllCat.checked = false;
          syncFaissPromptMode();
        }
        testNewsFAISS(DEFAULT_FAISS_PROMPT);
      });
      newsFaissBackupBtn?.addEventListener('click', downloadFaissBackup);
      newsFaissRestoreBtn?.addEventListener('click', triggerFaissRestoreDialog);
      newsFaissRestoreInput?.addEventListener('change', handleFaissRestoreInputChange);
      newsFaissAllCat?.addEventListener('change', syncFaissPromptMode);
      loadNewsRecipients();
      loadFaissStatus();
      syncRecipientPromptMode();
      syncFaissPromptMode();
    }

    if (newsIndicesTableBody) {
      newsIndicesTableBody.addEventListener('click', handleNewsIndicesAction);
      newsRefreshIndicesBtn?.addEventListener('click', loadNewsIndices);
      loadNewsIndices();
    }

    if (newsScrapeBtn) {
      newsScrapeBtn.addEventListener('click', runNewsScrape);
    }

    if (newsBuildIndexBtn) {
      newsBuildIndexBtn.addEventListener('click', buildNewsIndex);
    }

    if (newsFilesGrid) {
      newsFilesGrid.addEventListener('click', handleNewsFileCardClick);
      newsFilesRefreshBtn?.addEventListener('click', loadNewsFiles);
      loadNewsFiles();
    }

    if (newsOverlayCloseBtn) {
      newsOverlayCloseBtn.addEventListener('click', closeNewsFileOverlay);
    }

    if (newsFileOverlay) {
      const backdrop = newsFileOverlay.querySelector('.news-overlay__backdrop');
      if (backdrop) {
        backdrop.addEventListener('click', closeNewsFileOverlay);
      }
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
    newsTestBtn?.addEventListener('click', runNewsTest);

    if (multiSmsForm) {
      multiSmsForm.addEventListener('submit', submitMultiSms);
      multiSmsRefreshBtn?.addEventListener('click', loadMultiSmsBatches);
      multiSmsHistory?.addEventListener('click', handleMultiSmsToggleClick);
      loadMultiSmsBatches();
    }
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
