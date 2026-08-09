let currentUser = null;

const loginScreen = document.getElementById("login-screen");
const appScreen = document.getElementById("app-screen");
const alertBox = document.getElementById("global-alert");
const pageTitle = document.getElementById("page-title");
const pageContent = document.getElementById("page-content");
const navMenu = document.getElementById("nav-menu");
const userLabel = document.getElementById("user-label");

const pages = {
  teacher: [
    { id: "my-classes", label: "My Classes", render: renderTeacherClasses },
    { id: "my-reports", label: "My Reports", render: renderTeacherReports },
    { id: "new-report", label: "New Report", render: renderNewReport },
    { id: "my-salaries", label: "My Salaries", render: renderMySalaries },
    { id: "profile", label: "Profile", render: renderProfile },
  ],
  education_officer: [
    { id: "schools", label: "Schools", render: renderSchools },
    { id: "terms", label: "Terms", render: renderTerms },
    { id: "classes", label: "Classes", render: renderClasses },
    { id: "assignments", label: "Teacher Assignments", render: renderAssignments },
    { id: "reports", label: "Review Reports", render: renderOfficerReports },
    { id: "profile", label: "Profile", render: renderProfile },
  ],
  finance_officer: [
    { id: "base-rates", label: "Base Rates", render: renderBaseRates },
    { id: "calculate", label: "Calculate Salaries", render: renderCalculateSalaries },
    { id: "salaries", label: "Salary Records", render: renderSalaryRecords },
    { id: "profile", label: "Profile", render: renderProfile },
  ],
};

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBox);
  try {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const data = await API.login(username, password);
    API.setToken(data.access);
    await bootApp();
  } catch (error) {
    showAlert(alertBox, error.message);
  }
});

document.getElementById("logout-btn").addEventListener("click", () => {
  API.setToken("");
  currentUser = null;
  appScreen.classList.add("hidden");
  loginScreen.classList.remove("hidden");
});

async function bootApp() {
  currentUser = await API.me();
  userLabel.textContent = `${currentUser.first_name || currentUser.username} (${currentUser.role_display})`;
  buildNav();
  loginScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  openPage(getPages()[0].id);
}

function getPages() {
  if (currentUser.role === "teacher") return pages.teacher;
  if (currentUser.role === "education_officer") return pages.education_officer;
  return pages.finance_officer;
}

function buildNav() {
  navMenu.innerHTML = "";
  getPages().forEach((page) => {
    const button = document.createElement("button");
    button.textContent = page.label;
    button.onclick = () => openPage(page.id);
    navMenu.appendChild(button);
  });
}

function openPage(pageId) {
  const page = getPages().find((item) => item.id === pageId);
  if (!page) return;
  pageTitle.textContent = page.label;
  clearAlert(pageContent);
  page.render();
}

async function renderTeacherClasses() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.list("classes");
  renderTable(
    pageContent,
    [
      { key: "name", label: "Class" },
      { key: "school_name", label: "School" },
      { key: "term_name", label: "Term" },
      { key: "session_duration", label: "Duration (min)" },
      { key: "start_date", label: "Start", render: (row) => formatDate(row.start_date) },
      { key: "end_date", label: "End", render: (row) => formatDate(row.end_date) },
    ],
    unwrapList(data)
  );
}

async function renderTeacherReports() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.list("reports");
  renderTable(
    pageContent,
    [
      { key: "session_number", label: "#" },
      { key: "classroom_name", label: "Class" },
      { key: "session_date", label: "Date", render: (row) => formatDate(row.session_date) },
      { key: "status", label: "Status", render: (row) => statusBadge(row.status) },
      { key: "is_salary_eligible", label: "Salary Eligible" },
    ],
    unwrapList(data),
    (row) =>
      row.status !== "approved"
        ? `<button class="secondary" onclick="editReport(${row.id})">Edit</button>`
        : "-"
  );
}

async function renderNewReport() {
  const classes = unwrapList(await API.list("classes"));
  pageContent.innerHTML = `
    <div class="card">
      <form id="report-form">
        <label>Class</label>
        <select name="classroom" required>
          ${classes.map((item) => `<option value="${item.id}">${item.name}</option>`).join("")}
        </select>
        <label>Session Date</label>
        <input type="date" name="session_date" required>
        <label>Summary</label>
        <textarea name="summary" rows="4" required></textarea>
        <label>Present Count</label>
        <input type="number" name="present_count" min="0" required>
        <label>Absent Count</label>
        <input type="number" name="absent_count" min="0" required>
        <button type="submit">Submit Report</button>
      </form>
    </div>`;
  document.getElementById("report-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      await API.create("reports", formValues(event.target));
      showAlert(pageContent, "Report submitted.", "success");
      setTimeout(() => openPage("my-reports"), 800);
    } catch (error) {
      showAlert(pageContent, error.message);
    }
  };
}

window.editReport = async function editReport(id) {
  const report = await API.request(`/api/reports/${id}/`);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit Report #${report.session_number}</h3>
      <form id="edit-report-form">
        <label>Session Date</label>
        <input type="date" name="session_date" value="${report.session_date}" required>
        <label>Summary</label>
        <textarea name="summary" rows="4" required>${report.summary}</textarea>
        <label>Present Count</label>
        <input type="number" name="present_count" min="0" value="${report.present_count}" required>
        <label>Absent Count</label>
        <input type="number" name="absent_count" min="0" value="${report.absent_count}" required>
        <button type="submit">Save</button>
      </form>
    </div>`;
  document.getElementById("edit-report-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      await API.update("reports", id, formValues(event.target));
      showAlert(pageContent, "Report updated.", "success");
      setTimeout(() => openPage("my-reports"), 800);
    } catch (error) {
      showAlert(pageContent, error.message);
    }
  };
};

async function renderMySalaries() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.request("/api/finance/salaries/my/");
  renderTable(
    pageContent,
    [
      { key: "year", label: "Year" },
      { key: "month", label: "Month" },
      { key: "amount", label: "Amount" },
      { key: "calculated_at", label: "Calculated At", render: (row) => formatDate(row.calculated_at?.slice(0, 10)) },
    ],
    unwrapList(data)
  );
}

async function renderSchools() {
  pageContent.innerHTML = `
    <div class="card">
      <h3>Add School</h3>
      <form id="school-form" class="form-grid">
        <div><label>Name</label><input name="name" required></div>
        <div><label>Level</label><input name="level"></div>
        <div><label>Phone</label><input name="phone"></div>
        <div><label>Email</label><input name="email" type="email"></div>
        <div style="grid-column: 1 / -1"><label>Address</label><textarea name="address" rows="2"></textarea></div>
      </form>
      <button onclick="submitSchoolForm()">Create School</button>
    </div>
    <div id="school-list" style="margin-top:16px"></div>`;
  const listBox = document.getElementById("school-list");
  const data = await API.list("schools");
  renderTable(
    listBox,
    [
      { key: "name", label: "Name" },
      { key: "level", label: "Level" },
      { key: "phone", label: "Phone" },
    ],
    unwrapList(data)
  );
}

window.submitSchoolForm = async function submitSchoolForm() {
  try {
    await API.create("schools", formValues(document.getElementById("school-form")));
    openPage("schools");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderTerms() {
  pageContent.innerHTML = `
    <div class="card">
      <h3>Add Term</h3>
      <form id="term-form" class="form-grid">
        <div><label>Name</label><input name="name" required></div>
        <div><label>Start Date</label><input type="date" name="start_date" required></div>
        <div><label>End Date</label><input type="date" name="end_date" required></div>
        <div><label><input type="checkbox" name="is_summer">Summer term</label></div>
      </form>
      <button onclick="submitTermForm()">Create Term</button>
    </div>
    <div id="term-list" style="margin-top:16px"></div>`;
  const data = await API.list("terms");
  renderTable(
    document.getElementById("term-list"),
    [
      { key: "name", label: "Name" },
      { key: "start_date", label: "Start", render: (row) => formatDate(row.start_date) },
      { key: "end_date", label: "End", render: (row) => formatDate(row.end_date) },
      { key: "is_summer", label: "Summer" },
    ],
    unwrapList(data)
  );
}

window.submitTermForm = async function submitTermForm() {
  try {
    await API.create("terms", formValues(document.getElementById("term-form")));
    openPage("terms");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderClasses() {
  const schools = unwrapList(await API.list("schools"));
  const terms = unwrapList(await API.list("terms"));
  pageContent.innerHTML = `
    <div class="card">
      <h3>Add Class</h3>
      <form id="class-form" class="form-grid">
        <div><label>School</label><select name="school">${schools.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")}</select></div>
        <div><label>Term</label><select name="term">${terms.map((t) => `<option value="${t.id}">${t.name}</option>`).join("")}</select></div>
        <div><label>Name</label><input name="name" required></div>
        <div><label>Type</label><input name="class_type"></div>
        <div><label>Duration</label><select name="session_duration"><option value="60">60</option><option value="90" selected>90</option><option value="120">120</option></select></div>
        <div><label>Start Date</label><input type="date" name="start_date" required></div>
        <div><label>End Date</label><input type="date" name="end_date" required></div>
      </form>
      <button onclick="submitClassForm()">Create Class</button>
    </div>
    <div id="class-list" style="margin-top:16px"></div>`;
  const data = await API.list("classes");
  renderTable(
    document.getElementById("class-list"),
    [
      { key: "name", label: "Class" },
      { key: "school_name", label: "School" },
      { key: "term_name", label: "Term" },
      { key: "session_duration", label: "Duration" },
    ],
    unwrapList(data)
  );
}

window.submitClassForm = async function submitClassForm() {
  try {
    const body = formValues(document.getElementById("class-form"));
    body.school = Number(body.school);
    body.term = Number(body.term);
    await API.create("classes", body);
    openPage("classes");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderAssignments() {
  const classes = unwrapList(await API.list("classes"));
  const teachers = unwrapList(await API.request("/api/auth/teachers/"));
  pageContent.innerHTML = `
    <div class="card">
      <h3>Assign Teacher</h3>
      <form id="assignment-form" class="form-grid">
        <div><label>Class</label><select name="classroom">${classes.map((c) => `<option value="${c.id}">${c.name}</option>`).join("")}</select></div>
        <div><label>Teacher</label><select name="teacher">${teachers.map((t) => `<option value="${t.id}">${t.first_name} ${t.last_name} (${t.username})</option>`).join("")}</select></div>
        <div><label>Start Date</label><input type="date" name="start_date" required></div>
        <div><label>End Date</label><input type="date" name="end_date"></div>
      </form>
      <button onclick="submitAssignmentForm()">Create Assignment</button>
    </div>
    <div id="assignment-list" style="margin-top:16px"></div>`;
  const data = await API.list("teacher-assignments");
  renderTable(
    document.getElementById("assignment-list"),
    [
      { key: "classroom_name", label: "Class" },
      { key: "teacher_name", label: "Teacher" },
      { key: "start_date", label: "Start", render: (row) => formatDate(row.start_date) },
      { key: "end_date", label: "End", render: (row) => formatDate(row.end_date) },
    ],
    unwrapList(data)
  );
}

window.submitAssignmentForm = async function submitAssignmentForm() {
  try {
    const body = formValues(document.getElementById("assignment-form"));
    body.classroom = Number(body.classroom);
    body.teacher = Number(body.teacher);
    await API.create("teacher-assignments", body);
    openPage("assignments");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderOfficerReports() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.list("reports");
  renderTable(
    pageContent,
    [
      { key: "session_number", label: "#" },
      { key: "teacher_name", label: "Teacher" },
      { key: "classroom_name", label: "Class" },
      { key: "session_date", label: "Date", render: (row) => formatDate(row.session_date) },
      { key: "status", label: "Status", render: (row) => statusBadge(row.status) },
    ],
    unwrapList(data),
    (row) => `
      <button onclick="approveReport(${row.id})">Approve</button>
      <button class="danger" onclick="rejectReport(${row.id})">Reject</button>`
  );
}

window.approveReport = async function approveReport(id) {
  const note = prompt("Optional note:") || "";
  try {
    await API.post(`/api/reports/${id}/approve/`, { note });
    openPage("reports");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

window.rejectReport = async function rejectReport(id) {
  const note = prompt("Rejection reason:") || "";
  try {
    await API.post(`/api/reports/${id}/reject/`, { note });
    openPage("reports");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderBaseRates() {
  const terms = unwrapList(await API.list("terms"));
  pageContent.innerHTML = `
    <div class="card">
      <h3>Set Base Rate</h3>
      <form id="rate-form" class="form-grid">
        <div><label>Term</label><select name="term">${terms.map((t) => `<option value="${t.id}">${t.name}</option>`).join("")}</select></div>
        <div><label>Base Rate (90 min)</label><input type="number" name="base_rate" min="0" required></div>
      </form>
      <button onclick="submitRateForm()">Save Rate</button>
    </div>
    <div id="rate-list" style="margin-top:16px"></div>`;
  const data = await API.list("finance/base-rates");
  renderTable(
    document.getElementById("rate-list"),
    [
      { key: "term_name", label: "Term" },
      { key: "base_rate", label: "Base Rate" },
    ],
    unwrapList(data)
  );
}

window.submitRateForm = async function submitRateForm() {
  try {
    const body = formValues(document.getElementById("rate-form"));
    body.term = Number(body.term);
    await API.create("finance/base-rates", body);
    openPage("base-rates");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderCalculateSalaries() {
  pageContent.innerHTML = `
    <div class="card">
      <h3>Calculate Monthly Salaries</h3>
      <form id="calc-form" class="form-grid">
        <div><label>Year</label><input type="number" name="year" min="2000" max="2100" required></div>
        <div><label>Month</label><input type="number" name="month" min="1" max="12" required></div>
      </form>
      <button onclick="submitCalcForm()">Calculate</button>
      <div id="calc-result" style="margin-top:16px"></div>
    </div>`;
}

window.submitCalcForm = async function submitCalcForm() {
  try {
    const body = formValues(document.getElementById("calc-form"));
    const result = await API.post("/api/finance/salaries/calculate/", body);
    showAlert(document.getElementById("calc-result"), result.detail, "success");
    renderTable(
      document.getElementById("calc-result"),
      [
        { key: "teacher_name", label: "Teacher" },
        { key: "year", label: "Year" },
        { key: "month", label: "Month" },
        { key: "amount", label: "Amount" },
      ],
      result.records || []
    );
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

async function renderSalaryRecords() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.list("finance/salaries");
  renderTable(
    pageContent,
    [
      { key: "teacher_name", label: "Teacher" },
      { key: "year", label: "Year" },
      { key: "month", label: "Month" },
      { key: "amount", label: "Amount" },
    ],
    unwrapList(data)
  );
}

async function renderProfile() {
  const user = await API.me();
  pageContent.innerHTML = `
    <div class="card">
      <h3>Profile</h3>
      <form id="profile-form" class="form-grid">
        <div><label>First Name</label><input name="first_name" value="${user.first_name || ""}"></div>
        <div><label>Last Name</label><input name="last_name" value="${user.last_name || ""}"></div>
        <div><label>Phone</label><input name="phone" value="${user.phone || ""}"></div>
        <div><label>Emergency Phone</label><input name="emergency_phone" value="${user.emergency_phone || ""}"></div>
      </form>
      <button onclick="submitProfileForm()">Save Profile</button>
    </div>
    <div class="card" style="margin-top:16px">
      <h3>Change Password</h3>
      <form id="password-form" class="form-grid">
        <div><label>Current Password</label><input type="password" name="old_password" required></div>
        <div><label>New Password</label><input type="password" name="new_password" minlength="8" required></div>
      </form>
      <button onclick="submitPasswordForm()">Change Password</button>
    </div>`;
}

window.submitProfileForm = async function submitProfileForm() {
  try {
    await API.request("/api/auth/me/", {
      method: "PATCH",
      body: JSON.stringify(formValues(document.getElementById("profile-form"))),
    });
    showAlert(pageContent, "Profile updated.", "success");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

window.submitPasswordForm = async function submitPasswordForm() {
  try {
    await API.post("/api/auth/change-password/", formValues(document.getElementById("password-form")));
    showAlert(pageContent, "Password changed.", "success");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

if (API.token) {
  bootApp().catch(() => API.setToken(""));
}
