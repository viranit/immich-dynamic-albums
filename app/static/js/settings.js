/**
 * Settings page interactivity: test connection, reschedule, scheduler status, password toggles.
 *
 * All API calls return JSON:API 1.0 documents. Helpers below extract the
 * relevant data from the document before rendering results.
 */
document.addEventListener('DOMContentLoaded', () => {

  // ---- Conditional field visibility (auth_method -> show OIDC fields) -----
  const authSelect = document.getElementById('s_auth_method');
  if (authSelect) {
    const oidcFields = ['oidc_issuer_url', 'oidc_client_id', 'oidc_client_secret'];
    const updateOidcVisibility = () => {
      const show = ['oidc', 'both'].includes(authSelect.value);
      oidcFields.forEach(key => {
        const el = document.getElementById('s_' + key);
        if (el) el.closest('.col-md-6, .col-md-12').style.display = show ? '' : 'none';
      });
    };
    authSelect.addEventListener('change', updateOidcVisibility);
    updateOidcVisibility();
  }

  // ---- Test connection -------------------------------------------------------
  const testBtn = document.getElementById('testConnectionBtn');
  if (testBtn) {
    testBtn.addEventListener('click', async () => {
      const result = document.getElementById('testConnectionResult');
      result.textContent = '';
      testBtn.disabled = true;
      testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Testing…';
      try {
        const url = document.getElementById('s_immich_url')?.value.trim();
        const key = document.getElementById('s_immich_api_key')?.value.trim();
        const res = await fetch('/api/settings/test-connection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ immich_url: url, immich_api_key: key }),
        });
        // Response is a JSON:API document; attributes live at doc.data.attributes
        const doc = await res.json();
        const attrs = jsonapiAttrs(doc);
        result.innerHTML = (!doc.errors && attrs.ok)
          ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>' + escHtml(attrs.message) + '</span>'
          : '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>' + escHtml(jsonapiFirstError(doc) || attrs.message) + '</span>';
      } catch (e) {
        result.innerHTML = '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>Request failed</span>';
      } finally {
        testBtn.disabled = false;
        testBtn.innerHTML = '<i class="bi bi-plug me-1"></i>Test Connection';
      }
    });
  }

  // ---- Apply schedule -------------------------------------------------------
  const rescheduleBtn = document.getElementById('rescheduleBtn');
  if (rescheduleBtn) {
    rescheduleBtn.addEventListener('click', async () => {
      const result = document.getElementById('rescheduleResult');
      result.textContent = '';
      rescheduleBtn.disabled = true;
      rescheduleBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Applying…';
      try {
        const res = await fetch('/api/settings/reschedule', { method: 'POST' });
        // Successful reschedule returns a meta-only document; errors return errors array
        const doc = await res.json();
        const ok = !doc.errors;
        result.innerHTML = ok
          ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>' + escHtml(doc.meta?.message || 'Done') + '</span>'
          : '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>' + escHtml(jsonapiFirstError(doc)) + '</span>';
      } catch (e) {
        result.innerHTML = '<span class="text-danger">Request failed</span>';
      } finally {
        rescheduleBtn.disabled = false;
        rescheduleBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Apply Schedule Now';
      }
    });
  }

  // ---- Scheduler status panel -----------------------------------------------
  async function loadSchedulerStatus() {
    const el = document.getElementById('schedulerStatus');
    if (!el) return;
    try {
      const res = await fetch('/api/scheduler/status');
      // Response: { data: { type: 'scheduler-status', id: 'default', attributes: { running, jobs } } }
      const doc = await res.json();
      const attrs = jsonapiAttrs(doc);
      if (!attrs.running) {
        el.innerHTML = '<span class="text-secondary"><i class="bi bi-pause-circle me-1"></i>Scheduler not running</span>';
        return;
      }
      const jobs = attrs.jobs || [];
      if (jobs.length === 0) {
        el.innerHTML = '<span class="text-warning"><i class="bi bi-clock me-1"></i>Scheduler running, no jobs scheduled</span>';
        return;
      }
      el.innerHTML = `<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>Running — ${jobs.length} job(s)</span>
        <table class="table table-sm mt-2 small mb-0">
          <thead><tr><th>Job ID</th><th>Next Run</th></tr></thead>
          <tbody>${jobs.map(j => `<tr><td>${escHtml(j.id)}</td><td>${escHtml(j.next_run || '—')}</td></tr>`).join('')}</tbody>
        </table>`;
    } catch (_) {
      el.innerHTML = '<span class="text-secondary">Could not load scheduler status</span>';
    }
  }
  loadSchedulerStatus();

});

// ---- JSON:API document helpers ----------------------------------------------

/**
 * Extract the ``attributes`` object from a JSON:API single-resource document.
 * Returns an empty object when the document has no primary data or is an
 * errors document.
 */
function jsonapiAttrs(doc) {
  return doc?.data?.attributes || {};
}

/**
 * Return the ``detail`` of the first error in a JSON:API errors document,
 * or an empty string when there are no errors.
 */
function jsonapiFirstError(doc) {
  return doc?.errors?.[0]?.detail || '';
}

// ---- Utilities --------------------------------------------------------------

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  const eye   = document.getElementById('eye_' + inputId);
  if (!input) return;
  if (input.type === 'password') {
    input.type = 'text';
    if (eye) { eye.classList.remove('bi-eye'); eye.classList.add('bi-eye-slash'); }
  } else {
    input.type = 'password';
    if (eye) { eye.classList.remove('bi-eye-slash'); eye.classList.add('bi-eye'); }
  }
}

function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
