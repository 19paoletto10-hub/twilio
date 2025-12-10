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

  const renderMessages = (items) => {
    if (!items.length) {
      tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">Brak wiadomości do wyświetlenia.</td></tr>';
      return;
    }

    const rows = items.map((item) => {
      const directionCell = formatDirectionBadge(item.direction);
      const participantRaw = item.direction === 'inbound' ? item.from_number : item.to_number;
      const participantLabel = participantRaw || '—';
      const statusCell = formatStatusBadge(item.status);
      const timestamp = formatDateTime(item.created_at);
      const errorLine = item.error ? `<div class="text-danger small mt-1 text-truncate-2">${item.error}</div>` : '';
      const chatUrl = buildChatLink(participantRaw);
      const chatCell = chatUrl
        ? `<a class="btn btn-outline-primary btn-sm" href="${chatUrl}">Otwórz</a>`
        : '—';

      return `
        <tr>
          <td class="text-nowrap">${directionCell}</td>
          <td class="text-nowrap">${participantLabel}</td>
          <td>
            <div class="text-truncate-2">${item.body || ''}</div>
            ${errorLine}
          </td>
          <td class="text-nowrap">${statusCell}</td>
          <td class="text-nowrap">${chatCell}</td>
          <td class="text-nowrap">${timestamp}</td>
        </tr>
      `;
    });

    tableBody.innerHTML = rows.join('');
  };

  const refreshMessages = async () => {
    try {
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
  };

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (refreshTimer) {
        clearInterval(refreshTimer);
      }
    } else {
      refreshMessages();
      refreshStats();
      startAutoRefresh();
    }
  });

  document.addEventListener('DOMContentLoaded', init);
})();
