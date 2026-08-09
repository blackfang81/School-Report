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
      const message =
        data?.detail ||
        Object.values(data || {})
          .flat()
          .join(", ") ||
        "Request failed";
      throw new Error(message);
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

  post(path, body = {}) {
    return this.request(path, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};

function unwrapList(data) {
  return Array.isArray(data) ? data : data.results || [];
}

function formatDate(value) {
  return value || "-";
}

function statusBadge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

function showAlert(container, message, type = "error") {
  container.innerHTML = `<div class="alert ${type}">${message}</div>`;
}

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
      data[key] = form.querySelector('[name="is_summer"]').checked;
    } else {
      data[key] = value;
    }
  });
  return data;
}

function renderTable(container, columns, rows, actionsHtml = "") {
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
