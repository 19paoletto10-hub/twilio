'use strict';

(function () {
  const body = document.body;
  if (!body) {
    return;
  }

  const sidebar = document.querySelector('[data-app-sidebar]');
  const overlay = document.querySelector('[data-app-sidebar-overlay]');
  const toggles = document.querySelectorAll('[data-app-sidebar-toggle]');
  const collapseToggle = document.querySelector('[data-app-sidebar-collapse-toggle]');

  const STATES = {
    OPEN: 'open',
    CLOSED: 'closed'
  };

  const COLLAPSE = {
    TRUE: 'true',
    FALSE: 'false'
  };

  const COLLAPSE_STORAGE_KEY = 'app.sidebarCollapsed';

  const setState = (nextState) => {
    body.dataset.appSidebarState = nextState;
    if (overlay) {
      overlay.classList.toggle('is-visible', nextState === STATES.OPEN);
    }
    if (nextState === STATES.OPEN) {
      body.classList.add('overflow-hidden');
    } else {
      body.classList.remove('overflow-hidden');
    }
  };

  const toggleState = () => {
    const currentState = body.dataset.appSidebarState === STATES.OPEN ? STATES.OPEN : STATES.CLOSED;
    setState(currentState === STATES.OPEN ? STATES.CLOSED : STATES.OPEN);
  };

  const closeIfMobile = () => {
    if (window.matchMedia('(min-width: 992px)').matches) {
      setState(STATES.CLOSED);
    }
  };

  if (!sidebar || !overlay) {
    body.dataset.appSidebarState = STATES.CLOSED;
    return;
  }

  const setCollapsed = (isCollapsed) => {
    const collapsedValue = isCollapsed ? COLLAPSE.TRUE : COLLAPSE.FALSE;
    body.dataset.appSidebarCollapsed = collapsedValue;
    if (collapseToggle) {
      collapseToggle.setAttribute('aria-pressed', String(isCollapsed));
      collapseToggle.setAttribute('aria-expanded', String(!isCollapsed));
      const label = isCollapsed ? 'Rozwiń panel nawigacji' : 'Zwiń panel nawigacji';
      collapseToggle.setAttribute('aria-label', label);
      collapseToggle.setAttribute('title', label);
    }
  };

  const toggleCollapsed = () => {
    const nextValue = body.dataset.appSidebarCollapsed === COLLAPSE.TRUE ? COLLAPSE.FALSE : COLLAPSE.TRUE;
    const isCollapsed = nextValue === COLLAPSE.TRUE;
    setCollapsed(isCollapsed);
    try {
      window.localStorage.setItem(COLLAPSE_STORAGE_KEY, nextValue);
    } catch (error) {
      // ignore storage failures (private mode, etc.)
    }
  };

  const restoreCollapsePreference = () => {
    try {
      const storedValue = window.localStorage.getItem(COLLAPSE_STORAGE_KEY);
      if (storedValue === COLLAPSE.TRUE || storedValue === COLLAPSE.FALSE) {
        setCollapsed(storedValue === COLLAPSE.TRUE);
        return;
      }
    } catch (error) {
      // ignore storage failures
    }
    setCollapsed(false);
  };

  setState(STATES.CLOSED);
  restoreCollapsePreference();

  toggles.forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      toggleState();
    });
  });

  if (collapseToggle) {
    collapseToggle.addEventListener('click', (event) => {
      event.preventDefault();
      toggleCollapsed();
    });
  }

  overlay.addEventListener('click', () => setState(STATES.CLOSED));

  window.addEventListener('keyup', (event) => {
    if (event.key === 'Escape') {
      setState(STATES.CLOSED);
    }
  });

  const navLinks = sidebar.querySelectorAll('a, button');
  navLinks.forEach((element) => {
    element.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 991px)').matches) {
        setState(STATES.CLOSED);
      }
    });
  });

  const mq = window.matchMedia('(min-width: 992px)');
  mq.addEventListener('change', closeIfMobile);

  mq.addEventListener('change', (event) => {
    if (event.matches) {
      restoreCollapsePreference();
    } else {
      setCollapsed(false);
    }
  });
})();
