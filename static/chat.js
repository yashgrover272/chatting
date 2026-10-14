const statusElement = document.querySelector("#connection-status");
const messagesElement = document.querySelector("#messages");
const nameInput = document.querySelector("#person-name");
const messageInput = document.querySelector("#message-input");
const messageForm = document.querySelector("#message-form");
const sendButton = document.querySelector("#send-button");
const copyLinkButton = document.querySelector("#copy-link");

const address = new URL(window.location.href);
let room = address.searchParams.get("room");
if (!room) {
  room = crypto.randomUUID();
  address.searchParams.set("room", room);
  window.history.replaceState({}, "", address);
}

nameInput.value = localStorage.getItem("chat-name") || "";
let lastMessageId = 0;
let loadingMessages = false;

function showMessage(message) {
  const item = document.createElement("li");
  item.className = "message";
  if (message.person === nameInput.value.trim()) {
    item.classList.add("is-mine");
  }

  const person = document.createElement("strong");
  person.className = "message-person";
  person.textContent = message.person;

  const text = document.createElement("p");
  text.className = "message-text";
  text.textContent = message.message;

  item.append(person, text);
  messagesElement.append(item);
  messagesElement.scrollTop = messagesElement.scrollHeight;
}

async function loadMessages() {
  if (loadingMessages) return;
  loadingMessages = true;

  try {
    const query = new URLSearchParams({ room, after: String(lastMessageId) });
    const response = await fetch(`/api/messages?${query}`);
    if (!response.ok) throw new Error("Unable to load messages");

    const messages = await response.json();
    for (const message of messages) {
      showMessage(message);
      lastMessageId = message.id;
    }
    statusElement.textContent = "Connected";
  } catch {
    statusElement.textContent = "Reconnecting";
  } finally {
    loadingMessages = false;
    window.setTimeout(loadMessages, 1200);
  }
}

nameInput.addEventListener("change", () => {
  localStorage.setItem("chat-name", nameInput.value.trim());
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const person = nameInput.value.trim();
  const message = messageInput.value.trim();
  if (!person || !message) return;

  localStorage.setItem("chat-name", person);
  sendButton.disabled = true;
  try {
    const response = await fetch("/api/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ room, person, message }),
    });
    if (!response.ok) throw new Error("Unable to send message");
    messageInput.value = "";
    statusElement.textContent = "Connected";
    await loadMessages();
  } catch {
    statusElement.textContent = "Message not sent";
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

copyLinkButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(window.location.href);
    copyLinkButton.textContent = "Link copied";
    window.setTimeout(() => {
      copyLinkButton.textContent = "Copy invite link";
    }, 1600);
  } catch {
    statusElement.textContent = "Copy the link from the address bar";
  }
});

loadMessages();