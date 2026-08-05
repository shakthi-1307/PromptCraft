// --- State ---
let state = {
  userInput: "",
  questions: [],
  uploadedFiles: [],
};

function getToken() { return localStorage.getItem("pc_token"); }
function getName()  { return localStorage.getItem("pc_name"); }

function authHeaders() {
  return { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` };
}

// --- Screen navigation ---

function showScreen(id) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function showStep(id) {
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

// --- Loader ---

function showLoader(text = "Thinking...") {
  document.getElementById("loader-text").textContent = text;
  document.getElementById("loader").classList.remove("hidden");
}

function hideLoader() {
  document.getElementById("loader").classList.add("hidden");
}

// --- Toast ---

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

// --- Validation ---

function validateInput(value, { min = 0, max = Infinity, label = "Field" } = {}) {
  const trimmed = value.trim();
  if (!trimmed)             return `${label} cannot be empty.`;
  if (trimmed.length < min) return `${label} must be at least ${min} characters.`;
  if (trimmed.length > max) return `${label} must be under ${max} characters.`;
  return null;
}

// --- Auth tab switch ---

function switchTab(tab) {
  document.getElementById("form-login").classList.toggle("hidden",   tab !== "login");
  document.getElementById("form-signup").classList.toggle("hidden",  tab !== "signup");
  document.getElementById("form-forgot").classList.toggle("hidden",  tab !== "forgot");
  document.getElementById("tab-login").classList.toggle("active",    tab === "login");
  document.getElementById("tab-signup").classList.toggle("active",   tab === "signup");
  ["login-error", "signup-error", "forgot-error", "forgot-success"].forEach((id) => {
    document.getElementById(id)?.classList.add("hidden");
  });
}

async function handleForgot() {
  const email = document.getElementById("forgot-email").value.trim();
  if (!email) { showForgotMessage("error", "Please enter your email."); return; }

  const btn = document.getElementById("forgot-btn");
  btn.disabled = true;
  btn.textContent = "Sending...";

  try {
    const res  = await fetch("/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    showForgotMessage("success", "If that email exists, a reset link has been sent. Check your inbox.");
    btn.textContent = "Sent ✓";
  } catch (err) {
    showForgotMessage("error", "Something went wrong. Please try again.");
    btn.disabled = false;
    btn.textContent = "Send Reset Link →";
  }
}

function showForgotMessage(type, message) {
  const errEl = document.getElementById("forgot-error");
  const sucEl = document.getElementById("forgot-success");
  if (type === "error") {
    errEl.textContent = message; errEl.classList.remove("hidden");
    sucEl.classList.add("hidden");
  } else {
    sucEl.textContent = message; sucEl.classList.remove("hidden");
    errEl.classList.add("hidden");
  }
}

function showAuthError(formId, message) {
  const el = document.getElementById(`${formId}-error`);
  el.textContent = message;
  el.classList.remove("hidden");
}

// --- Login ---

async function handleLogin() {
  const email    = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  if (!email || !password) { showAuthError("login", "Please fill in all fields."); return; }

  showLoader("Logging in...");
  try {
    const res  = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");

    localStorage.setItem("pc_token", data.token);
    localStorage.setItem("pc_name", data.name);
    hideLoader();
    enterApp(data.name);
  } catch (err) {
    hideLoader();
    showAuthError("login", err.message);
  }
}

// --- Signup ---

async function handleSignup() {
  const name     = document.getElementById("signup-name").value.trim();
  const email    = document.getElementById("signup-email").value.trim();
  const password = document.getElementById("signup-password").value;

  const nameErr = validateInput(name,     { min: 2, max: 50,  label: "Name" });
  const passErr = validateInput(password, { min: 6, max: 72,  label: "Password" });

  if (!email)  { showAuthError("signup", "Please enter your email."); return; }
  if (nameErr) { showAuthError("signup", nameErr); return; }
  if (passErr) { showAuthError("signup", passErr); return; }

  showLoader("Creating account...");
  try {
    const res  = await fetch("/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed");

    localStorage.setItem("pc_token", data.token);
    localStorage.setItem("pc_name", data.name);
    hideLoader();
    showToast("Welcome! Check your email for a welcome message.");
    enterApp(data.name);
  } catch (err) {
    hideLoader();
    showAuthError("signup", err.message);
  }
}

// --- Enter app ---

function enterApp(name) {
  document.getElementById("user-name").textContent = name;
  showScreen("screen-app");
  showStep("step-input");
}

// --- Logout ---

function handleLogout() {
  localStorage.removeItem("pc_token");
  localStorage.removeItem("pc_name");
  showScreen("screen-auth");
  switchTab("login");
}

// --- File upload ---

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  handleFiles(Array.from(e.dataTransfer.files));
});
fileInput.addEventListener("change", () => { handleFiles(Array.from(fileInput.files)); fileInput.value = ""; });

async function handleFiles(files) {
  const valid = [];
  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "txt"].includes(ext)) { showToast(`${file.name}: only .pdf and .txt supported`); continue; }
    if (state.uploadedFiles.find((f) => f.filename === file.name)) { showToast(`${file.name} already uploaded`); continue; }
    valid.push(file);
  }
  if (!valid.length) return;

  showLoader(valid.length > 1 ? `Uploading ${valid.length} files...` : `Uploading ${valid[0].name}...`);
  // Upload all valid files in parallel
  await Promise.all(valid.map((file) => uploadFileSilent(file)));
  renderFileTags();
  hideLoader();
  showToast(valid.length > 1 ? `${valid.length} files uploaded` : `${valid[0].name} uploaded`);
}

async function uploadFileSilent(file) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const res  = await fetch("/upload", { method: "POST", headers: { "Authorization": `Bearer ${getToken()}` }, body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    state.uploadedFiles.push({ filename: data.filename });
  } catch (err) {
    showToast(`Failed to upload ${file.name}`);
  }
}

async function removeFile(filename) {
  await fetch(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE", headers: { "Authorization": `Bearer ${getToken()}` } });
  state.uploadedFiles = state.uploadedFiles.filter((f) => f.filename !== filename);
  renderFileTags();
}

function renderFileTags() {
  const list = document.getElementById("file-list");
  list.innerHTML = "";
  state.uploadedFiles.forEach(({ filename }) => {
    const tag = document.createElement("div");
    tag.className = "file-tag";
    tag.innerHTML = `<span>📄</span><span>${filename}</span><span class="remove" onclick="removeFile('${filename}')">×</span>`;
    list.appendChild(tag);
  });
}

// --- Step 1: Input ---

async function handleInput() {
  const input = document.getElementById("user-input").value.trim();

  const err = validateInput(input, { min: 10, max: 1000, label: "Your idea" });
  if (err) { showToast(err); return; }

  state.userInput = input;
  showLoader("Generating questions...");
  try {
    const res  = await fetch("/generate-questions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_input: input, filenames: state.uploadedFiles.map((f) => f.filename) }),
    });
    const data = await res.json();
    if (res.status === 429) { hideLoader(); showToast(data.detail); return; }
    if (!res.ok) throw new Error(data.detail || "Error");
    state.questions = data.questions;
    renderQuestions(data.questions);
    hideLoader();
    showStep("step-questions");
  } catch (err) {
    hideLoader();
    alert("Something went wrong. Please try again.");
  }
}

// --- Step 2: Questions ---

function renderQuestions(questions) {
  const container = document.getElementById("questions-list");
  container.innerHTML = "";
  questions.forEach((q, i) => {
    if (i > 0) { const d = document.createElement("div"); d.className = "questions-divider"; container.appendChild(d); }
    const block = document.createElement("div");
    block.className = "question-block";
    block.innerHTML = `<p>${q}</p><textarea id="answer-${i}" rows="2" placeholder="Your answer..."></textarea>`;
    container.appendChild(block);
  });
}

async function handleGenerate() {
  const answers = state.questions.map((_, i) => document.getElementById(`answer-${i}`)?.value.trim() || "");

  const allEmpty = answers.every((a) => !a);
  if (allEmpty) { showToast("Please answer at least one question for a better prompt."); return; }

  const safeAnswers = answers.map((a) => a.slice(0, 500));

  showLoader("Building your prompt...");
  try {
    const res  = await fetch("/generate-prompt", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_input: state.userInput, questions: state.questions, answers: safeAnswers, filenames: state.uploadedFiles.map((f) => f.filename) }),
    });
    const data = await res.json();
    if (res.status === 429) { hideLoader(); showToast(data.detail); return; }
    if (!res.ok) throw new Error(data.detail || "Error");
    document.getElementById("prompt-display").textContent = data.prompt;
    document.getElementById("prompt-output").value = data.prompt;
    showTokenBadge(data.token_count || 0);
    renderCoveragePanel(data.coverage || []);
    renderResultFiles();
    hideLoader();
    showStep("step-result");
    saveToHistory(state.userInput, data.prompt);
  } catch (err) {
    hideLoader();
    alert("Something went wrong. Please try again.");
  }
}

// --- Step 3: Result ---

function renderResultFiles() {
  const section = document.getElementById("result-files");
  const list    = document.getElementById("result-file-list");
  list.innerHTML = "";
  if (!state.uploadedFiles.length) { section.classList.add("hidden"); return; }
  state.uploadedFiles.forEach(({ filename }) => {
    const tag = document.createElement("div");
    tag.className = "file-tag";
    tag.innerHTML = `<span>📄</span><span>${filename}</span>`;
    list.appendChild(tag);
  });
  section.classList.remove("hidden");
}

function toggleEdit() {
  const display  = document.getElementById("prompt-display");
  const textarea = document.getElementById("prompt-output");
  const btn      = document.getElementById("btn-edit");
  const isEditing = !textarea.classList.contains("hidden");

  if (isEditing) {
    // Save edits — switch back to read-only
    const edited = textarea.value.trim();
    display.textContent = edited;
    display.classList.remove("hidden");
    textarea.classList.add("hidden");
    btn.textContent = "✎ Edit Prompt";
    btn.classList.remove("saving");
    // Update token count for saved version
    showTokenBadge(Math.max(1, Math.floor(edited.length / 4)));
    showToast("Edits saved");
  } else {
    // Enter edit mode
    textarea.value = display.textContent;
    display.classList.add("hidden");
    textarea.classList.remove("hidden");
    textarea.focus();
    btn.textContent = "✓ Save Edits";
    btn.classList.add("saving");
  }
}

// Live token update while editing
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("prompt-output").addEventListener("input", () => {
    const text  = document.getElementById("prompt-output").value;
    const count = Math.max(1, Math.floor(text.length / 4));
    document.getElementById("token-count").textContent = count;
    const badge = document.getElementById("token-badge");
    badge.classList.remove("good", "warn", "heavy");
    if (count <= 80)       badge.classList.add("good");
    else if (count <= 150) badge.classList.add("warn");
    else                   badge.classList.add("heavy");
  });
});


function showTokenBadge(count) {
  const badge = document.getElementById("token-badge");
  const label = document.getElementById("token-count");
  label.textContent = count;
  badge.classList.remove("hidden", "good", "warn", "heavy");
  if (count <= 80)       badge.classList.add("good");
  else if (count <= 150) badge.classList.add("warn");
  else                   badge.classList.add("heavy");
}

function renderCoveragePanel(coverage) {
  const panel = document.getElementById("coverage-panel");
  const list  = document.getElementById("coverage-list");
  list.innerHTML = "";

  if (!coverage || coverage.length === 0) {
    panel.classList.add("hidden");
    return;
  }

  const allCovered  = coverage.every((c) => c.covered);
  const noneCovered = coverage.every((c) => !c.covered);

  coverage.forEach((item) => {
    const el = document.createElement("div");
    el.className = "coverage-item";
    el.innerHTML = `
      <div class="coverage-icon ${item.covered ? "covered" : "missing"}">
        ${item.covered ? "✓" : "~"}
      </div>
      <div class="coverage-text">
        <div class="coverage-answer">${escapeHtml(item.answer)}</div>
        ${item.reason ? `<div class="coverage-reason">${escapeHtml(item.reason)}</div>` : ""}
      </div>
    `;
    list.appendChild(el);
  });

  // Summary line
  const summary = document.createElement("div");
  summary.className = `coverage-summary ${allCovered ? "all" : "some"}`;
  const coveredCount = coverage.filter((c) => c.covered).length;
  summary.textContent = allCovered
    ? `All ${coverage.length} answers included ✓`
    : `${coveredCount} of ${coverage.length} answers included`;
  list.appendChild(summary);

  panel.classList.remove("hidden");
}

function copyPrompt() {
  const textarea = document.getElementById("prompt-output");
  const display  = document.getElementById("prompt-display");
  const isEditing = !textarea.classList.contains("hidden");
  const text = isEditing ? textarea.value : display.textContent;
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard"));
}

async function startOver() {
  for (const { filename } of state.uploadedFiles) {
    await fetch(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE", headers: { "Authorization": `Bearer ${getToken()}` } });
  }
  state = { userInput: "", questions: [], uploadedFiles: [] };
  document.getElementById("user-input").value = "";
  document.getElementById("questions-list").innerHTML = "";
  document.getElementById("prompt-display").textContent = "";
  document.getElementById("prompt-output").value = "";
  document.getElementById("prompt-display").classList.remove("hidden");
  document.getElementById("prompt-output").classList.add("hidden");
  document.getElementById("btn-edit").textContent = "✎ Edit Prompt";
  document.getElementById("btn-edit").classList.remove("saving");
  document.getElementById("file-list").innerHTML = "";
  document.getElementById("result-file-list").innerHTML = "";
  document.getElementById("result-files").classList.add("hidden");
  document.getElementById("token-badge").classList.add("hidden");
  document.getElementById("token-count").textContent = "0";
  document.getElementById("coverage-panel").classList.add("hidden");
  document.getElementById("coverage-list").innerHTML = "";
  document.getElementById("char-counter").textContent = "0 / 1000";
  document.getElementById("char-counter").className = "char-counter";
  showStep("step-input");
}

// --- History ---

async function toggleHistory() {
  const panel   = document.getElementById("history-panel");
  const overlay = document.getElementById("history-overlay");
  const isOpen  = !panel.classList.contains("hidden");

  if (isOpen) {
    panel.classList.add("hidden");
    overlay.classList.add("hidden");
  } else {
    panel.classList.remove("hidden");
    overlay.classList.remove("hidden");
    await loadHistory();
  }
}

async function loadHistory() {
  const list = document.getElementById("history-list");
  list.innerHTML = `<p class="history-empty">Loading...</p>`;

  try {
    const res  = await fetch("/history", { headers: authHeaders() });
    const data = await res.json();

    if (!data.history.length) {
      list.innerHTML = `<p class="history-empty">No prompts yet. Generate one to see it here.</p>`;
      return;
    }

    list.innerHTML = "";
    data.history.forEach((item) => {
      const date = new Date(item.created_at).toLocaleDateString("en-US", {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
      });

      const el = document.createElement("div");
      el.className = "history-item";
      el.dataset.generated = item.generated;
      el.innerHTML = `
        <div class="history-item-header" onclick="toggleHistoryItem(this)">
          <div class="history-item-meta">
            <span class="history-item-input">${escapeHtml(item.user_input)}</span>
            <span class="history-item-date">${date}</span>
          </div>
          <div class="history-item-actions">
            <button class="history-btn" onclick="copyHistoryItem(event, this)">Copy</button>
            <button class="history-btn danger" onclick="deleteHistoryItem(event, '${item.id}', this)">Delete</button>
          </div>
        </div>
        <div class="history-item-body">${escapeHtml(item.generated)}</div>
      `;
      list.appendChild(el);
    });
  } catch (err) {
    list.innerHTML = `<p class="history-empty">Failed to load history.</p>`;
  }
}

function toggleHistoryItem(header) {
  header.nextElementSibling.classList.toggle("open");
}

function copyHistoryItem(e, btn) {
  e.stopPropagation();
  const generated = btn.closest(".history-item").dataset.generated;
  navigator.clipboard.writeText(generated).then(() => showToast("Copied to clipboard"));
}

async function deleteHistoryItem(e, id, btn) {
  e.stopPropagation();
  const res = await fetch(`/history/${id}`, { method: "DELETE", headers: authHeaders() });
  if (res.ok) {
    btn.closest(".history-item").remove();
    const list = document.getElementById("history-list");
    if (!list.children.length) {
      list.innerHTML = `<p class="history-empty">No prompts yet. Generate one to see it here.</p>`;
    }
    showToast("Prompt deleted");
  }
}

async function saveToHistory(userInput, generated) {
  try {
    await fetch("/history/save", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_input: userInput, generated }),
    });
  } catch (err) {
    console.error("Failed to save to history:", err);
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// --- Voice Input ---

let recognition = null;
let isListening  = false;

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showToast("Voice input not supported in this browser. Use Chrome or Edge.");
    return null;
  }

  const r = new SpeechRecognition();
  r.continuous     = false;
  r.interimResults = true;
  r.lang           = "en-US";

  r.onresult = (e) => {
    const transcript = Array.from(e.results).map((r) => r[0].transcript).join("");
    document.getElementById("user-input").value = transcript;
    // Update char counter
    const counter = document.getElementById("char-counter");
    counter.textContent = `${transcript.length} / 1000`;
    counter.className = "char-counter" + (transcript.length >= 1000 ? " limit" : transcript.length >= 800 ? " warn" : "");
  };

  r.onerror = (e) => {
    if (e.error === "not-allowed") showToast("Microphone access denied. Please allow mic permission.");
    else showToast("Voice input error. Please try again.");
    stopListening();
  };

  r.onend = () => stopListening();
  return r;
}

function toggleVoice() {
  if (isListening) {
    recognition?.stop();
    stopListening();
  } else {
    if (!recognition) recognition = initSpeechRecognition();
    if (!recognition) return;
    try { recognition.start(); startListening(); }
    catch (e) { showToast("Could not start voice input. Try again."); }
  }
}

function startListening() {
  isListening = true;
  document.getElementById("mic-btn").classList.add("listening");
  document.getElementById("mic-btn").title = "Stop listening";
}

function stopListening() {
  isListening = false;
  document.getElementById("mic-btn").classList.remove("listening");
  document.getElementById("mic-btn").title = "Voice input";
}

// --- Enter key shortcut ---
document.getElementById("user-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleInput(); }
});

// --- Character counter ---
document.getElementById("user-input").addEventListener("input", () => {
  const len     = document.getElementById("user-input").value.length;
  const counter = document.getElementById("char-counter");
  counter.textContent = `${len} / 1000`;
  counter.className   = "char-counter" + (len >= 1000 ? " limit" : len >= 800 ? " warn" : "");
});

// --- Init ---
if (getToken()) {
  enterApp(getName());
} else {
  showScreen("screen-auth");
}