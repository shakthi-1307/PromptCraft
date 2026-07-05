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

// --- Auth tab switch ---

function switchTab(tab) {
  document.getElementById("form-login").classList.toggle("hidden", tab !== "login");
  document.getElementById("form-signup").classList.toggle("hidden", tab !== "signup");
  document.getElementById("tab-login").classList.toggle("active", tab === "login");
  document.getElementById("tab-signup").classList.toggle("active", tab === "signup");
  document.getElementById("login-error").classList.add("hidden");
  document.getElementById("signup-error").classList.add("hidden");
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

  if (!name || !email || !password) { showAuthError("signup", "Please fill in all fields."); return; }
  if (password.length < 6) { showAuthError("signup", "Password must be at least 6 characters."); return; }

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
  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "txt"].includes(ext)) { showToast(`${file.name}: only .pdf and .txt supported`); continue; }
    if (state.uploadedFiles.find((f) => f.filename === file.name)) { showToast(`${file.name} already uploaded`); continue; }
    await uploadFile(file);
  }
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);
  showLoader(`Uploading ${file.name}...`);
  try {
    const res  = await fetch("/upload", { method: "POST", headers: { "Authorization": `Bearer ${getToken()}` }, body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");
    state.uploadedFiles.push({ filename: data.filename });
    renderFileTags();
    showToast(`${data.filename} uploaded`);
  } catch (err) {
    showToast(`Failed to upload ${file.name}`);
  } finally {
    hideLoader();
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
  if (!input) return;
  state.userInput = input;
  showLoader("Generating questions...");
  try {
    const res  = await fetch("/generate-questions", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_input: input, filenames: state.uploadedFiles.map((f) => f.filename) }),
    });
    const data = await res.json();
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
  showLoader("Building your prompt...");
  try {
    const res  = await fetch("/generate-prompt", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ user_input: state.userInput, questions: state.questions, answers, filenames: state.uploadedFiles.map((f) => f.filename) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error");
    document.getElementById("prompt-output").textContent = data.prompt;
    renderResultFiles();
    hideLoader();
    showStep("step-result");
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

function copyPrompt() {
  navigator.clipboard.writeText(document.getElementById("prompt-output").textContent)
    .then(() => showToast("Copied to clipboard"));
}

async function startOver() {
  for (const { filename } of state.uploadedFiles) {
    await fetch(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE", headers: { "Authorization": `Bearer ${getToken()}` } });
  }
  state = { userInput: "", questions: [], uploadedFiles: [] };
  document.getElementById("user-input").value = "";
  document.getElementById("questions-list").innerHTML = "";
  document.getElementById("prompt-output").textContent = "";
  document.getElementById("file-list").innerHTML = "";
  document.getElementById("result-file-list").innerHTML = "";
  document.getElementById("result-files").classList.add("hidden");
  showStep("step-input");
}

// --- Enter key shortcut ---
document.getElementById("user-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleInput(); }
});

// --- Init: check if already logged in ---
if (getToken()) {
  enterApp(getName());
} else {
  showScreen("screen-auth");
}