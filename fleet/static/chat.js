"use strict";
(() => {
  const el = (id) => document.getElementById(id);
  const panel = el("fleet-chat"), input = el("chat-input"), log = el("chat-messages");
  let busy = false;
  const make = (tag, text, cls) => {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (cls) item.className = cls;
    return item;
  };
  function close() {
    panel.hidden = true;
    el("chat-toggle").setAttribute("aria-expanded", "false");
    el("chat-toggle").focus();
  }
  el("chat-toggle").addEventListener("click", () => {
    if (!panel.hidden) return close();
    panel.hidden = false;
    el("chat-toggle").setAttribute("aria-expanded", "true");
    input.focus();
  });
  el("chat-close").addEventListener("click", close);
  panel.addEventListener("keydown", (event) => { if (event.key === "Escape") close(); });
  document.querySelectorAll(".chat-suggestions button").forEach((button) => {
    button.addEventListener("click", () => {
      if (busy) return;
      input.value = button.textContent;
      el("chat-form").requestSubmit();
    });
  });
  el("chat-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy || input.value.trim().length < 3) return;
    busy = true;
    el("chat-send").disabled = true;
    const message = input.value.trim();
    input.value = "";
    log.append(make("p", message, "chat-user"));
    const responseBox = make("article", undefined, "chat-answer");
    responseBox.append(make("p", "Checking your question and published fleet data…"));
    log.append(responseBox);
    log.scrollTop = log.scrollHeight;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 65000);
    try {
      const response = await fetch("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message}), signal: controller.signal});
      const answer = await response.json();
      if (!response.ok) throw new Error(typeof answer.detail === "string" ? answer.detail : "Please enter a valid fleet question.");
      responseBox.replaceChildren(make("span", answer.mode === "llama" ? "LOCAL LLAMA · VERIFIED DATA" : answer.mode.toUpperCase(), "chat-mode"), make("p", answer.answer));
      if (answer.data.length) {
        const wrapper = make("div", undefined, "chat-table-wrap");
        const table = make("table");
        const head = make("thead"), row = make("tr");
        const keys = Object.keys(answer.data[0]);
        keys.forEach((key) => { const th = make("th", key.replaceAll("_", " ")); th.scope = "col"; row.append(th); });
        head.append(row); table.append(head);
        const body = make("tbody");
        answer.data.forEach((record) => {
          const tr = make("tr");
          keys.forEach((key) => tr.append(make("td", record[key] === null ? "Not recorded" : typeof record[key] === "number" ? record[key].toLocaleString("en-US", {maximumFractionDigits: 3}) : String(record[key]))));
          body.append(tr);
        });
        table.append(body); wrapper.append(table); responseBox.append(wrapper);
      }
      if (answer.period) responseBox.append(make("p", "Period: " + answer.period, "chat-evidence"));
      if (answer.sources.length) responseBox.append(make("p", "Sources: " + answer.sources.join(", ") + " · Snapshot: " + answer.run_id, "chat-evidence"));
      responseBox.append(make("p", answer.notice, "chat-evidence"), make("p", "Trace: " + answer.request_id, "chat-evidence"));
    } catch (error) {
      responseBox.replaceChildren(make("p", error.name === "AbortError" ? "The local model took too long. Try again when Ollama is ready." : error.message));
    } finally {
      clearTimeout(timer); busy = false; el("chat-send").disabled = false;
      log.scrollTop = log.scrollHeight;
    }
  });
})();
