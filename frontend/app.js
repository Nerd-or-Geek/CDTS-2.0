function $(id) {
  return document.getElementById(id);
}

function setResult(el, message, kind) {
  if (!el) return;
  el.textContent = message;
  el.classList.remove("ok", "err");
  if (kind) el.classList.add(kind);
}

async function postJson(url, body, headers = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  return { res, data };
}

async function patchJson(url, body, headers = {}) {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  return { res, data };
}

async function getJson(url, headers = {}) {
  const res = await fetch(url, {
    method: "GET",
    headers,
  });
  const data = await res.json().catch(() => null);
  return { res, data };
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function canonicalStatus(s) {
  return String(s || "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");
}

function statusLabel(s) {
  const v = canonicalStatus(s);
  if (v === "in_progress") return "in progress";
  return v || "new";
}

function formatSubjectOption(s) {
  const name = escapeHtml(s.display_name || "");
  const code = s.code ? ` (${escapeHtml(s.code)})` : "";
  return `${name}${code}`;
}

async function initSubjectSelect() {
  const sel = $("subjectSelect");
  if (!sel) return;

  sel.disabled = true;
  sel.innerHTML = '<option value="" selected disabled>Loading…</option>';

  const { res, data } = await getJson("/api/subjects");
  if (!res.ok) {
    sel.innerHTML = '<option value="" selected disabled>Unable to load list</option>';
    return;
  }

  const subjects = Array.isArray(data?.subjects) ? data.subjects : [];
  if (subjects.length === 0) {
    sel.innerHTML = '<option value="" selected disabled>No subjects configured</option>';
    return;
  }

  const options = subjects
    .map((s) => {
      const id = escapeHtml(s.id);
      return `<option value="${id}">${formatSubjectOption(s)}</option>`;
    })
    .join("");

  sel.innerHTML = '<option value="" selected disabled>Select…</option>' + options;
  sel.disabled = false;
}

function initReportForm() {
  const form = $("reportForm");
  const result = $("result");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setResult(result, "Submitting…");

    const fd = new FormData(form);
    const payload = {
      subject_id: (fd.get("subject_id") || "").toString(),
      category: (fd.get("category") || "other").toString(),
      incident_date: (fd.get("incident_date") || "").toString(),
      location: (fd.get("location") || "").toString(),
      description: (fd.get("description") || "").toString(),
      evidence_url: (fd.get("evidence_url") || "").toString(),
      reporter_contact: (fd.get("reporter_contact") || "").toString(),
    };

    const { res, data } = await postJson("/api/reports", payload);

    if (!res.ok) {
      let msg = data?.error || `Request failed (${res.status})`;
      const fields = data?.details?.fields;
      if (fields && typeof fields === "object") {
        const first = Object.entries(fields)[0];
        if (first) msg = `${msg}: ${first[1]}`;
      }
      setResult(result, msg, "err");
      return;
    }

    const id = data?.report?.id || "(unknown)";
    setResult(result, `Report submitted. Reference ID: ${id}`, "ok");
    form.reset();

    const sel = $("subjectSelect");
    if (sel) sel.selectedIndex = 0;
  });
}

function initStatusChecker() {
  const idInput = $("statusId");
  const btn = $("checkStatus");
  const result = $("statusResult");
  if (!idInput || !btn || !result) return;

  async function run() {
    const id = idInput.value.trim();
    if (!id) {
      setResult(result, "Enter a report reference ID.", "err");
      return;
    }

    setResult(result, "Checking…");
    const { res, data } = await getJson(`/api/reports/${encodeURIComponent(id)}/status`);
    if (!res.ok) {
      setResult(result, data?.error || `Request failed (${res.status})`, "err");
      return;
    }

    const status = statusLabel(data?.report?.status);
    const updated = data?.report?.updated_at;
    const suffix = updated ? ` (updated ${updated})` : "";
    setResult(result, `Status: ${status}${suffix}`, "ok");
  }

  btn.addEventListener("click", run);
  idInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      run();
    }
  });
}

function renderReportCard(report, token) {
  const id = escapeHtml(report.id);
  const created = escapeHtml(report.created_at || "");
  const subjectLabel = escapeHtml(report.subject_label || report.subject || "");
  const subjectId = escapeHtml(report.subject_id || "");
  const category = escapeHtml(report.category || "");
  const status = escapeHtml(statusLabel(report.status || "new"));
  const incident = escapeHtml(report.incident_date || "");
  const location = escapeHtml(report.location || "");
  const evidence = report.evidence_url ? escapeHtml(report.evidence_url) : "";
  const notes = escapeHtml(report.internal_notes || "");

  const desc = escapeHtml(report.description || "");

  const wrap = document.createElement("div");
  wrap.className = "report";

  wrap.innerHTML = `
    <div class="meta">
      <span><strong>ID:</strong> ${id}</span>
      <span><strong>Created:</strong> ${created}</span>
      <span><strong>Status:</strong> ${status}</span>
      <span><strong>Category:</strong> ${category}</span>
      ${subjectId ? `<span><strong>Subject ID:</strong> ${subjectId}</span>` : ""}
      ${incident ? `<span><strong>Date:</strong> ${incident}</span>` : ""}
      ${location ? `<span><strong>Location:</strong> ${location}</span>` : ""}
      ${evidence ? `<span><strong>Evidence:</strong> <a href="${evidence}" target="_blank" rel="noreferrer">link</a></span>` : ""}
    </div>
    <div class="subject">${subjectLabel}</div>
    <p class="desc">${desc}</p>
    <div class="statusRow">
      <label>
        Update status
        <select data-status>
          <option value="new">new</option>
          <option value="in_progress">in progress</option>
          <option value="resolved">resolved</option>
          <option value="rejected">rejected</option>
        </select>
      </label>
      <label>
        Internal notes
        <textarea data-notes placeholder="Admin-only notes (optional)">${notes}</textarea>
      </label>
      <button class="btn" type="button" data-update>Save</button>
      <span class="result" data-msg></span>
    </div>
  `;

  const sel = wrap.querySelector("select[data-status]");
  if (sel) sel.value = canonicalStatus(report.status || "new") || "new";

  const notesEl = wrap.querySelector("textarea[data-notes]");

  const btn = wrap.querySelector("button[data-update]");
  const msg = wrap.querySelector("span[data-msg]");

  if (btn && sel && msg) {
    btn.addEventListener("click", async () => {
      setResult(msg, "Saving…");
      const next = sel.value;
      const nextNotes = notesEl ? notesEl.value : "";

      const { res, data } = await patchJson(
        `/api/reports/${encodeURIComponent(report.id)}`,
        { status: next, internal_notes: nextNotes },
        { "X-Admin-Token": token }
      );

      if (!res.ok) {
        setResult(msg, data?.error || `Failed (${res.status})`, "err");
        return;
      }

      setResult(msg, "Saved", "ok");
    });
  }

  return wrap;
}

function getAdminToken() {
  const tokenInput = $("adminToken");
  const saved = sessionStorage.getItem("adminToken") || "";

  if (tokenInput && !tokenInput.value && saved) {
    tokenInput.value = saved;
  }

  const token = (tokenInput?.value || saved || "").trim();
  if (token) sessionStorage.setItem("adminToken", token);
  return token;
}

function buildReportQueryParams() {
  const params = new URLSearchParams();
  const q = $("reportQuery")?.value?.trim() || "";
  const status = $("reportStatus")?.value || "";
  const subject_id = $("reportSubject")?.value || "";

  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (subject_id) params.set("subject_id", subject_id);
  params.set("limit", "200");
  return params;
}

async function loadReportsWithFilters(token) {
  const result = $("adminResult");
  const reportsEl = $("reports");
  if (!reportsEl) return;

  setResult(result, "Loading…");
  reportsEl.innerHTML = "";

  const params = buildReportQueryParams();
  const url = `/api/reports?${params.toString()}`;
  const { res, data } = await getJson(url, { "X-Admin-Token": token });

  if (!res.ok) {
    setResult(result, data?.error || `Request failed (${res.status})`, "err");
    return;
  }

  const reports = Array.isArray(data?.reports) ? data.reports : [];
  const total = typeof data?.total === "number" ? data.total : reports.length;
  setResult(result, `Loaded ${reports.length} of ${total} report(s).`, "ok");

  for (const r of reports) {
    reportsEl.appendChild(renderReportCard(r, token));
  }
}

function renderSubjectItem(subject, token) {
  const id = escapeHtml(subject.id);
  const name = escapeHtml(subject.display_name || "");
  const code = escapeHtml(subject.code || "");
  const active = subject.active === true;
  const created = escapeHtml(subject.created_at || "");

  const wrap = document.createElement("div");
  wrap.className = "subjectItem";

  wrap.innerHTML = `
    <div class="meta">
      <span><strong>ID:</strong> ${id}</span>
      <span><strong>Created:</strong> ${created}</span>
      <span><strong>Active:</strong> ${active ? "yes" : "no"}</span>
      ${code ? `<span><strong>Code:</strong> ${code}</span>` : ""}
    </div>
    <div class="controls">
      <div class="row">
        <label>
          Display name
          <input data-name value="${name}" minlength="2" maxlength="120" />
        </label>
        <label>
          Code
          <input data-code value="${code}" maxlength="50" />
        </label>
      </div>
      <div class="row">
        <label>
          Active
          <select data-active>
            <option value="true">active</option>
            <option value="false">inactive</option>
          </select>
        </label>
        <button class="btn" type="button" data-save>Save</button>
      </div>
      <span class="result" data-msg></span>
    </div>
  `;

  const activeSel = wrap.querySelector("select[data-active]");
  if (activeSel) activeSel.value = active ? "true" : "false";

  const btn = wrap.querySelector("button[data-save]");
  const msg = wrap.querySelector("span[data-msg]");
  const nameEl = wrap.querySelector("input[data-name]");
  const codeEl = wrap.querySelector("input[data-code]");

  if (btn && msg && nameEl && codeEl && activeSel) {
    btn.addEventListener("click", async () => {
      setResult(msg, "Saving…");

      const payload = {
        display_name: nameEl.value,
        code: codeEl.value,
        active: activeSel.value === "true",
      };

      const { res, data } = await patchJson(
        `/api/subjects/${encodeURIComponent(subject.id)}`,
        payload,
        { "X-Admin-Token": token }
      );

      if (!res.ok) {
        let err = data?.error || `Failed (${res.status})`;
        const fields = data?.details?.fields;
        if (fields && typeof fields === "object") {
          const first = Object.entries(fields)[0];
          if (first) err = `${err}: ${first[1]}`;
        }
        setResult(msg, err, "err");
        return;
      }

      setResult(msg, "Saved", "ok");
    });
  }

  return wrap;
}

async function loadSubjectsAdmin(token) {
  const subjectsEl = $("subjects");
  const subjectFilter = $("reportSubject");
  const result = $("subjectsResult");
  if (!subjectsEl) return;

  setResult(result, "Loading…");
  subjectsEl.innerHTML = "";

  const { res, data } = await getJson("/api/subjects/all", { "X-Admin-Token": token });
  if (!res.ok) {
    setResult(result, data?.error || `Request failed (${res.status})`, "err");
    return;
  }

  const subjects = Array.isArray(data?.subjects) ? data.subjects : [];
  setResult(result, `Loaded ${subjects.length} subject(s).`, "ok");

  for (const s of subjects) {
    subjectsEl.appendChild(renderSubjectItem(s, token));
  }

  if (subjectFilter) {
    const activeSubjects = subjects.filter((s) => s.active === true);
    const opts = activeSubjects
      .map((s) => `<option value="${escapeHtml(s.id)}">${formatSubjectOption(s)}</option>`)
      .join("");
    subjectFilter.innerHTML = '<option value="" selected>All</option>' + opts;
  }
}

async function exportCsv(token) {
  const result = $("adminResult");
  setResult(result, "Exporting…");

  const params = buildReportQueryParams();
  const url = `/api/reports/export.csv?${params.toString()}`;

  const res = await fetch(url, { headers: { "X-Admin-Token": token } });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    setResult(result, data?.error || `Export failed (${res.status})`, "err");
    return;
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = "reports.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();

  URL.revokeObjectURL(objectUrl);
  setResult(result, "Export downloaded.", "ok");
}

function initAdminPage() {
  const loadBtn = $("loadReports");
  const result = $("adminResult");
  const reportsEl = $("reports");
  const addSubjectForm = $("addSubjectForm");
  const loadSubjectsBtn = $("loadSubjects");
  const exportBtn = $("exportCsv");
  const queryInput = $("reportQuery");

  if (!loadBtn || !reportsEl) return;

  // Prefill saved token if present
  getAdminToken();

  loadBtn.addEventListener("click", async () => {
    const token = getAdminToken();
    if (!token) {
      setResult(result, "Enter an admin token.", "err");
      return;
    }

    await loadReportsWithFilters(token);
  });

  if (queryInput) {
    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loadBtn.click();
      }
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener("click", async () => {
      const token = getAdminToken();
      if (!token) {
        setResult(result, "Enter an admin token.", "err");
        return;
      }
      await exportCsv(token);
    });
  }

  if (loadSubjectsBtn) {
    loadSubjectsBtn.addEventListener("click", async () => {
      const token = getAdminToken();
      if (!token) {
        setResult(result, "Enter an admin token.", "err");
        return;
      }
      await loadSubjectsAdmin(token);
    });
  }

  if (addSubjectForm) {
    addSubjectForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const token = getAdminToken();
      if (!token) {
        setResult(result, "Enter an admin token.", "err");
        return;
      }

      const subjectsResult = $("subjectsResult");
      setResult(subjectsResult, "Adding…");

      const fd = new FormData(addSubjectForm);
      const payload = {
        display_name: (fd.get("display_name") || "").toString(),
        code: (fd.get("code") || "").toString(),
      };

      const { res, data } = await postJson("/api/subjects", payload, { "X-Admin-Token": token });

      if (!res.ok) {
        let err = data?.error || `Request failed (${res.status})`;
        const fields = data?.details?.fields;
        if (fields && typeof fields === "object") {
          const first = Object.entries(fields)[0];
          if (first) err = `${err}: ${first[1]}`;
        }
        setResult(subjectsResult, err, "err");
        return;
      }

      setResult(subjectsResult, "Added.", "ok");
      addSubjectForm.reset();
      await loadSubjectsAdmin(token);
      await initSubjectSelect();
    });
  }
}

initSubjectSelect();
initReportForm();
initStatusChecker();
initAdminPage();
