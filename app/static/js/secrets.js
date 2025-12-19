'use strict';

(function () {
  const toastWrapper = document.getElementById('toast-wrapper');
  const secretsForm = document.getElementById('secrets-form');
  const secretFields = document.querySelectorAll('[data-secret-field]');
  const refreshBtn = document.getElementById('secrets-refresh-btn');

  const fetchJSON = async (url, options = {}) => {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json'
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
    if (!toastWrapper) return;
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

  const setSecretLoading = (field, isLoading) => {
    const saveBtn = field?.querySelector('[data-secret-save]');
    const spinner = saveBtn?.querySelector('.spinner-border');
    if (!saveBtn || !spinner) return;
    if (isLoading) {
      saveBtn.setAttribute('disabled', 'true');
      spinner.classList.remove('d-none');
    } else {
      saveBtn.removeAttribute('disabled');
      spinner.classList.add('d-none');
    }
  };

  const renderSecrets = (payload = {}) => {
    if (!secretFields?.length) return;
    secretFields.forEach((field) => {
      const keyName = field.dataset.secretName;
      const statusEl = field.querySelector('[data-secret-status]');
      const saveBtn = field.querySelector('[data-secret-save]');
      const testBtn = field.querySelector('[data-secret-test]');
      const persist = field.querySelector('[data-secret-persist]');

      if (!keyName) return;
      const status = payload[keyName] || {};
      const masked = status.masked || '—';
      const exists = Boolean(status.exists);

      if (statusEl) {
        statusEl.textContent = exists ? `Zapisano (${masked})` : 'Brak klucza';
        statusEl.className = exists ? 'form-text text-success' : 'form-text text-muted';
      }
      saveBtn?.removeAttribute('disabled');
      testBtn?.removeAttribute('disabled');
      persist?.removeAttribute('disabled');
    });
  };

  const handleSecretAction = async (event) => {
    const actionBtn = event.target.closest('[data-secret-save],[data-secret-test]');
    if (!actionBtn) return;
    const field = actionBtn.closest('[data-secret-field]');
    if (!field) return;

    const keyName = field.dataset.secretName;
    const input = field.querySelector('[data-secret-input]');
    const persist = field.querySelector('[data-secret-persist]');
    const statusEl = field.querySelector('[data-secret-status]');

    if (!keyName || !input) return;

    const value = input.value.trim();
    const isSave = actionBtn.hasAttribute('data-secret-save');
    const isTest = actionBtn.hasAttribute('data-secret-test');

    if (!value && isSave) {
      input.focus();
      return;
    }

    if (isSave) setSecretLoading(field, true);
    if (statusEl) statusEl.textContent = 'Przetwarzanie...';

    try {
      if (isSave) {
        const payload = {
          value,
          persist_env: !!persist?.checked,
          test: true
        };
        const res = await fetchJSON(`/api/secrets/${encodeURIComponent(keyName)}`, {
          method: 'POST',
          body: JSON.stringify(payload)
        });
        renderSecrets(res.status ? { [keyName]: res.status } : {});
        showToast({ title: 'Zapisano', message: 'Klucz został zapisany.', type: 'success' });
        if (res.test && res.test.details) {
          showToast({ title: 'Test klucza', message: res.test.details, type: 'success' });
        }
        input.value = '';
      }

      if (isTest && !isSave) {
        const res = await fetchJSON(`/api/secrets/${encodeURIComponent(keyName)}/test`, {
          method: 'POST',
          body: JSON.stringify({ value })
        });
        const details = res?.details || 'Połączenie OK';
        showToast({ title: 'Test klucza', message: details, type: 'success' });
      }
    } catch (error) {
      console.error(error);
      const msg = error?.message || 'Operacja na kluczach nie powiodła się.';
      showToast({ title: 'Błąd', message: msg, type: 'error' });
      if (statusEl) statusEl.textContent = msg;
    } finally {
      if (isSave) setSecretLoading(field, false);
    }
  };

  const loadSecrets = async () => {
    if (!secretFields?.length) return;
    try {
      const data = await fetchJSON('/api/secrets');
      renderSecrets(data || {});
      showToast({ title: 'Status', message: 'Odświeżono status kluczy.', type: 'success' });
    } catch (error) {
      console.error(error);
      showToast({ title: 'Błąd', message: error.message || 'Nie udało się pobrać kluczy.', type: 'error' });
    }
  };

  const init = () => {
    if (secretsForm && secretFields.length) {
      secretsForm.addEventListener('click', handleSecretAction);
      loadSecrets();
    }
    refreshBtn?.addEventListener('click', (event) => {
      event.preventDefault();
      loadSecrets();
    });
  };

  document.addEventListener('DOMContentLoaded', init);
})();
