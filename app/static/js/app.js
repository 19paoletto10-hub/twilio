'use strict';

(function () {
  const body = document.body;
  if (!body) {
    return;
  }

  const sidebar = document.querySelector('[data-app-sidebar]');
  const overlay = document.querySelector('[data-app-sidebar-overlay]');
  const toggles = document.querySelectorAll('[data-app-sidebar-toggle]');

  const STATES = {
    OPEN: 'open',
    CLOSED: 'closed'
  };

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

  setState(STATES.CLOSED);

  toggles.forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      toggleState();
    });
  });

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
})();
