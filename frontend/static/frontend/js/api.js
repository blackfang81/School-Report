const API = {
  token: localStorage.getItem("access_token") || "",

  setToken(token) {
    this.token = token;
    if (token) localStorage.setItem("access_token", token);
    else localStorage.removeItem("access_token");
  },

  async request(path, options = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;

    const response = await fetch(path, { ...options, headers });
    let data = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }

    if (!response.ok) {
      throw new Error(formatApiError(data));
    }
    return data;
  },

  login(username, password) {
    return this.request("/api/auth/login/", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  me() {
    return this.request("/api/auth/me/");
  },

  list(path) {
    return this.request(`/api/${path}/`);
  },

  detail(path, id) {
    return this.request(`/api/${path}/${id}/`);
  },

  create(path, body) {
    return this.request(`/api/${path}/`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  update(path, id, body, partial = true) {
    return this.request(`/api/${path}/${id}/`, {
      method: partial ? "PATCH" : "PUT",
      body: JSON.stringify(body),
    });
  },

  remove(path, id) {
    return this.request(`/api/${path}/${id}/`, {
      method: "DELETE",
    });
  },

  post(path, body = {}) {
    return this.request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};

function formatApiError(data) {
  if (!data) return "Request failed";

  if (typeof data.error_message === "string" && data.error_message.trim()) {
    return data.error_message;
  }

  if (typeof data.detail === "string" && data.detail.trim()) {
    return data.detail;
  }

  const source = data.error_message || data;
  if (typeof source === "object" && source !== null && !Array.isArray(source)) {
    const parts = [];
    Object.entries(source).forEach(([field, messages]) => {
      const text = Array.isArray(messages) ? messages.join(" ") : String(messages);
      if (field === "non_field_errors" || field === "__all__") {
        parts.push(text);
      } else {
        parts.push(`${field}: ${text}`);
      }
    });
    if (parts.length) return parts.join(" | ");
  }

  if (Array.isArray(source)) {
    return source.join(" ");
  }

  const fallback = Object.values(data)
    .flatMap((value) => (Array.isArray(value) ? value : [value]))
    .filter((value) => typeof value === "string")
    .join(", ");
  return fallback || "Request failed";
}

function unwrapList(data) {
  return Array.isArray(data) ? data : data.results || [];
}

function formatDate(value) {
  return value || "-";
}

function formatDateTime(value) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function statusBadge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function sessionStatusBadge(status) {
  const labels = {
    upcoming: "Upcoming",
    ready: "Ready",
    pending: "Pending Review",
    rejected: "Rejected",
    approved: "Approved",
  };
  return `<span class="badge ${status === "ready" ? "pending" : status}">${labels[status] || status}</span>`;
}

function salaryEligibleBadge(value, status) {
  if (status && status !== "approved") {
    return `<span class="badge upcoming">—</span>`;
  }
  if (value === true) {
    return `<span class="badge approved" title="Approved within 48 hours">✓ 48h Eligible</span>`;
  }
  if (value === false && status === "approved") {
    return `<span class="badge rejected" title="Approved after 48-hour deadline">✗ Not Eligible</span>`;
  }
  return `<span class="badge upcoming">—</span>`;
}

function salaryEligibleLabel(value, status) {
  if (status !== "approved") {
    return "— (after approval)";
  }
  return value
    ? "Eligible — approved within 48 hours"
    : "Not eligible — approved after 48-hour deadline";
}

function showAlert(container, message, type = "error") {
  container.innerHTML = `<div class="alert ${type}">${message}</div>`;
}

function appendAlert(container, message, type = "error") {
  const existing = container.querySelector(".inline-alert");
  if (existing) existing.remove();
  const alert = document.createElement("div");
  alert.className = `alert ${type} inline-alert`;
  alert.textContent = message;
  container.prepend(alert);
}

function rejectionReasonCell(note, status) {
  if (status && status !== "rejected") {
    return `<span class="note-empty">—</span>`;
  }
  const text = (note || "").trim();
  if (!text) return `<span class="note-empty">—</span>`;
  return `<span class="note-preview" title="${escapeHtml(text)}">${escapeHtml(text)}</span>`;
}

function officerNoteCell(note) {
  return rejectionReasonCell(note, "rejected");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

let reportActionState = null;

function openReportActionModal(action, reportId) {
  const modal = document.getElementById("report-action-modal");
  const title = document.getElementById("report-action-title");
  const message = document.getElementById("report-action-message");
  const noteWrap = document.getElementById("report-action-note-wrap");
  const label = document.getElementById("report-action-label");
  const noteInput = document.getElementById("report-action-note");
  const submitBtn = document.getElementById("report-action-submit");
  const errorBox = document.getElementById("report-action-error");

  reportActionState = { action, reportId };
  errorBox.classList.add("hidden");
  errorBox.textContent = "";
  noteInput.value = "";

  if (action === "approve") {
    title.textContent = "Approve Report";
    message.textContent = "This report will be marked as approved. No note is required.";
    message.classList.remove("hidden");
    noteWrap.classList.add("hidden");
    noteInput.required = false;
    submitBtn.textContent = "Approve";
    submitBtn.className = "";
    submitBtn.focus();
  } else {
    title.textContent = "Reject Report";
    message.classList.add("hidden");
    noteWrap.classList.remove("hidden");
    label.textContent = "What needs to be fixed?";
    noteInput.placeholder =
      "مثلاً: تعداد حاضرین با واقعیت مطابقت ندارد، یا خلاصه جلسه ناقص است";
    noteInput.required = true;
    submitBtn.textContent = "Reject";
    submitBtn.className = "danger";
    noteInput.focus();
  }

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

window.closeReportActionModal = function closeReportActionModal() {
  const modal = document.getElementById("report-action-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
  reportActionState = null;
};

window.submitReportActionModal = async function submitReportActionModal() {
  if (!reportActionState) return;
  const noteInput = document.getElementById("report-action-note");
  const errorBox = document.getElementById("report-action-error");
  const note = noteInput.value.trim();
  const { action, reportId } = reportActionState;

  if (action === "reject" && !note) {
    errorBox.textContent = "Please describe what needs to be fixed.";
    errorBox.classList.remove("hidden");
    noteInput.focus();
    return;
  }

  try {
    const path = action === "approve" ? "approve" : "reject";
    const body = action === "approve" ? {} : { note };
    await API.post(`/api/reports/${reportId}/${path}/`, body);
    closeReportActionModal();
    if (typeof loadOfficerReports === "function") {
      loadOfficerReports();
    }
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("hidden");
  }
};

function clearAlert(container) {
  container.innerHTML = "";
}

function formValues(form) {
  const data = {};
  new FormData(form).forEach((value, key) => {
    if (value === "") return;
    if (key.endsWith("_count") || key === "session_duration" || key === "base_rate") {
      data[key] = Number(value);
    } else if (key === "is_summer") {
      data[key] = form.querySelector('[name="is_summer"]')?.checked || false;
    } else {
      data[key] = value;
    }
  });
  return data;
}

function renderTable(container, columns, rows, actionsHtml = null) {
  if (!rows.length) {
    container.innerHTML = "<p>No records found.</p>";
    return;
  }
  const head = columns.map((col) => `<th>${col.label}</th>`).join("") + (actionsHtml ? "<th>Actions</th>" : "");
  const body = rows
    .map((row) => {
      const cells = columns.map((col) => `<td>${col.render ? col.render(row) : row[col.key] ?? "-"}</td>`).join("");
      const actions = actionsHtml ? `<td>${actionsHtml(row)}</td>` : "";
      return `<tr>${cells}${actions}</tr>`;
    })
    .join("");
  container.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function officerActions(editHandler, resource, row) {
  return `
    <div class="actions">
      <button class="secondary" onclick="${editHandler}(${row.id})">Edit</button>
      <button class="danger" onclick="softDeleteItem('${resource}', ${row.id})">Delete</button>
    </div>`;
}

const WEEKDAY_OPTIONS = [
  ["0", "Monday"],
  ["1", "Tuesday"],
  ["2", "Wednesday"],
  ["3", "Thursday"],
  ["4", "Friday"],
  ["5", "Saturday"],
  ["6", "Sunday"],
];

function weekdayCheckboxes(selected = [], name = "weekdays") {
  const selectedSet = new Set(selected.map(String));
  return WEEKDAY_OPTIONS.map(
    ([value, label]) =>
      `<label class="weekday-option"><input type="checkbox" name="${name}" value="${value}" ${
        selectedSet.has(value) ? "checked" : ""
      }>${label}</label>`
  ).join("");
}

function readWeekdays(form, name = "weekdays") {
  return [...form.querySelectorAll(`input[name="${name}"]:checked`)].map((el) => Number(el.value));
}
