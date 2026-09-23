// Focused U2 phase 2B browser contract suite. All API traffic is mocked locally.
const { Buffer } = require('node:buffer');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const web = true;
const { chromium } = require(web ? (process.env.PLAYWRIGHT_MODULE || 'playwright') : 'playwright');
const repo = path.resolve(__dirname, '..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'knowledge-ui-'));
let html;
if (web) {
  const python = process.env.PYTHON || path.join(repo, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  execFileSync(python, [path.join(__dirname, 'render_knowledge.py'), path.join(temp, 'page.html')], { cwd: repo });
  html = fs.readFileSync(path.join(temp, 'page.html'));
} else {
  // Refuse an export older than any source file this suite exercises.
  const exported = fs.statSync(path.join(repo, 'dist/index.html')).mtimeMs;
  for (const file of ['src/screens/KnowledgeScreen.js', 'src/components/MessageText.js', 'src/services/apiClient.js', 'src/services/parityService.js']) {
    assert.ok(exported >= fs.statSync(path.join(repo, file)).mtimeMs, 'Run npx expo export --platform web before this test.');
  }
}
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  if (web && pathname === '/') { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(html); return; }
  const root = path.join(repo, web ? 'ai_assistant/static' : 'dist');
  const file = path.resolve(root, '.' + (web ? pathname.replace(/^\/static/, '') : pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (error, data) => {
    if (error) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'Content-Type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream' }); res.end(data);
  });
});
const escaped = name => name.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/([\\`*_{}\[\]()#!|])/g, '\\$1');
const special = 'Å_日本 & <img src=x onerror=alert(1)> _ [a] \\ ` * .txt';
const footer = names => 'Useful answer.\n\n**Källor i sökunderlaget**\n' + names.map((name, i) => `- ${escaped(name)} (KB ${i + 1})`).join('\n');
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
  let passed = 0;
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage(); page.setDefaultTimeout(10000);
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    let files = [], mode = { status: 201, data: { id: 2, name: 'upload.txt' } }, getFail = false, posts = 0, deletes = 0, release;
    let reply = footer([special]);
    let deleteMode = { status: 204 };
    const bot = { id: 7, name: 'Travel guide', description: 'Travel', personality: 'Helpful', category: 'travel', avatar_icon: 'book' };
    const conversation = { conversation_id: 'abc', bot_id: 7, bot_name: bot.name, title: 'Saved chat', message_count: 1, updated_at: '2026-09-23T12:00:00Z', messages: [] };
    await context.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token');
      // Accelerate only request timeout timers, not React/navigation timers.
      const original = window.setTimeout;
      window.setTimeout = (fn, ms, ...args) => original(fn, ms === 180000 && window.__shortKnowledgeTimeout ? 150 : ms, ...args);
    });
    await context.addCookies([{ name: 'sessionid', value: 'test-session', url: origin }]);
    const fulfill = (route, result) => route.fulfill({ status: result.status || 200, headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' }, ...(result.status === 204 ? {} : { contentType: result.html ? 'text/html' : 'application/json', body: result.html || JSON.stringify(result.data) }) });
    await context.route('**/*', async route => {
      const request = route.request(); const url = new URL(request.url()); const p = url.pathname;
      if (!p.includes('/api/') && !p.endsWith('/bot_chat_api/') && !p.endsWith('/ajax_chat/')) { if (url.origin === origin) return route.continue(); return route.abort(); }
      if (request.method() === 'OPTIONS') return fulfill(route, { status: 204 });
      if (/\/knowledge\/(\d+\/)?$/.test(p)) {
        if (request.method() === 'GET') return fulfill(route, getFail ? { status: 503, data: {} } : { data: { files } });
        if (web) {
          assert.match(request.headers().cookie, /sessionid=test-session/);
          assert.equal(request.headers()['x-csrftoken'], 'a'.repeat(64));
        } else assert.equal(request.headers().authorization, 'Token mock-token');
        if (request.method() === 'DELETE') {
          deletes++;
          if (deleteMode.delay) await new Promise(resolve => { release = resolve; });
          if (deleteMode.status === 204) files = files.filter(item => item.id !== Number(p.split('/').at(-2)));
          return fulfill(route, deleteMode);
        }
        posts++;
        assert.match(request.headers()['content-type'], /multipart\/form-data; boundary=/);
        const selected = mode;
        if (selected.delay) await new Promise(resolve => { release = resolve; });
        if (selected.abort) return route.abort('internetdisconnected');
        if (selected.timeout) { await new Promise(resolve => setTimeout(resolve, 250)); return route.abort(); }
        if (selected.status === 201 && selected.data?.id) files = [selected.data, ...files];
        return fulfill(route, selected);
      }
      let data;
      if (p.endsWith('/api/me/')) data = { username: 'Demo', email: 'demo@example.test', plan: 'premium' };
      else if (p.endsWith('/api/bots/')) data = [bot, { ...bot, id: 8, name: 'Second assistant' }];
      else if (p.endsWith('/api/conversations/')) data = [conversation];
      else if (p.endsWith('/api/conversations/abc/') || p.endsWith('/bot_chat_api/')) data = { ...conversation, messages: [{ id: 1, sender: 'bot', message: reply, timestamp: '2026-09-23T12:00:00Z' }] };
      else if (p.endsWith('/chat/') || p.endsWith('/ajax_chat/')) data = { response: reply, conversation_id: 'abc' };
      else throw new Error('Unexpected API request: ' + p);
      return fulfill(route, { data });
    });
    const upload = () => page.getByRole('button', { name: 'Upload Knowledge', exact: true });
    const refresh = () => page.getByRole('button', { name: 'Refresh file list', exact: true });
    async function open() {
      await page.goto(origin);
      if (!web) await page.getByRole('button', { name: 'Knowledge Base', exact: true }).first().click();
      await page.getByText('Knowledge list updated.', { exact: false }).waitFor();
    }
    async function pick(name = 'upload.txt') {
      const file = { name, mimeType: 'text/plain', buffer: Buffer.from('A useful fact.') };
      if (web) await page.locator('#knowledge-upload-form input[type=file]').setInputFiles(file);
      else { const chooser = page.waitForEvent('filechooser'); await page.getByRole('button', { name: 'Choose document', exact: true }).click(); await (await chooser).setFiles(file); }
    }
    const filename = () => page.locator('#knowledge-file-name');
    const retained = async () => {
      assert.equal(await page.locator('#knowledge-upload-form input[type=file]').evaluate(el => el.files.length), 1);
      assert.equal(await filename().textContent(), 'upload.txt');
    };
    async function check(message) { await page.getByText(message, { exact: false }).first().waitFor(); passed++; }
    await open(); await check('No uploaded knowledge yet.');
    assert.ok(await refresh().isVisible());
    assert.equal(await page.getByText(/Refresh knowledge/i).count(), 0);
    const choose = page.getByRole('button', { name: 'Choose file', exact: true });
    assert.ok(await choose.isVisible());
    assert.equal(await filename().textContent(), 'No file selected');
    assert.equal(await choose.getAttribute('aria-describedby'), 'knowledge-file-name');
    assert.equal(await filename().getAttribute('role'), 'status');
    assert.equal(await page.locator('#knowledge-upload-form input[type=file]').isVisible(), false);
    let dialogs = 0;
    const onDialog = dialog => { dialogs++; dialog.dismiss(); };
    page.on('dialog', onDialog);
    const hostile = 'Å_日本 & <img src=x onerror=alert(1)> \"quoted\".txt';
    for (const key of ['Enter', 'Space']) {
      await choose.focus();
      const chooser = page.waitForEvent('filechooser');
      await page.keyboard.press(key);
      await (await chooser).setFiles({ name: hostile, mimeType: 'text/plain', buffer: Buffer.from('Fact') });
      assert.equal(await filename().textContent(), hostile);
      assert.equal(await filename().locator('*').count(), 0);
    }
    assert.equal(dialogs, 0);
    page.off('dialog', onDialog);
    await page.locator('#knowledge-upload-form input[type=file]').setInputFiles([]);
    assert.equal(await filename().textContent(), 'No file selected');
    passed += 3;
    files = [{ id: 1, name: 'Existing.txt' }]; await refresh().click(); await check('Existing.txt');
    await pick(); await retained(); mode = { status: 201, data: { id: 2, name: 'upload.txt' }, delay: true };
    await upload().evaluate(el => { el.click(); el.click(); });
    await check('Uploading and processing…');
    assert.equal(posts, 1); assert.ok(await refresh().isDisabled()); assert.ok(await choose.isDisabled());
    assert.ok(await page.getByRole('button', { name: 'Delete Existing.txt', exact: true }).isDisabled());
    release(); await check('Knowledge uploaded and processed successfully!');
    assert.ok(await upload().isDisabled());
    assert.equal(await filename().textContent(), 'No file selected');
    assert.equal(await page.locator('#knowledge-upload-form input[type=file]').evaluate(el => el.files.length), 0); passed++;
    page.once('dialog', dialog => dialog.dismiss()); await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).click(); assert.equal(deletes, 0); passed++;
    deleteMode = { status: 204, delay: true };
    page.once('dialog', dialog => dialog.accept()); await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).click();
    await check('Deleting knowledge…'); assert.ok(await upload().isDisabled()); release(); await check('Knowledge deleted successfully.');
    await pick();
    const confirmed = [
      [400, { code: 'empty_content', error: 'No readable content.' }, 'No readable content.'],
      [400, { code: 'encrypted_document', error: 'Encrypted document.' }, 'Encrypted document.'],
      [400, { code: 'extraction_failed', error: 'Extraction failed.' }, 'Extraction failed.'],
      [400, { errors: { file: ['Unsupported file.'] } }, 'Unsupported file.'],
      [400, { errors: { __all__: ['Choose a file.'] } }, 'Choose a file.'],
      [403, { code: 'knowledge_quota_exceeded', error: 'Quota', plan: 'free' }, 'Knowledge storage limit reached for your free plan'],
      [403, { detail: 'CSRF or permission denied' }, 'Permission denied.'],
      [413, { code: 'processing_limit' }, 'This document exceeds the processing limit.'],
      [413, null, 'This document exceeds the processing limit.', '<html>Too large</html>'],
      [503, { code: 'embedding_failed' }, 'Document processing failed.'],
      [503, { code: 'storage_failed' }, 'Document processing failed.'],
      [404, { error: 'Not found.' }, web ? 'This assistant or document was not found.' : 'Not found.'],
    ];
    for (const [status, data, message, html] of confirmed) {
      mode = { status, data, html }; const before = posts; await upload().click(); await check(message);
      await retained(); assert.equal(posts, before + 1); assert.equal(await upload().isDisabled(), false);
    }
    for (const uncertain of [{ status: 201, data: { name: 'missing id' } }, { status: 201, html: '<html>Proxy</html>' }, { status: 200, data: { id: 2, name: 'wrong status' } }, { status: 502, data: {} }, { status: 503, data: {} }, { abort: true }, { timeout: true }]) {
      mode = uncertain; await page.evaluate(short => { window.__shortKnowledgeTimeout = short; }, !!uncertain.timeout); const before = posts; await upload().click(); await check('Upload could not be confirmed.');
      await retained(); assert.ok(await upload().isDisabled()); assert.equal(posts, before + 1);
      getFail = true; await refresh().click(); await check(web ? 'Unable to refresh knowledge.' : 'The service is temporarily unavailable.'); assert.ok(await upload().isDisabled());
      getFail = false; await refresh().click(); await check('Knowledge list updated.'); assert.equal(await upload().isDisabled(), false); await retained();
    }
    await page.evaluate(() => { window.__shortKnowledgeTimeout = false; });
    mode = { abort: true }; await upload().click(); await check('Upload could not be confirmed.');
    files.push({ id: 2, name: 'upload.txt' }); await refresh().click(); await check('Knowledge list updated.');
    assert.ok(await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).isVisible()); await retained();
    deleteMode = { status: 403, data: {} }; page.once('dialog', d => d.accept()); await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).click(); await check('Permission denied.');
    assert.ok(await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).isVisible());
    deleteMode = { status: 502, data: {} }; page.once('dialog', d => d.accept()); await page.getByRole('button', { name: 'Delete upload.txt', exact: true }).click(); await check('Deletion could not be confirmed.');
    assert.ok(await upload().isDisabled()); await refresh().click(); await check('Knowledge list updated.');
    for (const width of [360, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(temp, `knowledge-${width}.png`), fullPage: true }); passed++;
    }
    if (web) { await refresh().focus(); await page.keyboard.press('Enter'); await check('Knowledge list updated.'); assert.equal(await page.locator('#knowledge-status').getAttribute('aria-live'), 'polite'); }
    // Ignore a write response belonging to a departed screen/assistant.
    mode = { status: 201, data: { id: 99, name: 'Late.txt' }, delay: true };
    await upload().click(); await check('Uploading and processing…');
    if (web) {
      // Also cover back/forward cache: the old document can resume after navigation.
      await page.evaluate(() => { window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })); window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })); });
      await check('Knowledge list updated.');
    }
    else { await page.getByLabel(/back/i).first().click(); await page.getByRole('button', { name: 'Knowledge Base', exact: true }).last().click(); await check('Knowledge for Second assistant'); await check('Knowledge list updated.'); }
    release(); await page.waitForTimeout(100); assert.equal(await page.getByText('Late.txt', { exact: true }).count(), 0); passed++;
    // Actual chat and reopened history use the same server-supplied source footer.
    for (const names of [[special], [special, 'Other &amp; _file_.pdf'], []]) {
      reply = names.length ? footer(names) : 'Old history &lt;literal&gt; without knowledge.';
      await page.goto(origin);
      if (!web) { await page.getByRole('button', { name: 'All conversations', exact: true }).click(); await page.getByRole('button', { name: 'Open Saved chat', exact: true }).click(); }
      else await page.locator('.conversation-content').filter({ hasText: 'Saved chat' }).click();
      await check(names.length ? 'Källor i sökunderlaget' : reply);
      const content = web ? await page.locator('#chat-box').innerText() : await page.locator('body').innerText();
      for (const name of names) assert.ok(content.includes(name), `Readable filename: ${name}`);
      assert.equal((content.match(/Källor i sökunderlaget/g) || []).length, names.length ? 1 : 0);
      assert.equal(await page.locator('img[src=x]').count(), 0);
      if (names.length) {
        reply = reply.replace('Useful answer.', 'Fresh answer.');
        const input = web ? page.locator('#chat-input') : page.getByRole('textbox', { name: 'Message your assistant' });
        await input.fill('Use knowledge'); await page.getByRole('button', { name: 'Send', exact: true }).click();
        await check('Fresh answer.');
        const current = web ? await page.locator('#chat-box').innerText() : await page.locator('body').innerText();
        assert.ok(current.includes(special)); assert.equal((current.match(/Källor i sökunderlaget/g) || []).length, 1); passed++;
      }
    }
    if (!web) {
      await page.goto(origin); await page.getByRole('button', { name: 'Dark theme', exact: true }).click();
      await page.getByRole('button', { name: 'Knowledge Base', exact: true }).first().click(); await check('Knowledge list updated.');
      await page.screenshot({ path: path.join(temp, 'knowledge-dark.png'), fullPage: true });
      await pick(); await retained(); mode = { status: 401, data: { detail: 'Invalid token' } }; await upload().click(); await check('Welcome Back');
      assert.equal(await page.evaluate(() => localStorage.getItem('auth_token')), null);
    }
    assert.deepEqual(errors, []);
    console.log(`PASS ${web ? 'web' : 'mobile'}: ${passed} focused checks; no page errors. Screenshots: ${temp}`);
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
