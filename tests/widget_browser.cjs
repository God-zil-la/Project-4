/* Run with NODE_PATH pointing at an existing Playwright installation. No build. */
const { chromium } = require('playwright');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const http = require('node:http');

(async () => {
  const repo = path.resolve(__dirname, '..');
  const python = process.env.U3_PYTHON || path.join(repo, '.venv', 'Scripts', 'python.exe');
  const server = spawn(python, ['-B', path.join(__dirname, 'widget_browser_server.py')], { cwd: repo, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, windowsHide: true });
  let browser;
  let parentServer;
  try {
    const fixture = await new Promise((resolve, reject) => {
      let out = '';
      const timer = setTimeout(() => reject(new Error('Fixture startup timed out')), 60000);
      server.stdout.on('data', chunk => {
        out += chunk.toString();
        for (const line of out.split('\n')) {
          if (line.startsWith('{')) { clearTimeout(timer); resolve(JSON.parse(line)); return; }
        }
      });
      server.once('error', reject);
      server.once('exit', code => { clearTimeout(timer); reject(new Error(`Fixture exited ${code}: ${out}`)); });
    });
    // Drain logs without retaining chat request output.
    server.stderr.resume();
    browser = await chromium.launch({ channel: 'msedge', headless: true });
    const context = await browser.newContext({ viewport: { width: 380, height: 720 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const url = `${fixture.base}/bots/public/${fixture.publicIds[0]}/`;
    await page.goto(url);
    await page.waitForFunction(() => !document.getElementById('send').disabled);
    await page.getByLabel('Message', { exact: true }).fill('Visitor one question');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await page.getByText('You: Visitor one question', { exact: true }).waitFor();
    assert.equal(await page.locator('#messages img').count(), 0, 'AI text must not execute HTML');
    await page.reload();
    await page.getByText('You: Visitor one question', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const otherContext = await browser.newContext();
    const other = await otherContext.newPage();
    await other.goto(url);
    await other.waitForFunction(() => !document.getElementById('send').disabled);
    assert.equal(await other.locator('#messages p').count(), 0, 'New visitor must have empty history');
    await page.goto(`${fixture.base}/bots/public/${fixture.publicIds[1]}/`);
    await page.waitForFunction(() => !document.getElementById('send').disabled);
    assert.equal(await page.locator('#messages p').count(), 0, 'Other assistant must have its own session');
    await page.goto(url);
    await page.getByText('You: Visitor one question', { exact: true }).waitFor();
    // Commit the server response but drop it before the browser receives it.
    await page.route('**/message/', async route => { await route.fetch(); await route.abort(); });
    await page.getByLabel('Message', { exact: true }).fill('Response was lost');
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    await page.getByRole('button', { name: 'Refresh chat', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Send', exact: true }).isDisabled(), true);
    await page.unroute('**/message/');
    await page.getByRole('button', { name: 'Refresh chat', exact: true }).click();
    await page.getByText('You: Response was lost', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('Message', { exact: true }).inputValue(), 'Response was lost');
    await page.getByRole('button', { name: 'New chat', exact: true }).click();
    await page.getByText('New chat started.', { exact: true }).waitFor();
    assert.equal(await page.locator('#messages p').count(), 0);
    if (process.env.U3_SCREENSHOT_DIR) {
      fs.mkdirSync(process.env.U3_SCREENSHOT_DIR, { recursive: true });
      for (const scheme of ['light', 'dark']) {
        await page.emulateMedia({ colorScheme: scheme });
        await page.screenshot({ path: path.join(process.env.U3_SCREENSHOT_DIR, `public-${scheme}.png`), fullPage: true });
      }
    }
    // A different parent origin embeds the same real public page without a login cookie.
    parentServer = http.createServer((req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`<iframe title="Embedded chat" src="${url}"></iframe>`);
    });
    await new Promise(resolve => parentServer.listen(0, '127.0.0.1', resolve));
    await other.goto(`http://127.0.0.1:${parentServer.address().port}/`);
    const frame = other.frameLocator('iframe');
    await frame.getByRole('heading', { name: 'Travel guide', exact: true }).waitFor();
    await frame.getByLabel('Message', { exact: true }).fill('Embedded question');
    await frame.getByRole('button', { name: 'Send', exact: true }).click();
    await frame.getByText('You: Embedded question', { exact: true }).waitFor();
    // Owner UI: saved visitor conversations are visible and read-only.
    await context.addCookies([{ name: 'sessionid', value: fixture.session, url: fixture.base }]);
    await page.goto(`${fixture.base}/bots/${fixture.botId}/widget/`);
    await page.getByRole('heading', { name: 'Website Widget / Public Chatbot' }).waitFor();
    await page.goto(`${fixture.base}/bots/${fixture.botId}/playground/`);
    await page.locator('#chat-box').getByText('Embedded question', { exact: true }).waitFor();
    await page.waitForFunction(() => document.getElementById('chat-form').style.display === 'none');
    assert.deepEqual(errors, []);
    await otherContext.close();
    console.log('PASS: standalone/iframe chat, visitor and assistant isolation, reload, XSS text safety, lost-response recovery, new chat, responsive light/dark UI, owner visibility/read-only.');
  } finally {
    if (browser) await browser.close();
    if (parentServer) parentServer.close();
    server.kill();
    await once(server, 'exit').catch(() => {});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
