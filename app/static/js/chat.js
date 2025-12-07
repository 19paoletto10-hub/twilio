'use strict';

(function () {
  const root = document.getElementById('chat-root');
  if (!root) {
    return;
  }

  const participant = root.dataset.participant || '';
  const participantParam = encodeURIComponent(participant);

  const threadEl = document.getElementById('chat-thread');
  const totalMessagesEl = document.getElementById('chat-total-messages');
  const lastUpdatedEl = document.getElementById('chat-last-updated');
  const refreshBtn = document.getElementById('chat-refresh-btn');
  const form = document.getElementById('chat-send-form');
  const messageInput = document.getElementById('chat-message-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const sendSpinner = sendBtn?.querySelector('.spinner-border');
  const toastWrapper = document.getElementById('chat-toast-wrapper');

  let autoRefreshTimer = null;

  const fetchJSON = async (url, options = {}) => {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
      },
      ...options
    });

    if (!response.ok) {
      throw new Error(`Błąd podczas pobierania danych (${response.status})`);
    }

    return response.json();
  };

  const escapeHtml = (value = '') =>
    value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] || char));

  const formatDateTime = (value) => {
    if (!value) {
      return '—';
    }
    const iso = value.endsWith('Z') ? value : `${value}Z`;
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  };

  const showToast = ({ title, message, type = 'success' }) => {
    if (!toastWrapper) {
      return;
    }

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
    const toastInstance = bootstrap.Toast.getOrCreateInstance(toast, { delay: 4500 });
    toastInstance.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
  };

  const renderThread = (items) => {
    if (!threadEl) {
      return;
    }

    if (!items.length) {
      threadEl.innerHTML = '<div class="text-center text-muted py-4">Brak wiadomości w tym wątku.</div>';
      return;
    }

    const bubbles = items.map((item) => {
      const isInbound = item.direction === 'inbound';
      const bubbleClass = isInbound ? 'chat-bubble chat-bubble--inbound' : 'chat-bubble chat-bubble--outbound';
      const author = isInbound ? 'Klient' : 'Zespół';
      const timestamp = formatDateTime(item.created_at);
      const status = item.status ? item.status : isInbound ? 'odebrano' : 'wysłano';
      const body = escapeHtml(item.body || '');
      const errorLine = item.error ? `<div class="chat-bubble__error">${escapeHtml(item.error)}</div>` : '';

      return `
        <div class="${bubbleClass}">
          <div class="chat-bubble__meta">
            <span>${author}</span>
            <span>${timestamp}</span>
          </div>
          <div class="chat-bubble__body">${body.replace(/\n/g, '<br>')}</div>
          <div class="chat-bubble__status">Status: ${status}</div>
          ${errorLine}
        </div>
      `;
    });

    threadEl.innerHTML = bubbles.join('');
    requestAnimationFrame(() => {
      threadEl.scrollTop = threadEl.scrollHeight;
    });
  };

  const refreshThread = async (auto = false) => {
    if (!participant) {
      return;
    }

    try {
      const data = await fetchJSON(`/api/conversations/${participantParam}?limit=400`);
      renderThread(data.items || []);
      if (totalMessagesEl) {
        totalMessagesEl.textContent = data.count ?? 0;
      }
      if (lastUpdatedEl) {
        lastUpdatedEl.textContent = new Date().toLocaleString();
      }
    } catch (error) {
      console.error(error);
      if (!auto) {
        showToast({ title: 'Błąd', message: 'Nie udało się pobrać historii.', type: 'error' });
      }
    }
  };

  const setSendingState = (isSending) => {
    if (!sendBtn) {
      return;
    }
    if (isSending) {
      sendBtn.setAttribute('disabled', 'true');
      sendSpinner?.classList.remove('d-none');
    } else {
      sendBtn.removeAttribute('disabled');
      sendSpinner?.classList.add('d-none');
    }
  };

  const normalizeRecipient = () => participant.replace(/^whatsapp:/i, '');

  const handleSubmit = async (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (!form.checkValidity()) {
      form.classList.add('was-validated');
      return;
    }

    const to = normalizeRecipient();
    const body = messageInput.value.trim();
    if (!body) {
      form.classList.add('was-validated');
      return;
    }

    setSendingState(true);

    try {
      await fetchJSON('/api/send-message', {
        method: 'POST',
        body: JSON.stringify({ to, body })
      });
      messageInput.value = '';
      form.classList.remove('was-validated');
      showToast({ title: 'Sukces', message: 'Wiadomość wysłana.', type: 'success' });
      refreshThread();
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: 'Nie udało się wysłać wiadomości.', type: 'error' });
    } finally {
      setSendingState(false);
    }
  };

  const startAutoRefresh = () => {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
    }
    autoRefreshTimer = setInterval(() => refreshThread(true), 12000);
  };

  const init = () => {
    if (!form || !messageInput || !threadEl) {
      return;
    }

    refreshBtn?.addEventListener('click', () => refreshThread());
    form?.addEventListener('submit', handleSubmit);
    refreshThread();
    startAutoRefresh();
  };

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
      }
    } else {
      refreshThread(true);
      startAutoRefresh();
    }
  });

  document.addEventListener('DOMContentLoaded', init);
})();
