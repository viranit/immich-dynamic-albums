/**
 * Settings page interactivity: test connection, reschedule, scheduler status, password toggles.
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
        const data = await res.json();
        result.innerHTML = data.ok
          ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>' + escHtml(data.message) + '</span>'
          : '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>' + escHtml(data.error) + '</span>';
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
        const data = await res.json();
        result.innerHTML = data.ok
          ? '<span class="text-success"><i class="bi bi-check-circle-fill me-1"></i>' + escHtml(data.message) + '</span>'
          : '<span class="text-danger"><i class="bi bi-x-circle-fill me-1"></i>' + escHtml(data.error) + '</span>';
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
      const data = await res.json();
      if (!data.running) {
        el.innerHTML = '<span class="text-secondary"><i class="bi bi-pause-circle me-1"></i>Scheduler not running</span>';
        return;
      }
      const jobs = (data.jobs || []);
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

// ---- Utilities ---------------------------------------------------------------

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
