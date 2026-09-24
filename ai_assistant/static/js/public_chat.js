/* One session per assistant, embedding site and browser tab; cookies are not required. */
(() => {
  'use strict';
  const root = document.getElementById('public-chat');
  const messages = document.getElementById('messages');
  const status = document.getElementById('status');
  const input = document.getElementById('message');
  const send = document.getElementById('send');
  const fresh = document.getElementById('new-chat');
  const refresh = document.getElementById('refresh-chat');
  const key = `widget:${root.dataset.sessionUrl}`;
  let token = null;
  let busy = false;
  let uncertain = false;
  try { token = sessionStorage.getItem(key); } catch { /* In-memory fallback for blocked storage. */ }
  function append(sender, text) {
    const p = document.createElement('p');
    p.className = sender === 'user' ? 'user' : 'assistant';
    p.textContent = `${sender === 'user' ? 'You' : 'Assistant'}: ${text}`;
    messages.appendChild(p);
  }
  function controls() {
    send.disabled = busy || !token || uncertain;
    fresh.disabled = busy;
    refresh.disabled = busy;
    input.disabled = busy;
  }
  async function post(url, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(url, { method: 'POST', credentials: 'omit',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: controller.signal });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.error || data.detail || 'Chat unavailable. Please try again later.');
      return data;
    } finally { clearTimeout(timer); }
  }
  async function load(newChat = false) {
    if (busy) return;
    busy = true; controls(); status.textContent = 'Loading…';
    try {
      const data = await post(root.dataset.sessionUrl, !newChat && token ? { visitor_token: token } : {});
      token = data.visitor_token;
      try { sessionStorage.setItem(key, token); } catch { /* Continue in memory. */ }
      messages.replaceChildren();
      data.messages.forEach(item => append(item.sender, item.message));
      uncertain = false; refresh.hidden = true;
      status.textContent = newChat ? 'New chat started.' : '';
      if (newChat) input.value = '';
    } catch (error) {
      uncertain = true; refresh.hidden = false; status.textContent = error.message;
    } finally { busy = false; controls(); }
  }
  document.getElementById('chat-form').addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (busy || uncertain || !token || !message) return;
    busy = true; controls(); status.textContent = 'Thinking…';
    try {
      const data = await post(root.dataset.messageUrl, { visitor_token: token, message });
      append('user', message); append('assistant', data.response);
      input.value = ''; status.textContent = '';
    } catch (error) {
      uncertain = true; refresh.hidden = false;
      status.textContent = `${error.message} Refresh the chat to check delivery before sending again. Your draft is kept.`;
    } finally { busy = false; controls(); }
  });
  fresh.addEventListener('click', () => load(true));
  refresh.addEventListener('click', () => load());
  load();
})();
