const form = document.getElementById("query-form");
const input = document.getElementById("query-input");
const submitButton = document.getElementById("submit-button");
const conversation = document.getElementById("conversation");
const resultsPanel = document.getElementById("results-panel");
const resultsList = document.getElementById("results-list");

const statusBar = document.getElementById("status-bar");
const resetButton = document.getElementById("reset-chat");

const API_BASE_URL =
  (window.AGENTNET_CONFIG && window.AGENTNET_CONFIG.apiBaseUrl) || "/api";

const buildApiUrl = (path) => {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  const normalizedBase = API_BASE_URL.replace(/\/+$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
};

let currentInstruction = "";
let currentResults = [];
let activeIndex = -1;
let isBusy = false;
let conversationHistory = [];
let selectedServer = null;
let serverLocked = false;

const hideResultsPanel = () => {
  resultsList.innerHTML = "";
  resultsPanel.classList.add("hidden");
};

const scrollConversationToBottom = () => {
  conversation.scrollTo({
    top: conversation.scrollHeight,
    behavior: "smooth",
  });
};

const clearPanels = () => {
  hideResultsPanel();
  activeIndex = -1;
};

const resetChatContext = () => {
  conversation.innerHTML = "";
  conversationHistory = [];
  currentResults = [];
  selectedServer = null;
  serverLocked = false;
  currentInstruction = "";
  clearPanels();
  showStatus("Chat cleared. Ask a new question.");
  form.reset();
  input.focus();
};

const setBusy = (state) => {
  isBusy = state;
  submitButton.disabled = state;
  input.disabled = state;
  if (!state) {
    input.focus();
  }
};

const showStatus = (message, variant = "") => {
  statusBar.textContent = message || "";
  statusBar.className = variant ? variant : "";
};

const safeText = (value) => {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
};

const appendMessage = (role, text, subtitle = "") => {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const header = document.createElement("div");
  header.className = "message-header";

  if (subtitle) {
    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = subtitle;
    header.appendChild(label);
  }

  const time = document.createElement("span");
  time.className = "message-time";
  const now = new Date();
  time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  header.appendChild(time);
  wrapper.appendChild(header);

  const body = document.createElement("div");
  body.textContent = text;
  wrapper.appendChild(body);
  conversation.appendChild(wrapper);
  scrollConversationToBottom();

  if (role === "user" || role === "agent" || role === "assistant") {
    const normalizedRole = role === "agent" ? "assistant" : role;
    conversationHistory.push({ role: normalizedRole, content: text });
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }
  }
};

const updateActiveResultHighlight = () => {
  const cards = resultsList.querySelectorAll(".result-card");
  cards.forEach((card) => {
    const index = Number(card.dataset.index);
    if (index === activeIndex) {
      card.classList.add("active");
    } else {
      card.classList.remove("active");
    }
  });
};

const formatScore = (score) => {
  if (score === null || score === undefined || Number.isNaN(score)) {
    return null;
  }
  return Number(score).toFixed(2);
};

const renderResults = (results) => {
  if (serverLocked) {
    hideResultsPanel();
    return;
  }

  resultsList.innerHTML = "";
  if (!Array.isArray(results) || results.length === 0) {
    hideResultsPanel();
    return;
  }

  resultsPanel.classList.remove("hidden");

  results.forEach((item, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "result-card";
    button.dataset.index = String(index);

    const title = document.createElement("h3");
    title.className = "result-title";
    title.textContent = item.server || "Unknown server";

    const meta = document.createElement("div");
    meta.className = "result-meta";

    const childLink = item.child_link ? `Path: ${item.child_link}` : null;
    const score = formatScore(item.score);
    if (score) {
      const scoreSpan = document.createElement("span");
      scoreSpan.textContent = `Score ${score}`;
      meta.appendChild(scoreSpan);
    }
    if (childLink) {
      const linkSpan = document.createElement("span");
      linkSpan.textContent = childLink;
      meta.appendChild(linkSpan);
    }

    const why = document.createElement("p");
    why.className = "result-why";
    why.textContent = item.why || "No reason provided.";

    button.append(title, meta, why);
    button.addEventListener("click", async () => {
      if (isBusy || activeIndex === index) {
        return;
      }
      setBusy(true);
      const label = item.server || "selected server";
      if (item.mode === "direct") {
        showStatus("Answering directly (no MCP tools)...");
      } else {
        showStatus(`Running AgentNet through ${label}...`);
      }
      try {
        await runAgentWithIndex(index);
      } catch (error) {
        showStatus(error.message || "Agent run failed.", "error");
      } finally {
        setBusy(false);
      }
    });

    resultsList.appendChild(button);
  });

  updateActiveResultHighlight();
};

const fetchJSON = async (path, body) => {
  const response = await fetch(buildApiUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail = data && (data.detail || data.message);
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return data;
};

const runAgentWithIndex = async (index) => {
  const server = currentResults[index];
  if (!server) {
    throw new Error("Invalid server selection.");
  }

  activeIndex = index;
  updateActiveResultHighlight();
  selectedServer = server;
  serverLocked = true;
  hideResultsPanel();

  await runAgentWithServer(server, currentInstruction);
};

const runAgentWithServer = async (server, instruction) => {
  if (!server) {
    throw new Error("No server selected.");
  }
  currentInstruction = instruction;

  const payload = await fetchJSON("/execute", {
    notion_instruction: instruction,
    child_link: server.child_link,
    server_name: server.server,
    mode: server.mode,
    history: conversationHistory,
  });

  appendMessage(
    "agent",
    safeText(payload.final_output).trim() || "Agent returned no output.",
    `AgentNet • ${server.server || "selected server"}`
  );
  // setAgentDetails(payload, server); // Panel removed
  showStatus("Agent run completed.", "success");
};

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (isBusy) {
    return;
  }

  const query = input.value.trim();
  if (!query) {
    return;
  }

  // Clear the input immediately so the typed message moves to the chat list right away.
  form.reset();

  // If a server is already selected, reuse it and skip new RAG search.
  if (selectedServer) {
    hideResultsPanel();
    appendMessage("user", query, "You");
    showStatus(`Running AgentNet through ${selectedServer.server || "selected server"}...`);
    setBusy(true);
    try {
      await runAgentWithServer(selectedServer, query);
      showStatus("Agent run completed.", "success");
    } catch (error) {
      showStatus(error.message || "Agent run failed.", "error");
    } finally {
      setBusy(false);
      form.reset();
    }
    return;
  }

  clearPanels();
  appendMessage("user", query, "You");
  showStatus("Searching for matching MCP servers...");
  setBusy(true);

  try {
    const searchPayload = await fetchJSON("/search", {
      query,
      notion_instruction: query,
    });

    currentInstruction = searchPayload.notion_instruction || query;
    currentResults = Array.isArray(searchPayload.results) ? searchPayload.results : [];

    renderResults(currentResults);

    if (!currentResults.length) {
      showStatus("No matching MCP servers were found. Try another query.", "error");
      return;
    }

    showStatus("Select a server to run the agent.");
  } catch (error) {
    showStatus(error.message || "Something went wrong.", "error");
  } finally {
    setBusy(false);
    form.reset();
  }
});

// Provide keyboard support for Enter on the send button.
submitButton.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    submitButton.click();
  }
});

resetButton.addEventListener("click", () => {
  if (isBusy) {
    showStatus("Please wait for the current run to finish before starting over.", "error");
    return;
  }
  resetChatContext();
});
