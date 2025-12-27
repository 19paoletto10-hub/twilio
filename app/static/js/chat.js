'use strict';

/**
 * Twilio Chat App - Conversation View Controller
 * @version 3.2.7
 * @description Professional chat interface with dynamic conversation switching,
 *              real-time updates, and responsive design.
 */
(function () {
  // ============================================================================
  // CONSTANTS & CONFIGURATION
  // ============================================================================
  
  /** @constant {number} Auto-refresh interval in milliseconds */
  const AUTO_REFRESH_INTERVAL = 12000;
  
  /** @constant {number} Conversation list refresh interval */
  const CONVERSATIONS_REFRESH_INTERVAL = 30000;
  
  /** @constant {number} Debounce delay for search input */
  const SEARCH_DEBOUNCE_MS = 250;
  
  /** @constant {number} Maximum conversations to load */
  const MAX_CONVERSATIONS = 100;

  // ============================================================================
  // DOM ELEMENTS
  // ============================================================================
  
  const root = document.getElementById('chat-root');
  if (!root) {
    return;
  }

  // Current conversation state
  let currentParticipant = root.dataset.participant || '';
  let currentDisplayNumber = root.dataset.displayNumber || currentParticipant;
  let currentLastActivity = root.dataset.lastActivity || '';
  
  // Thread elements
  const threadEl = document.getElementById('chat-thread');
  const scrollToLatestBtn = document.getElementById('chat-scroll-latest-btn');
  const totalMessagesEl = document.getElementById('chat-total-messages');
  const lastUpdatedEl = document.getElementById('chat-last-updated');
  const lastUpdatedInlineEl = document.getElementById('chat-last-updated-inline');
  const refreshBtn = document.getElementById('chat-refresh-btn');
  const refreshBtnInline = document.getElementById('chat-refresh-btn-inline');
  const deleteConversationBtn = document.getElementById('chat-delete-conversation-btn');
  
  // Composer elements
  const form = document.getElementById('chat-send-form');
  const messageInput = document.getElementById('chat-message-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const sendSpinner = sendBtn?.querySelector('.spinner-border');
  const clearBtn = document.getElementById('chat-clear-btn');
  const messageCounter = document.getElementById('chat-message-counter');
  const toastWrapper = document.getElementById('chat-toast-wrapper');
  
  // Header elements (for dynamic updates)
  const chatCurrentTitle = document.getElementById('chat-current-title');
  const chatCurrentSubtitle = document.getElementById('chat-current-subtitle');
  const chatSidebarTitle = document.getElementById('chat-sidebar-title');
  const chatThreadTitle = document.getElementById('chat-thread-title');
  
  // Conversation switcher elements
  const conversationsList = document.getElementById('conversations-list');
  const conversationsListMobile = document.getElementById('conversations-list-mobile');
  const conversationsSearch = document.getElementById('conversations-search');
  const conversationsSearchMobile = document.getElementById('conversations-search-mobile');
  const conversationsSearchClear = document.getElementById('conversations-search-clear');
  const conversationsRefreshBtn = document.getElementById('conversations-refresh-btn');
  const conversationsCountEl = document.getElementById('conversations-count');
  
  // New conversation modal elements
  const newConversationBtn = document.getElementById('new-conversation-btn');
  const quickNewConversationBtn = document.getElementById('quick-new-conversation-btn');
  const newConversationForm = document.getElementById('new-conversation-form');
  const newConversationNumber = document.getElementById('new-conversation-number');
  const newConversationMessage = document.getElementById('new-conversation-message');
  const newConversationCounter = document.getElementById('new-conversation-counter');
  const startConversationBtn = document.getElementById('start-conversation-btn');
  
  // State
  let autoRefreshTimer = null;
  let conversationsRefreshTimer = null;
  let searchDebounceTimer = null;
  let conversationsCache = [];
  let newConversationModal = null;

  // ============================================================================
  // UTILITIES
  // ============================================================================

  /**
   * Fetch JSON with standardized error handling
   * @param {string} url - Request URL
   * @param {RequestInit} options - Fetch options
   * @returns {Promise<Object>} Parsed JSON response
   */
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

  /**
   * Escape HTML special characters
   * @param {string} value - Raw string
   * @returns {string} Escaped string
   */
  const escapeHtml = (value = '') =>
    value.replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char] || char));

  /**
   * Format ISO datetime to localized string
   * @param {string} value - ISO datetime string
   * @returns {string} Formatted datetime
   */
  const formatDateTime = (value) => {
    if (!value) return '—';
    const iso = value.endsWith('Z') ? value : `${value}Z`;
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  };

  /**
   * Format relative time (e.g., "2 min temu")
   * @param {string} value - ISO datetime string
   * @returns {string} Relative time string
   */
  const formatRelativeTime = (value) => {
    if (!value) return '';
    const iso = value.endsWith('Z') ? value : `${value}Z`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'teraz';
    if (diffMins < 60) return `${diffMins} min`;
    if (diffHours < 24) return `${diffHours} godz.`;
    if (diffDays < 7) return `${diffDays} dni`;
    return date.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' });
  };

  /**
   * Display toast notification
   * @param {Object} options - Toast options
   * @param {string} options.title - Toast title
   * @param {string} options.message - Toast message
   * @param {string} options.type - Toast type (success|error|warning)
   */
  const showToast = ({ title, message, type = 'success' }) => {
    if (!toastWrapper) return;

    const iconMap = {
      success: 'bi-check-circle-fill text-success',
      error: 'bi-exclamation-circle-fill text-danger',
      warning: 'bi-exclamation-triangle-fill text-warning'
    };

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-light border-0 shadow toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          <i class="${iconMap[type] || iconMap.success} me-2"></i>
          <strong class="me-1">${title}</strong>
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

  // ============================================================================
  // CONVERSATION SWITCHER
  // ============================================================================

  /**
   * Load conversations list from API
   * @returns {Promise<Array>} Conversations array
   */
  const loadConversations = async () => {
    try {
      const data = await fetchJSON(`/api/conversations?limit=${MAX_CONVERSATIONS}`);
      conversationsCache = data.items || [];
      return conversationsCache;
    } catch (error) {
      console.error('Failed to load conversations:', error);
      return [];
    }
  };

  /**
   * Render conversation item HTML
   * @param {Object} conv - Conversation object
   * @param {boolean} isActive - Whether this is the current conversation
   * @returns {string} HTML string
   */
  const renderConversationItem = (conv, isActive) => {
    const participant = conv.participant || '';
    const displayNumber = participant.replace(/^whatsapp:/i, '');
    const lastMessage = conv.last_message?.body || '';
    const lastMessageTime = formatRelativeTime(conv.last_message?.created_at);
    const messageCount = conv.message_count ?? 0;
    const truncatedMessage = lastMessage.length > 50 ? lastMessage.slice(0, 50) + '...' : lastMessage;
    const direction = conv.last_message?.direction || 'outbound';
    const directionIcon = direction === 'inbound' ? 'bi-arrow-down-left' : 'bi-arrow-up-right';
    
    return `
      <div class="conversation-item ${isActive ? 'is-active' : ''}" 
           data-participant="${escapeHtml(participant)}"
           data-display="${escapeHtml(displayNumber)}"
           role="button"
           tabindex="0"
           aria-label="Rozmowa z ${escapeHtml(displayNumber)}">
        <div class="conversation-item__avatar">
          <i class="bi bi-person-fill"></i>
        </div>
        <div class="conversation-item__content">
          <div class="conversation-item__header">
            <span class="conversation-item__name">${escapeHtml(displayNumber)}</span>
            <span class="conversation-item__time">${lastMessageTime}</span>
          </div>
          <div class="conversation-item__preview">
            <i class="${directionIcon} conversation-item__direction"></i>
            <span class="conversation-item__message">${escapeHtml(truncatedMessage) || 'Brak wiadomości'}</span>
          </div>
        </div>
        <div class="conversation-item__badge">
          <span class="badge bg-secondary-subtle text-secondary-emphasis">${messageCount}</span>
        </div>
      </div>
    `;
  };

  /**
   * Render conversations list
   * @param {Array} conversations - Conversations array
   * @param {HTMLElement} container - Target container
   */
  const renderConversationsList = (conversations, container) => {
    if (!container) return;

    if (!conversations.length) {
      container.innerHTML = `
        <div class="conversation-switcher__empty">
          <i class="bi bi-chat-dots"></i>
          <span>Brak rozmów</span>
        </div>
      `;
      return;
    }

    const html = conversations
      .map((conv) => renderConversationItem(conv, conv.participant === currentParticipant))
      .join('');
    
    container.innerHTML = html;
    
    // Update count
    if (conversationsCountEl) {
      conversationsCountEl.textContent = String(conversations.length);
    }
  };

  /**
   * Filter conversations by search query
   * @param {string} query - Search query
   * @returns {Array} Filtered conversations
   */
  const filterConversations = (query) => {
    if (!query.trim()) return conversationsCache;
    
    const lowerQuery = query.toLowerCase();
    return conversationsCache.filter((conv) => {
      const participant = (conv.participant || '').toLowerCase();
      const lastMessage = (conv.last_message?.body || '').toLowerCase();
      return participant.includes(lowerQuery) || lastMessage.includes(lowerQuery);
    });
  };

  /**
   * Handle search input with debounce
   * @param {Event} event - Input event
   */
  const handleSearchInput = (event) => {
    const query = event.target.value;
    
    // Show/hide clear button
    if (conversationsSearchClear) {
      conversationsSearchClear.classList.toggle('d-none', !query);
    }
    
    // Debounce search
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      const filtered = filterConversations(query);
      renderConversationsList(filtered, conversationsList);
      renderConversationsList(filtered, conversationsListMobile);
    }, SEARCH_DEBOUNCE_MS);
  };

  /**
   * Handle conversation item click - switch to conversation
   * @param {Event} event - Click event
   */
  const handleConversationClick = async (event) => {
    const item = event.target.closest('.conversation-item');
    if (!item) return;

    const participant = item.dataset.participant;
    const displayNumber = item.dataset.display;
    
    if (!participant || participant === currentParticipant) return;

    // Find conversation in cache to get last activity
    const conv = conversationsCache.find(c => c.participant === participant);
    const lastActivity = conv?.last_message?.created_at || '';

    // Update state
    currentParticipant = participant;
    currentDisplayNumber = displayNumber;
    currentLastActivity = lastActivity;
    
    // Update URL without reload
    const newUrl = `/chat/${encodeURIComponent(participant)}`;
    window.history.pushState({ participant }, '', newUrl);
    
    // Update UI
    updateCurrentConversationUI();
    
    // Mark item as active
    document.querySelectorAll('.conversation-item').forEach((el) => {
      el.classList.toggle('is-active', el.dataset.participant === participant);
    });
    
    // Close mobile offcanvas if open
    const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById('conversationsOffcanvas'));
    if (offcanvas) offcanvas.hide();
    
    // Load new thread
    await refreshThread();
  };

  /**
   * Update UI elements to reflect current conversation
   */
  const updateCurrentConversationUI = () => {
    const display = currentDisplayNumber || currentParticipant;
    const participant = currentParticipant;
    
    // Update main header title and subtitle
    if (chatCurrentTitle) chatCurrentTitle.textContent = display || 'Nieznany numer';
    if (chatCurrentSubtitle) {
      // Show E.164 number in subtitle if different from display, else generic label
      const subtitleText = (participant && participant !== display) 
        ? participant 
        : 'Rozmowa SMS';
      chatCurrentSubtitle.textContent = subtitleText;
    }
    
    // Update sidebar title
    if (chatSidebarTitle) chatSidebarTitle.textContent = display || 'Nieznany';
    
    // Update thread header title (above message bubbles)
    if (chatThreadTitle) chatThreadTitle.textContent = display || 'Nieznany';
    
    // Update last activity timestamp in thread header
    if (lastUpdatedInlineEl) {
      lastUpdatedInlineEl.textContent = currentLastActivity ? formatDateTime(currentLastActivity) : '—';
    }
    
    // Update data attributes on root element for consistency
    if (root) {
      root.dataset.participant = participant;
      root.dataset.displayNumber = display;
    }
    
    // Update composer recipient
    updateComposerRecipient();
    
    // Update document title
    document.title = `Rozmowa z ${display || 'kontaktem'} | Twilio`;
  };

  /**
   * Refresh conversations list
   */
  const refreshConversations = async () => {
    const conversations = await loadConversations();
    const query = conversationsSearch?.value || '';
    const filtered = filterConversations(query);
    renderConversationsList(filtered, conversationsList);
    renderConversationsList(filtered, conversationsListMobile);
  };

  // ============================================================================
  // THREAD RENDERING
  // ============================================================================
  // ============================================================================
  // THREAD RENDERING
  // ============================================================================

  /**
   * Check if scroll is near bottom of thread
   * @returns {boolean}
   */
  const isNearBottom = () => {
    if (!threadEl) return true;
    const distanceFromBottom = threadEl.scrollHeight - threadEl.scrollTop - threadEl.clientHeight;
    return distanceFromBottom <= 120;
  };

  /**
   * Update scroll-to-bottom button visibility
   */
  const updateScrollHint = () => {
    if (!scrollToLatestBtn || !threadEl) return;
    const shouldHide = isNearBottom() || threadEl.scrollHeight <= threadEl.clientHeight;
    scrollToLatestBtn.classList.toggle('is-hidden', shouldHide);
  };

  /**
   * Scroll thread to bottom
   */
  const scrollThreadToBottom = () => {
    if (!threadEl) return;
    threadEl.scrollTop = threadEl.scrollHeight;
    updateScrollHint();
  };

  /**
   * Get status icon for message
   * @param {string} status - Message status
   * @param {boolean} isInbound - Whether message is inbound
   * @returns {string} HTML icon
   */
  const getStatusIcon = (status, isInbound) => {
    const statusLower = (status || '').toLowerCase();
    if (statusLower.includes('delivered') || statusLower.includes('dostarczono')) {
      return '<i class="bi bi-check2-all text-success"></i>';
    }
    if (statusLower.includes('sent') || statusLower.includes('wysłano')) {
      return '<i class="bi bi-check2"></i>';
    }
    if (statusLower.includes('failed') || statusLower.includes('błąd')) {
      return '<i class="bi bi-exclamation-circle text-danger"></i>';
    }
    if (isInbound) {
      return '<i class="bi bi-arrow-down-left"></i>';
    }
    return '<i class="bi bi-arrow-up-right"></i>';
  };

  /**
   * Get date key for grouping messages
   * @param {string} dateStr - ISO date string
   * @returns {string} Formatted date key
   */
  const getDateKey = (dateStr) => {
    if (!dateStr) return '';
    const iso = dateStr.endsWith('Z') ? dateStr : `${dateStr}Z`;
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) {
      return 'Dzisiaj';
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return 'Wczoraj';
    }
    return date.toLocaleDateString('pl-PL', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  /**
   * Render thread messages
   * @param {Array} items - Message items
   */
  const renderThread = (items) => {
    if (!threadEl) return;

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

  // ============================================================================
  // API OPERATIONS
  // ============================================================================

  /**
   * Refresh thread messages from API
   * @param {boolean} auto - Whether this is an auto-refresh
   */
  const refreshThread = async (auto = false) => {
    if (!currentParticipant) return;

    const participantParam = encodeURIComponent(currentParticipant);

    try {
      const data = await fetchJSON(`/api/conversations/${participantParam}`);
      renderThread(data.items || []);
      
      if (totalMessagesEl) {
        totalMessagesEl.textContent = String(data.count ?? 0);
      }
      
      // Update last activity from latest message in thread
      const items = data.items || [];
      if (items.length > 0) {
        // Items are sorted descending - first is newest
        const latestMessage = items[0];
        currentLastActivity = latestMessage.date_created || latestMessage.created_at || '';
      }
      
      // Update inline timestamp with actual last activity
      if (lastUpdatedInlineEl) {
        lastUpdatedInlineEl.textContent = currentLastActivity ? formatDateTime(currentLastActivity) : '—';
      }
      
      // Update sidebar timestamp if exists
      const timestamp = new Date().toLocaleString();
      if (lastUpdatedEl) lastUpdatedEl.textContent = timestamp;
      
    } catch (error) {
      console.error('Thread refresh error:', error);
      if (!auto) {
        showToast({ title: 'Błąd', message: 'Nie udało się pobrać historii.', type: 'error' });
      }
    }
  };

  /**
   * Delete single message
   * @param {string} sid - Message SID
   */
  const deleteMessage = async (sid) => {
    if (!sid) return;
    
    const confirmed = window.confirm('Czy na pewno chcesz usunąć tę wiadomość? Operacja jest nieodwracalna.');
    if (!confirmed) return;

    try {
      await fetchJSON(`/api/messages/${encodeURIComponent(sid)}`, { method: 'DELETE' });
      showToast({ title: 'Usunięto', message: 'Wiadomość została usunięta.', type: 'success' });
      await refreshThread();
      await refreshConversations();
    } catch (error) {
      console.error('Delete message error:', error);
      showToast({ title: 'Błąd', message: error?.message || 'Nie udało się usunąć wiadomości.', type: 'error' });
    }
  };

  /**
   * Delete entire conversation
   */
  const handleConversationDelete = async () => {
    if (!currentParticipant) return;
    
    const confirmed = window.confirm('Czy na pewno chcesz usunąć cały wątek? Wszystkie wiadomości zostaną skasowane.');
    if (!confirmed) return;

    const participantParam = encodeURIComponent(currentParticipant);
    
    if (deleteConversationBtn) {
      deleteConversationBtn.setAttribute('disabled', 'true');
    }

    try {
      await fetchJSON(`/api/conversations/${participantParam}`, { method: 'DELETE' });
      showToast({ title: 'Usunięto', message: 'Rozmowa została wyczyszczona.', type: 'success' });
      
      // Refresh conversations and switch to first available
      await refreshConversations();
      
      if (conversationsCache.length > 0) {
        const firstConv = conversationsCache.find((c) => c.participant !== currentParticipant) || conversationsCache[0];
        if (firstConv && firstConv.participant !== currentParticipant) {
          currentParticipant = firstConv.participant;
          currentDisplayNumber = firstConv.participant.replace(/^whatsapp:/i, '');
          const newUrl = `/chat/${encodeURIComponent(currentParticipant)}`;
          window.history.pushState({ participant: currentParticipant }, '', newUrl);
          updateCurrentConversationUI();
          await refreshThread();
        } else {
          window.location.href = '/';
        }
      } else {
        window.location.href = '/';
      }
    } catch (error) {
      console.error('Delete conversation error:', error);
      showToast({ title: 'Błąd', message: error?.message || 'Nie udało się usunąć rozmowy.', type: 'error' });
    } finally {
      if (deleteConversationBtn) {
        deleteConversationBtn.removeAttribute('disabled');
      }
    }
  };

  // ============================================================================
  // FORM HANDLING
  // ============================================================================

  /**
   * Set sending state on submit button
   * @param {boolean} isSending
   */
  const setSendingState = (isSending) => {
    if (!sendBtn) return;
    if (isSending) {
      sendBtn.setAttribute('disabled', 'true');
      sendSpinner?.classList.remove('d-none');
      updateComposerStatus('sending');
    } else {
      sendBtn.removeAttribute('disabled');
      sendSpinner?.classList.add('d-none');
      updateComposerStatus('ready');
    }
  };

  /**
   * Normalize recipient (remove whatsapp: prefix)
   * @returns {string}
   */
  const normalizeRecipient = () => currentParticipant.replace(/^whatsapp:/i, '');

  /**
   * Update message counter with enhanced styling
   */
  const updateMessageCounter = () => {
    if (!messageCounter || !messageInput) return;
    const max = Number(messageCounter.dataset.max) || messageInput.maxLength || 1000;
    const length = messageInput.value.length;
    
    // Check for new counter structure
    const currentEl = messageCounter.querySelector('.chat-composer__counter-current');
    if (currentEl) {
      currentEl.textContent = String(length);
      // Warning/danger states
      messageCounter.classList.toggle('is-warning', max - length <= 100 && max - length > 40);
      messageCounter.classList.toggle('is-danger', max - length <= 40);
    } else {
      // Legacy format
      messageCounter.textContent = `${length} / ${max}`;
      messageCounter.classList.toggle('text-danger', max - length <= 40);
    }
  };

  /**
   * Update composer status indicator
   * @param {'ready'|'sending'|'error'} status
   * @param {string} message
   */
  const updateComposerStatus = (status, message = '') => {
    const statusEl = document.getElementById('composer-status');
    if (!statusEl) return;
    
    const statusConfig = {
      ready: { icon: 'bi-circle-fill', text: message || 'Gotowy', class: '' },
      sending: { icon: 'bi-arrow-repeat', text: message || 'Wysyłanie...', class: 'is-sending' },
      error: { icon: 'bi-exclamation-circle-fill', text: message || 'Błąd', class: 'is-error' }
    };
    
    const config = statusConfig[status] || statusConfig.ready;
    statusEl.className = `chat-composer__status ${config.class}`;
    statusEl.innerHTML = `<i class="bi ${config.icon}"></i><span>${config.text}</span>`;
  };

  /**
   * Update recipient display in composer
   */
  const updateComposerRecipient = () => {
    const recipientEl = document.getElementById('composer-recipient');
    if (recipientEl) {
      recipientEl.textContent = currentDisplayNumber || currentParticipant;
    }
  };

  /**
   * Handle form submission
   * @param {Event} event
   */
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
      await refreshThread();
      await refreshConversations();
    } catch (error) {
      console.error('Send message error:', error);
      showToast({ title: 'Błąd', message: 'Nie udało się wysłać wiadomości.', type: 'error' });
      updateComposerStatus('error', 'Błąd wysyłki');
    } finally {
      setSendingState(false);
    }
  };

  /**
   * Focus on composer and scroll to it
   */
  const focusComposer = () => {
    const composer = document.getElementById('chat-send-form');
    if (composer) {
      composer.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(() => {
        messageInput?.focus();
      }, 300);
    }
  };

  /**
   * Handle keyboard shortcuts in textarea
   * @param {KeyboardEvent} event
   */
  const handleTextareaKeydown = (event) => {
    // Ctrl/Cmd + Enter to send
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      form?.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  };

  // ============================================================================
  // NEW CONVERSATION
  // ============================================================================

  /**
   * Normalize phone number to E.164 format
   * @param {string} number - Raw phone number
   * @returns {string} Normalized number
   */
  const normalizePhoneNumber = (number) => {
    if (!number) return '';
    // Remove all non-digit characters except +
    let cleaned = number.replace(/[^\d+]/g, '');
    // Ensure starts with +
    if (!cleaned.startsWith('+')) {
      // Assume Polish number if no prefix
      if (cleaned.startsWith('48')) {
        cleaned = '+' + cleaned;
      } else if (cleaned.length === 9) {
        cleaned = '+48' + cleaned;
      } else {
        cleaned = '+' + cleaned;
      }
    }
    return cleaned;
  };

  /**
   * Validate phone number format
   * @param {string} number - Phone number to validate
   * @returns {boolean} Whether the number is valid
   */
  const isValidPhoneNumber = (number) => {
    const normalized = normalizePhoneNumber(number);
    // Basic E.164 validation: + followed by 7-15 digits
    return /^\+[1-9]\d{6,14}$/.test(normalized);
  };

  /**
   * Update new conversation message counter
   */
  const updateNewConversationCounter = () => {
    if (!newConversationCounter || !newConversationMessage) return;
    const length = newConversationMessage.value.length;
    newConversationCounter.textContent = `${length} / 1000`;
  };

  /**
   * Open new conversation modal
   */
  const openNewConversationModal = () => {
    if (!newConversationModal) {
      const modalEl = document.getElementById('newConversationModal');
      if (modalEl) {
        newConversationModal = new bootstrap.Modal(modalEl);
      }
    }
    
    // Reset form
    if (newConversationForm) {
      newConversationForm.reset();
      newConversationForm.classList.remove('was-validated');
    }
    updateNewConversationCounter();
    
    newConversationModal?.show();
    
    // Focus on number input
    setTimeout(() => {
      newConversationNumber?.focus();
    }, 300);
  };

  /**
   * Start new conversation
   */
  const startNewConversation = async () => {
    if (!newConversationNumber) return;
    
    const rawNumber = newConversationNumber.value.trim();
    const normalizedNumber = normalizePhoneNumber(rawNumber);
    
    if (!isValidPhoneNumber(rawNumber)) {
      newConversationForm?.classList.add('was-validated');
      showToast({ 
        title: 'Błąd', 
        message: 'Wprowadź poprawny numer telefonu w formacie E.164', 
        type: 'error' 
      });
      return;
    }
    
    const messageBody = newConversationMessage?.value.trim() || '';
    const spinner = startConversationBtn?.querySelector('.spinner-border');
    
    // Set loading state
    if (startConversationBtn) {
      startConversationBtn.setAttribute('disabled', 'true');
      spinner?.classList.remove('d-none');
    }
    
    try {
      // If message provided, send it first
      if (messageBody) {
        await fetchJSON('/api/send-message', {
          method: 'POST',
          body: JSON.stringify({ to: normalizedNumber, body: messageBody })
        });
        showToast({ title: 'Sukces', message: 'Wiadomość wysłana do nowego kontaktu.', type: 'success' });
      }
      
      // Close modal
      newConversationModal?.hide();
      
      // Navigate to new conversation
      currentParticipant = normalizedNumber;
      currentDisplayNumber = normalizedNumber;
      
      const newUrl = `/chat/${encodeURIComponent(normalizedNumber)}`;
      window.history.pushState({ participant: normalizedNumber }, '', newUrl);
      
      updateCurrentConversationUI();
      await refreshThread();
      await refreshConversations();
      
      // Mark new conversation as active
      document.querySelectorAll('.conversation-item').forEach((el) => {
        el.classList.toggle('is-active', el.dataset.participant === normalizedNumber);
      });
      
    } catch (error) {
      console.error('Start conversation error:', error);
      showToast({ 
        title: 'Błąd', 
        message: error?.message || 'Nie udało się rozpocząć rozmowy.', 
        type: 'error' 
      });
    } finally {
      if (startConversationBtn) {
        startConversationBtn.removeAttribute('disabled');
        spinner?.classList.add('d-none');
      }
    }
  };

  // ============================================================================
  // AUTO-REFRESH & TIMERS
  // ============================================================================

  /**
   * Start auto-refresh for thread
   */
  const startAutoRefresh = () => {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    autoRefreshTimer = setInterval(() => refreshThread(true), AUTO_REFRESH_INTERVAL);
  };

  /**
   * Start auto-refresh for conversations list
   */
  const startConversationsRefresh = () => {
    if (conversationsRefreshTimer) clearInterval(conversationsRefreshTimer);
    conversationsRefreshTimer = setInterval(refreshConversations, CONVERSATIONS_REFRESH_INTERVAL);
  };

  /**
   * Stop all timers
   */
  const stopAllTimers = () => {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    if (conversationsRefreshTimer) clearInterval(conversationsRefreshTimer);
  };

  // ============================================================================
  // INITIALIZATION
  // ============================================================================

  /**
   * Initialize event listeners
   */
  const initEventListeners = () => {
    // Refresh buttons
    [refreshBtn, refreshBtnInline].filter(Boolean).forEach((btn) => {
      btn.addEventListener('click', () => refreshThread());
    });
    
    // Delete conversation
    deleteConversationBtn?.addEventListener('click', handleConversationDelete);
    
    // Thread message actions
    threadEl?.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) return;
      
      const deleteBtn = target.closest('.chat-delete-message');
      if (deleteBtn) {
        deleteMessage(deleteBtn.dataset.sid);
      }
    });
    
    // Thread scroll
    threadEl?.addEventListener('scroll', updateScrollHint);
    scrollToLatestBtn?.addEventListener('click', scrollThreadToBottom);
    
    // Form
    form?.addEventListener('submit', handleSubmit);
    clearBtn?.addEventListener('click', () => {
      messageInput.value = '';
      form.classList.remove('was-validated');
      messageInput.focus();
      updateMessageCounter();
    });
    messageInput?.addEventListener('input', updateMessageCounter);
    messageInput?.addEventListener('keydown', handleTextareaKeydown);
    
    // Navigation write message action
    const writeMessageLink = document.getElementById('nav-write-message');
    writeMessageLink?.addEventListener('click', (event) => {
      event.preventDefault();
      focusComposer();
    });
    
    // Any link with data-action="focus-composer"
    document.querySelectorAll('[data-action="focus-composer"]').forEach((link) => {
      link.addEventListener('click', (event) => {
        event.preventDefault();
        focusComposer();
      });
    });
    
    // Conversation switcher
    conversationsSearch?.addEventListener('input', handleSearchInput);
    conversationsSearchMobile?.addEventListener('input', handleSearchInput);
    
    conversationsSearchClear?.addEventListener('click', () => {
      if (conversationsSearch) conversationsSearch.value = '';
      conversationsSearchClear.classList.add('d-none');
      renderConversationsList(conversationsCache, conversationsList);
      renderConversationsList(conversationsCache, conversationsListMobile);
    });
    
    conversationsRefreshBtn?.addEventListener('click', refreshConversations);
    
    // New conversation buttons
    newConversationBtn?.addEventListener('click', openNewConversationModal);
    quickNewConversationBtn?.addEventListener('click', openNewConversationModal);
    
    // New conversation form
    newConversationMessage?.addEventListener('input', updateNewConversationCounter);
    startConversationBtn?.addEventListener('click', startNewConversation);
    
    // Enter key in new conversation number field
    newConversationNumber?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        startNewConversation();
      }
    });
    
    // Conversation item clicks
    conversationsList?.addEventListener('click', handleConversationClick);
    conversationsListMobile?.addEventListener('click', handleConversationClick);
    
    // Keyboard navigation for conversation items
    [conversationsList, conversationsListMobile].filter(Boolean).forEach((list) => {
      list.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          handleConversationClick(event);
        }
      });
    });
    
    // Browser history navigation
    window.addEventListener('popstate', async (event) => {
      if (event.state?.participant) {
        currentParticipant = event.state.participant;
        currentDisplayNumber = currentParticipant.replace(/^whatsapp:/i, '');
        updateCurrentConversationUI();
        await refreshThread();
        await refreshConversations();
      }
    });
    
    // Visibility change
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        stopAllTimers();
      } else {
        refreshThread(true);
        refreshConversations();
        startAutoRefresh();
        startConversationsRefresh();
      }
    });
  };

  /**
   * Initialize sidebar - ensure it's always visible on chat page
   */
  const initSidebar = () => {
    // Force sidebar visibility on chat page
    const sidebar = document.querySelector('[data-app-sidebar]');
    const shell = document.querySelector('[data-app-sidebar-state]');
    
    if (sidebar && shell) {
      shell.setAttribute('data-app-sidebar-state', 'open');
      // Prevent sidebar from being toggled closed on chat page
      const toggleBtns = document.querySelectorAll('[data-app-sidebar-toggle]');
      toggleBtns.forEach((btn) => {
        const originalClick = btn.onclick;
        btn.onclick = (e) => {
          // On mobile, allow toggle
          if (window.innerWidth < 992) {
            if (originalClick) originalClick.call(btn, e);
          }
          // On desktop, prevent toggle on chat page
        };
      });
    }
  };

  /**
   * Main initialization
   */
  const init = async () => {
    if (!form || !messageInput || !threadEl) return;

    initEventListeners();
    initSidebar();
    updateMessageCounter();
    updateCurrentConversationUI();
    
    // Load initial data
    await Promise.all([
      refreshThread(),
      refreshConversations()
    ]);
    
    // Start auto-refresh timers
    startAutoRefresh();
    startConversationsRefresh();
  };

  // Start application
  document.addEventListener('DOMContentLoaded', init);
})();
