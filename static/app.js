let state = {
  userInput: "",
  questions: [],
};

// --- Step navigation ---

function showStep(id) {
  document.querySelectorAll(".step").forEach((s) => s.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function showLoader(text = "Thinking...") {
  document.getElementById("loader-text").textContent = text;
  document.getElementById("loader").classList.remove("hidden");
}

function hideLoader() {
  document.getElementById("loader").classList.add("hidden");
}

// --- Step 1: Handle input ---

async function handleInput() {
  const input = document.getElementById("user-input").value.trim();
  if (!input) return;

  state.userInput = input;
  showLoader("Generating questions...");

  try {
    const res = await fetch("http://localhost:8000/generate-prompt", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ user_input: input }),
    });

    const data = await res.json();

    console.log(data);

    if (!res.ok) {
      throw new Error(data.error || "Gemini API error");
    }

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
  const answers = state.questions.map((_, i) => {
    return document.getElementById(`answer-${i}`)?.value.trim() || "";
  });

  showLoader("Building your prompt...");

  try {
    const res = await fetch("http://localhost:8000/generate-prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_input: state.userInput,
        questions: state.questions,
        answers: answers,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error");

    document.getElementById("prompt-output").textContent = data.prompt;
    hideLoader();
    showStep("step-result");
  } catch (err) {
    hideLoader();
    alert("Something went wrong. Please try again.");
    console.error(err);
  }
}

// --- Step 3: Copy prompt ---

function copyPrompt() {
  const text = document.getElementById("prompt-output").textContent;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied to clipboard");
  });
}

function startOver() {
  state = { userInput: "", questions: [] };
  document.getElementById("user-input").value = "";
  document.getElementById("questions-list").innerHTML = "";
  document.getElementById("prompt-output").textContent = "";
  showStep("step-input");
}

// --- Toast ---

function showToast(message) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 2000);
}

// --- Enter key on textarea in step 1 (Shift+Enter = newline) ---

document.getElementById("user-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    handleInput();
  }
});