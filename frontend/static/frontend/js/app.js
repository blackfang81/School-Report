let currentUser = null;
let currentPageId = null;

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
    { id: "new-report", label: "Write Report", render: renderNewReport },
    { id: "my-salaries", label: "My Salaries", render: renderMySalaries },
    { id: "profile", label: "Profile", render: renderProfile },
  ],
  education_officer: [
    { id: "schools", label: "Schools", render: renderSchools },
    { id: "terms", label: "Terms", render: renderTerms },
    { id: "classes", label: "Classes", render: renderClasses },
    { id: "assignments", label: "Teacher Assignments", render: renderAssignments },
    { id: "reports", label: "Review Reports", render: renderOfficerReports },
    { id: "timeline", label: "Timeline (Test Clock)", render: renderTimeline },
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
  await refreshClockBanner();
  loginScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  openPage(getPages()[0].id);
}

async function refreshClockBanner() {
  const banner = document.getElementById("clock-banner");
  if (!banner) return;
  if (currentUser?.role !== "education_officer") {
    banner.classList.add("hidden");
    return;
  }
  try {
    const clock = await API.request("/api/dev/clock/");
    banner.classList.remove("hidden");
    banner.textContent = clock.is_overridden
      ? `Test time: ${formatDateTime(clock.project_now)}`
      : `Live time: ${formatDateTime(clock.project_now)}`;
  } catch {
    banner.classList.add("hidden");
  }
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
  currentPageId = pageId;
  const page = getPages().find((item) => item.id === pageId);
  if (!page) return;
  pageTitle.textContent = page.label;
  clearAlert(pageContent);
  page.render();
}

window.softDeleteItem = async function softDeleteItem(resource, id) {
  if (!confirm("Soft delete this record?")) return;
  try {
    await API.remove(resource, id);
    showAlert(pageContent, "Record deleted.", "success");
    openPage(currentPageId);
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

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
      {
        key: "is_salary_eligible",
        label: "48h Salary",
        render: (row) => salaryEligibleBadge(row.is_salary_eligible, row.status),
      },
      {
        key: "officer_note",
        label: "Rejection Reason",
        render: (row) => rejectionReasonCell(row.officer_note, row.status),
      },
    ],
    unwrapList(data),
    (row) =>
      row.status !== "approved"
        ? `<button class="secondary" onclick="editReport(${row.id})">Edit</button>`
        : "-"
  );
}

async function renderNewReport() {
  pageContent.innerHTML = "<p>Loading sessions...</p>";
  try {
    const sessions = unwrapList(await API.request("/api/reports/my-sessions/"));

    if (!sessions.length) {
      pageContent.innerHTML = `
        <div class="card">
          <div class="alert error">
            هیچ جلسه‌ای یافت نشد. مسئول آموزش باید:
            <ol style="margin:8px 0 0 20px">
              <li>کلاس را با روزهای هفتگی (Weekly Sessions) بسازد</li>
              <li>شما را به آن کلاس assign کند</li>
            </ol>
          </div>
        </div>`;
      return;
    }

    const readyCount = sessions.filter((item) => item.can_submit).length;
    const editCount = sessions.filter((item) => item.can_edit).length;
    const nextReady = sessions.find((item) => item.session_status === "upcoming");

    let banner = "";
    if (readyCount === 0 && editCount === 0) {
      banner = `
        <div class="alert pending">
          هنوز جلسه‌ای برای گزارش‌نویسی آماده نیست — فقط بعد از تاریخ برگزاری جلسه می‌توانید گزارش بنویسید.
          ${
            nextReady
              ? `اولین جلسه: <strong>${formatDate(nextReady.session_date)}</strong> (${nextReady.classroom_name})`
              : ""
          }
          <br>برای تست، مسئول آموزش می‌تواند از منوی <strong>Timeline</strong> تاریخ پروژه را جلو ببرد.
        </div>`;
    } else {
      banner = `<div class="alert success">${readyCount} جلسه آماده گزارش${editCount ? ` · ${editCount} قابل ویرایش` : ""}</div>`;
    }

    pageContent.innerHTML = `
      <div class="card">
        ${banner}
        <p style="margin-bottom:0">لیست جلسات شما — روی <strong>Write Report</strong> بزنید:</p>
      </div>
      <div id="teacher-session-list" style="margin-top:16px"></div>`;

    renderTable(
      document.getElementById("teacher-session-list"),
      [
        { key: "session_number", label: "#" },
        { key: "classroom_name", label: "Class" },
        { key: "session_date", label: "Date", render: (row) => formatDate(row.session_date) },
        { key: "weekday", label: "Day" },
        {
          key: "session_duration",
          label: "Duration",
          render: (row) => `${row.session_duration} min`,
        },
        {
          key: "session_status",
          label: "Status",
          render: (row) => sessionStatusBadge(row.session_status),
        },
        {
          key: "is_salary_eligible",
          label: "48h Salary",
          render: (row) => salaryEligibleBadge(row.is_salary_eligible, row.report_status),
        },
        {
          key: "officer_note",
          label: "Rejection Reason",
          render: (row) => rejectionReasonCell(row.officer_note, row.report_status),
        },
      ],
      sessions,
      (row) => {
        if (row.can_submit) {
          return `<button onclick="openSessionReportForm(${row.class_session_id}, ${row.classroom_id})">Write Report</button>`;
        }
        if (row.can_edit && row.report_id) {
          return `<button class="secondary" onclick="editReport(${row.report_id})">Edit Report</button>`;
        }
        if (row.session_status === "approved") {
          return `<span class="badge approved">Done</span>`;
        }
        if (row.session_status === "upcoming") {
          return `<span class="badge upcoming">From ${formatDate(row.session_date)}</span>`;
        }
        return "-";
      }
    );
  } catch (error) {
    pageContent.innerHTML = `
      <div class="card">
        <div class="alert error">خطا در بارگذاری جلسات: ${error.message}</div>
      </div>`;
  }
}

window.openSessionReportForm = async function openSessionReportForm(classSessionId, classroomId) {
  const sessions = unwrapList(await API.request("/api/reports/my-sessions/"));
  const session = sessions.find((item) => item.class_session_id === classSessionId);
  if (!session || !session.can_submit) {
    showAlert(pageContent, "This session is not ready for reporting yet.");
    return;
  }

  pageContent.innerHTML = `
    <div class="card">
      <h3>Session Report</h3>
      <p><strong>Class:</strong> ${session.classroom_name}</p>
      <p><strong>Date:</strong> ${formatDate(session.session_date)} (${session.weekday})</p>
      <p><strong>Duration:</strong> ${session.session_duration} min</p>
      <form id="session-report-form">
        <input type="hidden" name="classroom" value="${classroomId}">
        <input type="hidden" name="class_session" value="${classSessionId}">
        <label>Summary</label>
        <textarea name="summary" rows="4" required></textarea>
        <label>Present Count</label>
        <input type="number" name="present_count" min="0" required>
        <label>Absent Count</label>
        <input type="number" name="absent_count" min="0" required>
        <div class="actions">
          <button type="submit">Submit Report</button>
          <button type="button" class="secondary" onclick="openPage('new-report')">Back</button>
        </div>
      </form>
    </div>`;

  document.getElementById("session-report-form").onsubmit = async (event) => {
    event.preventDefault();
    try {
      const body = formValues(event.target);
      body.classroom = Number(body.classroom);
      body.class_session = Number(body.class_session);
      await API.create("reports", body);
      showAlert(pageContent, "Report submitted.", "success");
      setTimeout(() => openPage("new-report"), 800);
    } catch (error) {
      showAlert(pageContent, error.message);
    }
  };
};

window.editReport = async function editReport(id) {
  const report = await API.request(`/api/reports/${id}/`);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit Report #${report.session_number}</h3>
      ${
        report.status === "rejected" && report.officer_note
          ? `<div class="alert pending"><strong>Rejection reason:</strong> ${escapeHtml(report.officer_note)}</div>`
          : ""
      }
      <form id="edit-report-form">
        <p><strong>Session:</strong> #${report.session_number} - ${formatDate(report.session_date)}</p>
        <p><strong>48h Salary:</strong> ${salaryEligibleLabel(report.is_salary_eligible, report.status)}</p>
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
      { key: "calculation_date", label: "Calc Date", render: (row) => formatDate(row.calculation_date) },
      { key: "period_start", label: "From", render: (row) => formatDate(row.period_start) },
      { key: "period_end", label: "To", render: (row) => formatDate(row.period_end) },
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
    unwrapList(data),
    (row) => officerActions("editSchool", "schools", row)
  );
}

window.editSchool = async function editSchool(id) {
  const school = await API.detail("schools", id);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit School</h3>
      <form id="school-edit-form" class="form-grid">
        <div><label>Name</label><input name="name" value="${school.name || ""}" required></div>
        <div><label>Level</label><input name="level" value="${school.level || ""}"></div>
        <div><label>Phone</label><input name="phone" value="${school.phone || ""}"></div>
        <div><label>Email</label><input name="email" type="email" value="${school.email || ""}"></div>
        <div class="full-width"><label>Address</label><textarea name="address" rows="2">${school.address || ""}</textarea></div>
      </form>
      <div class="actions">
        <button onclick="submitSchoolEdit(${id})">Save</button>
        <button class="secondary" onclick="openPage('schools')">Cancel</button>
      </div>
    </div>`;
};

window.submitSchoolEdit = async function submitSchoolEdit(id) {
  try {
    await API.update("schools", id, formValues(document.getElementById("school-edit-form")));
    openPage("schools");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

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
        <div><label>Start Date (1st of month)</label><input type="date" name="start_date" required></div>
        <div><label>End Date (last day of month)</label><input type="date" name="end_date" required></div>
        <div class="checkbox-field">
          <input type="checkbox" name="is_summer" id="term-is-summer">
          <label for="term-is-summer">Summer term</label>
        </div>
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
      { key: "is_summer", label: "Summer", render: (row) => (row.is_summer ? "Yes" : "No") },
    ],
    unwrapList(data),
    (row) => officerActions("editTerm", "terms", row)
  );
}

window.submitTermForm = async function submitTermForm() {
  try {
    const form = document.getElementById("term-form");
    const body = formValues(form);
    body.is_summer = form.querySelector('[name="is_summer"]').checked;
    await API.create("terms", body);
    openPage("terms");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

window.editTerm = async function editTerm(id) {
  const term = await API.detail("terms", id);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit Term</h3>
      <form id="term-edit-form" class="form-grid">
        <div><label>Name</label><input name="name" value="${term.name || ""}" required></div>
        <div><label>Start Date (1st of month)</label><input type="date" name="start_date" value="${term.start_date || ""}" required></div>
        <div><label>End Date (last day of month)</label><input type="date" name="end_date" value="${term.end_date || ""}" required></div>
        <div class="checkbox-field">
          <input type="checkbox" name="is_summer" id="term-edit-is-summer" ${term.is_summer ? "checked" : ""}>
          <label for="term-edit-is-summer">Summer term</label>
        </div>
      </form>
      <div class="actions">
        <button onclick="submitTermEdit(${id})">Save</button>
        <button class="secondary" onclick="openPage('terms')">Cancel</button>
      </div>
    </div>`;
};

window.submitTermEdit = async function submitTermEdit(id) {
  try {
    const form = document.getElementById("term-edit-form");
    const body = formValues(form);
    body.is_summer = form.querySelector('[name="is_summer"]').checked;
    await API.update("terms", id, body);
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
        <div class="full-width">
          <label>Weekly Sessions</label>
          <div class="weekday-options">${weekdayCheckboxes()}</div>
        </div>
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
      { key: "expected_session_count", label: "Sessions" },
    ],
    unwrapList(data),
    (row) => officerActions("editClass", "classes", row)
  );
}

window.editClass = async function editClass(id) {
  const [classroom, schools, terms] = await Promise.all([
    API.detail("classes", id),
    unwrapList(await API.list("schools")),
    unwrapList(await API.list("terms")),
  ]);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit Class</h3>
      <form id="class-edit-form" class="form-grid">
        <div><label>School</label><select name="school">${schools.map((s) => `<option value="${s.id}" ${s.id === classroom.school ? "selected" : ""}>${s.name}</option>`).join("")}</select></div>
        <div><label>Term</label><select name="term">${terms.map((t) => `<option value="${t.id}" ${t.id === classroom.term ? "selected" : ""}>${t.name}</option>`).join("")}</select></div>
        <div><label>Name</label><input name="name" value="${classroom.name || ""}" required></div>
        <div><label>Type</label><input name="class_type" value="${classroom.class_type || ""}"></div>
        <div><label>Duration</label><select name="session_duration">${[60, 90, 120].map((d) => `<option value="${d}" ${Number(classroom.session_duration) === d ? "selected" : ""}>${d}</option>`).join("")}</select></div>
        <div><label>Start Date</label><input type="date" name="start_date" value="${classroom.start_date || ""}" required></div>
        <div><label>End Date</label><input type="date" name="end_date" value="${classroom.end_date || ""}" required></div>
        <div class="full-width">
          <label>Weekly Sessions</label>
          <div class="weekday-options">${weekdayCheckboxes(classroom.weekday_list || [])}</div>
        </div>
      </form>
      <div class="actions">
        <button onclick="submitClassEdit(${id})">Save</button>
        <button class="secondary" onclick="openPage('classes')">Cancel</button>
      </div>
    </div>`;
};

window.submitClassEdit = async function submitClassEdit(id) {
  try {
    const form = document.getElementById("class-edit-form");
    const body = formValues(form);
    body.school = Number(body.school);
    body.term = Number(body.term);
    body.weekdays = readWeekdays(form);
    if (!body.weekdays.length) {
      showAlert(pageContent, "Select at least one weekly session day.");
      return;
    }
    await API.update("classes", id, body);
    openPage("classes");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

window.submitClassForm = async function submitClassForm() {
  try {
    const form = document.getElementById("class-form");
    const body = formValues(form);
    body.school = Number(body.school);
    body.term = Number(body.term);
    body.weekdays = readWeekdays(form);
    if (!body.weekdays.length) {
      showAlert(pageContent, "Select at least one weekly session day.");
      return;
    }
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
    unwrapList(data),
    (row) => officerActions("editAssignment", "teacher-assignments", row)
  );
}

window.editAssignment = async function editAssignment(id) {
  const [assignment, classes, teachers] = await Promise.all([
    API.detail("teacher-assignments", id),
    unwrapList(await API.list("classes")),
    unwrapList(await API.request("/api/auth/teachers/")),
  ]);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Edit Assignment</h3>
      <form id="assignment-edit-form" class="form-grid">
        <div><label>Class</label><select name="classroom">${classes.map((c) => `<option value="${c.id}" ${c.id === assignment.classroom ? "selected" : ""}>${c.name}</option>`).join("")}</select></div>
        <div><label>Teacher</label><select name="teacher">${teachers.map((t) => `<option value="${t.id}" ${t.id === assignment.teacher ? "selected" : ""}>${t.first_name} ${t.last_name} (${t.username})</option>`).join("")}</select></div>
        <div><label>Start Date</label><input type="date" name="start_date" value="${assignment.start_date || ""}" required></div>
        <div><label>End Date</label><input type="date" name="end_date" value="${assignment.end_date || ""}"></div>
      </form>
      <div class="actions">
        <button onclick="submitAssignmentEdit(${id})">Save</button>
        <button class="secondary" onclick="openPage('assignments')">Cancel</button>
      </div>
    </div>`;
};

window.submitAssignmentEdit = async function submitAssignmentEdit(id) {
  try {
    const body = formValues(document.getElementById("assignment-edit-form"));
    body.classroom = Number(body.classroom);
    body.teacher = Number(body.teacher);
    await API.update("teacher-assignments", id, body);
    openPage("assignments");
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

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
  const [schools, terms, teachers] = await Promise.all([
    unwrapList(await API.list("schools")),
    unwrapList(await API.list("terms")),
    unwrapList(await API.request("/api/auth/teachers/")),
  ]);
  pageContent.innerHTML = `
    <div class="card form-grid">
      <div><label>School</label><select id="filter-school"><option value="">All</option>${schools.map((s) => `<option value="${s.id}">${s.name}</option>`).join("")}</select></div>
      <div><label>Term</label><select id="filter-term"><option value="">All</option>${terms.map((t) => `<option value="${t.id}">${t.name}</option>`).join("")}</select></div>
      <div><label>Teacher</label><select id="filter-teacher"><option value="">All</option>${teachers.map((t) => `<option value="${t.id}">${t.first_name} ${t.last_name}</option>`).join("")}</select></div>
      <div><label>From</label><input type="date" id="filter-from"></div>
      <div><label>To</label><input type="date" id="filter-to"></div>
      <div><button onclick="loadOfficerReports()">Filter</button></div>
    </div>
    <div id="officer-report-list" style="margin-top:16px"></div>`;
  await loadOfficerReports();
}

window.loadOfficerReports = async function loadOfficerReports() {
  const params = new URLSearchParams();
  const school = document.getElementById("filter-school")?.value;
  const term = document.getElementById("filter-term")?.value;
  const teacher = document.getElementById("filter-teacher")?.value;
  const dateFrom = document.getElementById("filter-from")?.value;
  const dateTo = document.getElementById("filter-to")?.value;
  if (school) params.set("school", school);
  if (term) params.set("term", term);
  if (teacher) params.set("teacher", teacher);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString();
  const data = await API.request(`/api/reports/${query ? `?${query}` : ""}`);
  renderTable(
    document.getElementById("officer-report-list"),
    [
      { key: "session_number", label: "#" },
      { key: "teacher_name", label: "Teacher" },
      { key: "classroom_name", label: "Class" },
      { key: "term_name", label: "Term" },
      { key: "session_date", label: "Date", render: (row) => formatDate(row.session_date) },
      { key: "status", label: "Status", render: (row) => statusBadge(row.status) },
      {
        key: "is_salary_eligible",
        label: "48h Salary",
        render: (row) => salaryEligibleBadge(row.is_salary_eligible, row.status),
      },
      {
        key: "officer_note",
        label: "Rejection Reason",
        render: (row) => rejectionReasonCell(row.officer_note, row.status),
      },
    ],
    unwrapList(data),
    (row) => `
      <button onclick="openReportActionModal('approve', ${row.id})">Approve</button>
      <button class="danger" onclick="openReportActionModal('reject', ${row.id})">Reject</button>`
  );
};

window.approveReport = async function approveReport(id) {
  openReportActionModal("approve", id);
};

window.rejectReport = async function rejectReport(id) {
  openReportActionModal("reject", id);
};

async function renderTimeline() {
  pageContent.innerHTML = `<div class="card"><p>Loading timeline settings...</p></div>`;
  try {
    const clock = await API.request("/api/dev/clock/");
    const value = clock.override ? clock.override.slice(0, 16) : clock.project_now.slice(0, 16);
    pageContent.innerHTML = `
      <div class="card">
        <h3>Project Timeline (Test Clock)</h3>
        <p>Set a virtual "now" for this project only. Useful for testing the 48-hour approval rule without changing your computer clock.</p>
        <div class="form-grid">
          <div><label>Real system time</label><input value="${formatDateTime(clock.real_now)}" disabled></div>
          <div><label>Current project time</label><input value="${formatDateTime(clock.project_now)}" disabled></div>
          <div><label>Simulated datetime</label><input type="datetime-local" id="timeline-datetime" value="${value}"></div>
        </div>
        <div class="actions" style="margin-top:12px">
          <button onclick="applyTimeline()">Apply Test Time</button>
          <button class="secondary" onclick="resetTimeline()">Use Real Time</button>
        </div>
        <p style="font-size:13px;color:#666;margin-top:16px">
          Example: set time to 2 days after a session date, then approve a report to verify salary eligibility.
        </p>
      </div>`;
  } catch (error) {
    showAlert(pageContent, error.message);
  }
}

window.applyTimeline = async function applyTimeline() {
  try {
    const raw = document.getElementById("timeline-datetime").value;
    if (!raw) {
      showAlert(pageContent, "Choose a datetime first.");
      return;
    }
    await API.post("/api/dev/clock/", { datetime: raw });
    await refreshClockBanner();
    showAlert(pageContent, "Test time applied.", "success");
    setTimeout(() => renderTimeline(), 600);
  } catch (error) {
    showAlert(pageContent, error.message);
  }
};

window.resetTimeline = async function resetTimeline() {
  try {
    await API.post("/api/dev/clock/", { reset: true });
    await refreshClockBanner();
    showAlert(pageContent, "Real time restored.", "success");
    setTimeout(() => renderTimeline(), 600);
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
  const today = new Date().toISOString().slice(0, 10);
  pageContent.innerHTML = `
    <div class="card">
      <h3>Calculate Salaries</h3>
      <p style="color:#555;font-size:14px">
        تاریخ محاسبه را انتخاب کنید. حقوق برای <strong>۳۰ روز قبل</strong> از آن تاریخ محاسبه می‌شود
        (تا روز قبل از تاریخ محاسبه).
        <br>
        مثال: ۱۵ سپتامبر → بازه ۱۶ آگوست تا ۱۴ سپتامبر.
        <br>
        شرط پرداخت: همه جلسات آن بازه تأیید شده باشند؛ فقط جلسات تأییدشده در ۴۸ ساعت حقوق می‌گیرند.
      </p>
      <form id="calc-form" class="form-grid">
        <div><label>Calculation Date</label><input type="date" name="calculation_date" value="${today}" required></div>
      </form>
      <button onclick="submitCalcForm()">Calculate Last 30 Days</button>
      <div id="calc-result" style="margin-top:16px"></div>
    </div>`;
}

window.submitCalcForm = async function submitCalcForm() {
  const resultBox = document.getElementById("calc-result");
  try {
    const body = formValues(document.getElementById("calc-form"));
    const result = await API.post("/api/finance/salaries/calculate/", body);
    let html = `<div class="alert success">${result.detail || "Calculation completed."}</div>`;
    if (result.period_start && result.period_end) {
      html += `<p><strong>Payroll period:</strong> ${formatDate(result.period_start)} → ${formatDate(result.period_end)}</p>`;
    }

    if (result.skipped?.length) {
      html += `<div class="alert pending"><strong>Not paid (${result.skipped.length}):</strong><ul style="margin:8px 0 0 20px">`;
      html += result.skipped
        .map(
          (item) =>
            `<li><strong>${item.teacher_name}</strong>: ${item.reason}${
              item.session_count != null ? ` (${item.approved_count}/${item.session_count} approved, ${item.eligible_count} eligible)` : ""
            }</li>`
        )
        .join("");
      html += `</ul></div>`;
    }

    resultBox.innerHTML = html;

    if (result.records?.length) {
      renderTable(
        resultBox,
        [
          { key: "teacher_name", label: "Teacher" },
          { key: "calculation_date", label: "Calc Date", render: (row) => formatDate(row.calculation_date) },
          { key: "period_start", label: "From", render: (row) => formatDate(row.period_start) },
          { key: "period_end", label: "To", render: (row) => formatDate(row.period_end) },
          { key: "amount", label: "Amount" },
        ],
        result.records
      );
    } else if (!result.skipped?.length) {
      resultBox.innerHTML += `<p>No teachers qualified for this payroll period.</p>`;
    }
  } catch (error) {
    showAlert(resultBox, error.message);
  }
};

async function renderSalaryRecords() {
  pageContent.innerHTML = "<p>Loading...</p>";
  const data = await API.list("finance/salaries");
  renderTable(
    pageContent,
    [
      { key: "teacher_name", label: "Teacher" },
      { key: "calculation_date", label: "Calc Date", render: (row) => formatDate(row.calculation_date) },
      { key: "period_start", label: "From", render: (row) => formatDate(row.period_start) },
      { key: "period_end", label: "To", render: (row) => formatDate(row.period_end) },
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
