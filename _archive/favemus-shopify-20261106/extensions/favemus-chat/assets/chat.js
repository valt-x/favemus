(function () {
  "use strict";

  var root = document.getElementById("favemus-chat");
  if (!root || root.dataset.favemusReady === "1") return;
  root.dataset.favemusReady = "1";

  var proxyRoot = (root.dataset.proxyRoot || "/apps/favemus").replace(/\/+$/, "");
  var title = root.dataset.title || "Chat with us";
  var greeting = root.dataset.greeting || "Hi! How can we help you today?";
  var color = root.dataset.color || "#111111";

  var storageKey = "favemus_chat_session";
  var sessionId = "";
  try {
    sessionId = localStorage.getItem(storageKey) || "";
  } catch (error) {
    sessionId = "";
  }
  function storeSession(value) {
    try {
      localStorage.setItem(storageKey, value);
    } catch {
      return;
    }
  }

  if (!sessionId) {
    sessionId =
      "web-" +
      Math.random().toString(36).slice(2, 10) +
      Date.now().toString(36);
    storeSession(sessionId);
  }

  var wrap = document.createElement("div");
  wrap.className = "favemus-chat";

  var launcher = document.createElement("button");
  launcher.type = "button";
  launcher.className = "favemus-chat__launcher";
  launcher.setAttribute("aria-label", "Open support chat");
  launcher.style.backgroundColor = color;
  launcher.innerHTML =
    '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';

  var panel = document.createElement("div");
  panel.className = "favemus-chat__panel";
  panel.hidden = true;

  var header = document.createElement("div");
  header.className = "favemus-chat__header";
  header.style.backgroundColor = color;

  var titleEl = document.createElement("span");
  titleEl.className = "favemus-chat__title";
  titleEl.textContent = title;

  var close = document.createElement("button");
  close.type = "button";
  close.className = "favemus-chat__close";
  close.setAttribute("aria-label", "Close chat");
  close.textContent = "\u00d7";

  header.appendChild(titleEl);
  header.appendChild(close);

  var messages = document.createElement("div");
  messages.className = "favemus-chat__messages";
  messages.setAttribute("aria-live", "polite");

  var form = document.createElement("form");
  form.className = "favemus-chat__form";

  var input = document.createElement("input");
  input.className = "favemus-chat__input";
  input.type = "text";
  input.placeholder = "Type your message";
  input.autocomplete = "off";
  input.maxLength = 2000;
  input.setAttribute("aria-label", "Message");

  var send = document.createElement("button");
  send.type = "submit";
  send.className = "favemus-chat__send";
  send.style.backgroundColor = color;
  send.textContent = "Send";

  form.appendChild(input);
  form.appendChild(send);

  panel.appendChild(header);
  panel.appendChild(messages);
  panel.appendChild(form);
  wrap.appendChild(panel);
  wrap.appendChild(launcher);
  root.appendChild(wrap);

  var greeted = false;

  function addMessage(text, who) {
    var el = document.createElement("div");
    el.className = "favemus-chat__msg favemus-chat__msg--" + who;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function openPanel() {
    panel.hidden = false;
    launcher.classList.add("favemus-chat__launcher--hidden");
    if (!greeted) {
      greeted = true;
      addMessage(greeting, "bot");
    }
    input.focus();
  }

  function closePanel() {
    panel.hidden = true;
    launcher.classList.remove("favemus-chat__launcher--hidden");
    launcher.focus();
  }

  launcher.addEventListener("click", openPanel);
  close.addEventListener("click", closePanel);

  var sending = false;

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = input.value.trim();
    if (!text || sending) return;

    input.value = "";
    addMessage(text, "user");
    var typing = addMessage("\u2026", "bot");
    sending = true;
    send.disabled = true;

    fetch(proxyRoot + "/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) {
            throw new Error(data && data.error ? data.error : "Request failed");
          }
          return data;
        });
      })
      .then(function (data) {
        if (data && data.session_id) {
          sessionId = data.session_id;
          storeSession(sessionId);
        }
        typing.textContent =
          (data && data.reply) || "Sorry, I did not get a reply.";
      })
      .catch(function () {
        typing.textContent = "Sorry, something went wrong. Please try again.";
      })
      .then(function () {
        sending = false;
        send.disabled = false;
        input.focus();
        messages.scrollTop = messages.scrollHeight;
      });
  });
})();
