const elements = {
  form: document.getElementById("search-form"),
  queryInput: document.getElementById("query-input"),
  modeSelect: document.getElementById("mode-select"),
  daysInput: document.getElementById("days-input"),
  eventTitle: document.getElementById("event-title"),
  eventSummary: document.getElementById("event-summary"),
  modeUsed: document.getElementById("mode-used"),
  coverageWindow: document.getElementById("coverage-window"),
  heroStats: document.getElementById("hero-stats"),
  statusBox: document.getElementById("status-box"),
  consensusList: document.getElementById("consensus-list"),
  conflictList: document.getElementById("conflict-list"),
  sourceGrid: document.getElementById("source-grid"),
  timeline: document.getElementById("timeline"),
  briefList: document.getElementById("brief-list"),
};

function renderList(target, items) {
  target.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

function renderStats(data) {
  const stats = [
    { label: "Articles compared", value: data.articles.length },
    { label: "Sources compared", value: new Set(data.articles.map((item) => item.source)).size },
    { label: "Consensus points", value: data.analysis.consensus.length },
    { label: "Conflict points", value: data.analysis.conflicts.length },
  ];

  elements.heroStats.innerHTML = stats
    .map(
      (item) => `
        <div class="stat-card">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
        </div>
      `
    )
    .join("");
}

function renderSources(articles) {
  elements.sourceGrid.innerHTML = articles
    .map(
      (article) => `
        <article class="source-card">
          <div class="source-topline">
            <span class="outlet">${article.source}</span>
            <span class="feed-badge">RSS</span>
          </div>
          <h3 class="headline">${article.title}</h3>
          <div class="badge-row">
            <span class="pill meta">Source & time</span>
            <span class="pill unique">Outlet angle</span>
          </div>
          <div class="meta-row">
            <span>${new Date(article.published).toLocaleString()}</span>
          </div>
          <p>${article.summary || "This feed provided a short or empty summary."}</p>
          <a class="story-link" href="${article.link}" target="_blank" rel="noreferrer">Read original coverage</a>
        </article>
      `
    )
    .join("");
}

function renderBrief(briefItems = []) {
  elements.briefList.innerHTML = briefItems
    .map((item) => {
      const sources =
        item.sources && item.sources.length
          ? `<div class="brief-sources">${item.sources
              .map(
                (s) =>
                  `<a href="${s.link}" target="_blank" rel="noreferrer">${s.name}</a>`
              )
              .join(" · ")}</div>`
          : "";
      return `
        <div class="brief-item ${item.type}">
          <div class="brief-bar"></div>
          <div>
            <p class="brief-text">${item.text}</p>
            ${item.levelDisplay ? `<div class="tag ${item.type}">${item.levelDisplay}</div>` : ""}
            ${sources}
          </div>
        </div>
      `;
    })
    .join("");
}

function renderTimeline(entries) {
  elements.timeline.innerHTML = entries
    .map(
      (entry) => `
        <div class="timeline-item">
          <div class="timeline-time">${entry.time}</div>
          <p>${entry.detail}</p>
        </div>
      `
    )
    .join("");
}

function setLoadingState(query, mode) {
  elements.eventTitle.textContent = `Analyzing coverage for "${query}"`;
  elements.eventSummary.textContent = "Fetching live RSS feeds and preparing the comparison.";
  elements.modeUsed.textContent = mode;
  elements.coverageWindow.textContent = "Loading";
  elements.statusBox.textContent = "Working on a fresh comparison...";
  renderList(elements.consensusList, ["Loading live coverage..."]);
  renderList(elements.conflictList, ["Checking for disagreements and uncertainty..."]);
  elements.sourceGrid.innerHTML = "";
  elements.timeline.innerHTML = "";
  elements.heroStats.innerHTML = "";
}

function renderResponse(data) {
  elements.eventTitle.textContent = data.analysis.overview.title;
  elements.eventSummary.textContent = data.analysis.overview.summary;
  elements.modeUsed.textContent = data.modeUsed;
  elements.coverageWindow.textContent = data.analysis.overview.coverageWindow;
  elements.statusBox.textContent = data.errors.length
    ? data.errors.join(" | ")
    : "Live comparison completed successfully.";

  renderStats(data);
  renderList(elements.consensusList, data.analysis.consensus);
  renderList(elements.conflictList, data.analysis.conflicts);
  renderSources(data.articles);
  // Prefer claims with levels; fall back to brief.
  const claims = (data.analysis.claims || []).map((c) => {
    let type = "unique";
    if (c.level === "green_strong" || c.level === "green_light") type = "consensus";
    else if (c.level === "red") type = "conflict";
    return {
      type,
      text: `${c.text}（支持 ${c.support} 源）`,
      sources: c.sources || [],
      levelDisplay: c.levelDisplay || "",
    };
  });
  renderBrief(claims.length ? claims : data.analysis.brief || []);
  renderTimeline(data.analysis.timeline);
}

async function runAnalysis(query, mode) {
  setLoadingState(query, mode);

  try {
    const response = await fetch(
      `/api/search?q=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}&days=${encodeURIComponent(
        elements.daysInput.value || "3"
      )}`
    );

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }

    const data = await response.json();
    renderResponse(data);
  } catch (error) {
    elements.statusBox.textContent =
      "The app could not reach the backend. Start the local Python server and try again.";
    elements.eventSummary.textContent = String(error);
    renderList(elements.consensusList, ["Backend unavailable."]);
    renderList(elements.conflictList, ["No analysis available."]);
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  runAnalysis(elements.queryInput.value.trim() || "technology", elements.modeSelect.value);
});

document.querySelectorAll(".topic-chip").forEach((button) => {
  button.addEventListener("click", () => {
    elements.queryInput.value = button.dataset.topic;
    runAnalysis(button.dataset.topic, elements.modeSelect.value);
  });
});

runAnalysis(elements.queryInput.value, elements.modeSelect.value);
