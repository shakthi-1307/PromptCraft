let state = {
  userInput: "",
  questions: [],
  uploadedFiles: [], // [{ filename, characters }]
};

// --- Loader ---

function showLoader(text = "Thinking...") {
  document.getElementById("loader-text").textContent = text;
  document.getElementById("loader").classList.remove("hidden");
}

function hideLoader() {
  document.getElementById("loader").classList.add("hidden");
}

// --- Step navigation ---

function showStep(id) {
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

// --- File upload ---

const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  handleFiles(Array.from(e.dataTransfer.files));
});

fileInput.addEventListener("change", () => {
  handleFiles(Array.from(fileInput.files));
  fileInput.value = "";
});

async function handleFiles(files) {
  for (const file of files) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["pdf", "txt"].includes(ext)) {
      showToast(`${file.name}: only .pdf and .txt supported`);
      continue;
    }
    if (state.uploadedFiles.find((f) => f.filename === file.name)) {
      showToast(`${file.name} already uploaded`);
      continue;
    }
    await uploadFile(file);
  }
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  showLoader(`Uploading ${file.name}...`);
  try {
    const res = await fetch("/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    state.uploadedFiles.push({ filename: data.filename, characters: data.characters });
    renderFileTags();
    showToast(`${data.filename} uploaded`);
  } catch (err) {
    showToast(`Failed to upload ${file.name}`);
    console.error(err);
  } finally {
    hideLoader();
  }
}

async function removeFile(filename) {
  await fetch(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE" });
  state.uploadedFiles = state.uploadedFiles.filter((f) => f.filename !== filename);
  renderFileTags();
}

function renderFileTags() {
  const list = document.getElementById("file-list");
  list.innerHTML = "";
  state.uploadedFiles.forEach(({ filename }) => {
    const tag = document.createElement("div");
    tag.className = "file-tag";
    tag.innerHTML = `
      <span class="file-icon">📄</span>
      <span>${filename}</span>
      <span class="remove" onclick="removeFile('${filename}')">×</span>
    `;
    list.appendChild(tag);
  });
}

// --- Step 1: Handle input ---

async function handleInput() {
  const input = document.getElementById("user-input").value.trim();
  if (!input) return;

  state.userInput = input;
  showLoader("Generating questions...");

  try {
    const res = await fetch("/generate-questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_input: input,
        filenames: state.uploadedFiles.map((f) => f.filename),
      }),
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
    console.error(err);
  }
}

// --- Step 2: Render questions ---

function renderQuestions(questions) {
  const container = document.getElementById("questions-list");
  container.innerHTML = "";

  questions.forEach((q, i) => {
    if (i > 0) {
      const divider = document.createElement("div");
      divider.className = "questions-divider";
      container.appendChild(divider);
    }
    const block = document.createElement("div");
    block.className = "question-block";
    block.innerHTML = `
      <p>${q}</p>
      <textarea id="answer-${i}" rows="2" placeholder="Your answer..."></textarea>
    `;
    container.appendChild(block);
  });
}

// --- Step 2: Generate prompt ---

async function handleGenerate() {
  const answers = state.questions.map((_, i) =>
    document.getElementById(`answer-${i}`)?.value.trim() || ""
  );

  showLoader("Building your prompt...");

  try {
    const res = await fetch("/generate-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_input: state.userInput,
        questions: state.questions,
        answers,
        filenames: state.uploadedFiles.map((f) => f.filename),
      }),
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
    console.error(err);
  }
}

// --- Step 3: Result files ---

function renderResultFiles() {
  const section = document.getElementById("result-files");
  const list = document.getElementById("result-file-list");
  list.innerHTML = "";

  if (state.uploadedFiles.length === 0) {
    section.classList.add("hidden");
    return;
  }

  state.uploadedFiles.forEach(({ filename }) => {
    const tag = document.createElement("div");
    tag.className = "file-tag";
    tag.innerHTML = `<span class="file-icon">📄</span><span>${filename}</span>`;
    list.appendChild(tag);
  });

  section.classList.remove("hidden");
}

// --- Copy & reset ---

function copyPrompt() {
  const text = document.getElementById("prompt-output").textContent;
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard"));
}

async function startOver() {
  // Delete all uploaded files from server
  for (const { filename } of state.uploadedFiles) {
    await fetch(`/upload/${encodeURIComponent(filename)}`, { method: "DELETE" });
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

// --- Toast ---

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2200);
}

// --- Enter key shortcut on step 1 ---

document.getElementById("user-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleInput();
  }
});