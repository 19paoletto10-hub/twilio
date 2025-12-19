'use strict';

(function () {
  const root = document.getElementById('chat-root');
  if (!root) {
    return;
  }

  const participant = root.dataset.participant || '';
  const participantParam = encodeURIComponent(participant);

  const threadEl = document.getElementById('chat-thread');
  const scrollToLatestBtn = document.getElementById('chat-scroll-latest-btn');
  const totalMessagesEl = document.getElementById('chat-total-messages');
  const lastUpdatedEl = document.getElementById('chat-last-updated');
  const lastUpdatedInlineEl = document.getElementById('chat-last-updated-inline');
  const refreshBtn = document.getElementById('chat-refresh-btn');
  const refreshBtnInline = document.getElementById('chat-refresh-btn-inline');
  const deleteConversationBtn = document.getElementById('chat-delete-conversation-btn');
  const form = document.getElementById('chat-send-form');
  const messageInput = document.getElementById('chat-message-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const sendSpinner = sendBtn?.querySelector('.spinner-border');
  const clearBtn = document.getElementById('chat-clear-btn');
  const messageCounter = document.getElementById('chat-message-counter');
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

    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (error) {
        console.error('Nieprawidłowy JSON w odpowiedzi', error);
      }
    }

    if (!response.ok) {
      const errorMessage = (data && data.error) || `Błąd podczas pobierania danych (${response.status})`;
      const err = new Error(errorMessage);
      err.status = response.status;
      err.payload = data;
      throw err;
    }

    return data ?? {};
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

  const isNearBottom = () => {
    if (!threadEl) {
      return true;
    }
    const distanceFromBottom = threadEl.scrollHeight - threadEl.scrollTop - threadEl.clientHeight;
    return distanceFromBottom <= 120;
  };

  const updateScrollHint = () => {
    if (!scrollToLatestBtn || !threadEl) {
      return;
    }
    const shouldHide = isNearBottom() || threadEl.scrollHeight <= threadEl.clientHeight;
    scrollToLatestBtn.classList.toggle('is-hidden', shouldHide);
  };

  const scrollThreadToBottom = () => {
    if (!threadEl) {
      return;
    }
    threadEl.scrollTop = threadEl.scrollHeight;
    updateScrollHint();
  };

  const getStatusIcon = (status, isInbound) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('delivered') || statusLower.includes('dostarczono')) {
      return '<i class="bi bi-check2-all"></i>';
    }
    if (statusLower.includes('sent') || statusLower.includes('wysłano')) {
      return '<i class="bi bi-check2"></i>';
    }
    if (statusLower.includes('failed') || statusLower.includes('błąd')) {
      return '<i class="bi bi-exclamation-circle"></i>';
    }
    if (isInbound) {
      return '<i class="bi bi-arrow-down-left"></i>';
    }
    return '<i class="bi bi-arrow-up-right"></i>';
  };

  const renderThread = (items) => {
    if (!threadEl) {
      return;
    }

    if (!items.length) {
      threadEl.innerHTML = `
        <div class="chat-empty">
          <div class="chat-empty__icon"><i class="bi bi-chat-dots"></i></div>
          <div class="chat-empty__title">Brak wiadomości</div>
          <div class="chat-empty__desc">Ten wątek nie zawiera jeszcze żadnych wiadomości.</div>
        </div>`;
      updateScrollHint();
      return;
    }

    const shouldStickToBottom = isNearBottom();
    
    const getDateKey = (dateStr) => {
      if (!dateStr) return '';
      const iso = dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`;
      const date = new Date(iso);
      if (Number.isNaN(date.getTime())) return '';
      return date.toLocaleDateString('pl-PL', { year: 'numeric', month: 'long', day: 'numeric' });
    };
    
    const bubbles = [];
    let lastDateKey = '';
    
    for (const item of items) {
      const dateKey = getDateKey(item.created_at);
      if (dateKey && dateKey !== lastDateKey) {
        bubbles.push(`<div class="chat-date-divider">${dateKey}</div>`);
        lastDateKey = dateKey;
      }
      
      const isInbound = item.direction === 'inbound';
      const bubbleClass = isInbound ? 'chat-bubble chat-bubble--inbound' : 'chat-bubble chat-bubble--outbound';
      const authorIcon = isInbound ? '<i class="bi bi-person"></i>' : '<i class="bi bi-headset"></i>';
      const author = isInbound ? 'Klient' : 'Zespół';
      const timestamp = formatDateTime(item.created_at);
      const status = item.status ? item.status : isInbound ? 'odebrano' : 'wysłano';
      const statusIcon = getStatusIcon(status, isInbound);
      const body = escapeHtml(item.body || '');
      const errorLine = item.error 
        ? `<div class="chat-bubble__error"><i class="bi bi-exclamation-triangle-fill"></i> ${escapeHtml(item.error)}</div>` 
        : '';
      const sid = item.sid ? String(item.sid) : '';
      const deleteAction = sid
        ? `<button type="button" class="btn btn-sm ${isInbound ? 'btn-outline-danger' : 'btn-light'} chat-delete-message" data-sid="${sid}" title="Usuń wiadomość"><i class="bi bi-trash3"></i></button>`
        : '';

      bubbles.push(`
        <div class="${bubbleClass}">
          <div class="chat-bubble__meta">
            <span>${authorIcon} ${author}</span>
            <span><i class="bi bi-clock"></i> ${timestamp}</span>
          </div>
          <div class="chat-bubble__body">${body.replace(/\n/g, '<br>')}</div>
          <div class="chat-bubble__status">${statusIcon} ${status}</div>
          ${deleteAction ? `<div class="chat-bubble__actions">${deleteAction}</div>` : ''}
          ${errorLine}
        </div>
      `);
    }

    threadEl.innerHTML = bubbles.join('');
    requestAnimationFrame(() => {
      if (shouldStickToBottom) {
        scrollThreadToBottom();
      } else {
        updateScrollHint();
      }
    });
  };

  const refreshThread = async (auto = false) => {
    if (!participant) {
      return;
    }

    try {
      const data = await fetchJSON(`/api/conversations/${participantParam}`);
      renderThread(data.items || []);
      if (totalMessagesEl) {
        totalMessagesEl.textContent = data.count ?? 0;
      }
      if (lastUpdatedEl) {
        const timestamp = new Date().toLocaleString();
        lastUpdatedEl.textContent = timestamp;
        if (lastUpdatedInlineEl) {
          lastUpdatedInlineEl.textContent = timestamp;
        }
      } else if (lastUpdatedInlineEl) {
        lastUpdatedInlineEl.textContent = new Date().toLocaleString();
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

  const updateMessageCounter = () => {
    if (!messageCounter || !messageInput) {
      return;
    }
    const max = Number(messageCounter.dataset.max) || messageInput.maxLength || 1000;
    const length = messageInput.value.length;
    messageCounter.textContent = `${length} / ${max}`;
    messageCounter.classList.toggle('text-danger', max - length <= 40);
  };

  const deleteMessage = async (sid) => {
    if (!sid) {
      return;
    }
    const confirmed = window.confirm('Czy na pewno chcesz usunąć tę wiadomość? Operacja jest nieodwracalna.');
    if (!confirmed) {
      return;
    }

    try {
      await fetchJSON(`/api/messages/${encodeURIComponent(sid)}`, { method: 'DELETE' });
      showToast({ title: 'Usunięto', message: 'Wiadomość została usunięta na Twilio i lokalnie.', type: 'success' });
      await refreshThread();
    } catch (error) {
      console.error(error);
      const message = error?.message || 'Nie udało się usunąć wiadomości.';
      showToast({ title: 'Błąd', message, type: 'error' });
    }
  };

  const toggleConversationDeleteState = (pending) => {
    if (!deleteConversationBtn) {
      return;
    }
    if (pending) {
      deleteConversationBtn.setAttribute('disabled', 'true');
      deleteConversationBtn.classList.add('disabled');
    } else {
      deleteConversationBtn.removeAttribute('disabled');
      deleteConversationBtn.classList.remove('disabled');
    }
  };

  const handleConversationDelete = async () => {
    if (!participant) {
      return;
    }
    const confirmed = window.confirm('Czy na pewno chcesz usunąć cały wątek? Wszystkie wiadomości zostaną także skasowane z Twilio.');
    if (!confirmed) {
      return;
    }

    toggleConversationDeleteState(true);
    try {
      await fetchJSON(`/api/conversations/${participantParam}`, { method: 'DELETE' });
      showToast({ title: 'Usunięto', message: 'Rozmowa została wyczyszczona.', type: 'success' });
      setTimeout(() => {
        window.location.href = '/';
      }, 1200);
    } catch (error) {
      console.error(error);
      const message = error?.message || 'Nie udało się usunąć rozmowy.';
      showToast({ title: 'Błąd', message, type: 'error' });
    } finally {
      toggleConversationDeleteState(false);
    }
  };

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
      updateMessageCounter();
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

    [refreshBtn, refreshBtnInline]
      .filter(Boolean)
      .forEach((btn) => btn.addEventListener('click', () => refreshThread()));
    deleteConversationBtn?.addEventListener('click', handleConversationDelete);
    threadEl?.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      if (target.classList.contains('chat-delete-message')) {
        const sid = target.dataset.sid;
        deleteMessage(sid);
      }
    });
    threadEl?.addEventListener('scroll', () => updateScrollHint());
    form?.addEventListener('submit', handleSubmit);
    clearBtn?.addEventListener('click', () => {
      messageInput.value = '';
      form.classList.remove('was-validated');
      messageInput.focus();
      updateMessageCounter();
    });
    messageInput?.addEventListener('input', updateMessageCounter);
    scrollToLatestBtn?.addEventListener('click', () => scrollThreadToBottom());
    updateMessageCounter();
    refreshThread();
    startAutoRefresh();
  };

  const initSidebarShortcuts = () => {
    const links = document.querySelectorAll('[data-chat-scroll]');
    if (!links.length) {
      return;
    }
    links.forEach((link) => {
      link.addEventListener('click', (event) => {
        const href = link.getAttribute('href') || '';
        if (!href.startsWith('#')) {
          return;
        }
        const target = document.querySelector(href);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
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
  document.addEventListener('DOMContentLoaded', initSidebarShortcuts);
})();
