const form = document.getElementById("query-form");
const input = document.getElementById("query-input");
const submitButton = document.getElementById("submit-button");
const conversation = document.getElementById("conversation");
const resultsPanel = document.getElementById("results-panel");
const resultsList = document.getElementById("results-list");
const agentPanel = document.getElementById("agent-panel");
const agentOutput = document.getElementById("agent-output");
const agentRaw = document.getElementById("agent-raw");
const statusBar = document.getElementById("status-bar");

let currentInstruction = "";
let currentResults = [];
let activeIndex = -1;
let isBusy = false;

const scrollConversationToBottom = () => {
  conversation.scrollTo({
    top: conversation.scrollHeight,
    behavior: "smooth",
  });
};

const clearPanels = () => {
  resultsList.innerHTML = "";
  resultsPanel.classList.add("hidden");
  agentPanel.classList.add("hidden");
  agentOutput.textContent = "";
  agentOutput.classList.add("empty");
  agentRaw.textContent = "No agent run yet.";
  activeIndex = -1;
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

  if (subtitle) {
    const label = document.createElement("div");
    label.className = "message-label";
    label.textContent = subtitle;
    wrapper.appendChild(label);
  }

  const body = document.createElement("div");
  body.textContent = text;
  wrapper.appendChild(body);
  conversation.appendChild(wrapper);
  scrollConversationToBottom();
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
  resultsList.innerHTML = "";
  if (!Array.isArray(results) || results.length === 0) {
    resultsPanel.classList.add("hidden");
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
      showStatus(`Running Notion agent using ${item.server || "selected server"}...`);
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

const setAgentDetails = (payload, server) => {
  agentPanel.classList.remove("hidden");

  agentOutput.innerHTML = "";
  agentOutput.classList.remove("empty");

  const meta = document.createElement("div");
  meta.className = "agent-meta";

  const nameSpan = document.createElement("span");
  nameSpan.className = "meta-primary";
  nameSpan.textContent = server.server || "Unknown server";
  meta.appendChild(nameSpan);

  if (payload.mcp_base_url) {
    const urlSpan = document.createElement("span");
    urlSpan.className = "meta-secondary";
    urlSpan.textContent = payload.mcp_base_url;
    meta.appendChild(urlSpan);
  }

  const instructionSpan = document.createElement("span");
  instructionSpan.className = "meta-secondary";
  instructionSpan.textContent = `Instruction: ${currentInstruction}`;
  meta.appendChild(instructionSpan);

  const outputParagraph = document.createElement("p");
  const finalText = safeText(payload.final_output).trim();
  outputParagraph.textContent = finalText || "Agent returned no output.";

  if (!finalText) {
    agentOutput.classList.add("empty");
  }

  agentOutput.append(meta, outputParagraph);

  if (payload.raw_output === null || payload.raw_output === undefined) {
    agentRaw.textContent = "No additional payload returned.";
  } else {
    try {
      agentRaw.textContent = JSON.stringify(payload.raw_output, null, 2);
    } catch (error) {
      agentRaw.textContent = safeText(payload.raw_output);
    }
  }
};

const fetchJSON = async (url, body) => {
  const response = await fetch(url, {
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

  const payload = await fetchJSON("/api/execute", {
    notion_instruction: currentInstruction,
    child_link: server.child_link,
    server_name: server.server,
  });

  appendMessage(
    "agent",
    safeText(payload.final_output).trim() || "Agent returned no output.",
    `AgentNet • ${server.server || "selected server"}`
  );
  setAgentDetails(payload, server);
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

  clearPanels();
  appendMessage("user", query, "You");
  showStatus("Searching for matching MCP servers...");
  setBusy(true);

  try {
    const searchPayload = await fetchJSON("/api/search", {
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

    showStatus("Running Notion agent...");
    await runAgentWithIndex(0);
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
