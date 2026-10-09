// Run with node; reads the actual template helper without starting the app.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../templates/bots/playground.html'), 'utf8');
const helper = source.slice(source.indexOf('        async function readChatResponse('),
    source.indexOf('        async function sendMessage('));
assert.ok(helper.includes('readChatResponse'));
const read = vm.runInNewContext(helper + '\nreadChatResponse', {TextDecoder, Error});

function response(bytes, size = 1) {
    return new Response(new ReadableStream({
        start(controller) {
            for (let i = 0; i < bytes.length; i += size) {
                controller.enqueue(bytes.slice(i, i + size));
            }
            controller.close();
        }
    }), {headers: {'Content-Type': 'application/x-ndjson'}});
}

(async () => {
    const reply = 'မင်္ဂလာပါ — svenska åäö — English '.repeat(20);
    const bytes = new TextEncoder().encode('{"type":"heartbeat"}\n' +
        JSON.stringify({type: 'result', status: 200, data: {reply, conversation_id: 'kept'}}) + '\n');
    for (const size of [1, 7, bytes.length]) {
        const result = await read(response(bytes, size));
        assert.equal(result.reply, reply);
        assert.equal(result.conversation_id, 'kept');
    }
    const encode = text => new TextEncoder().encode(text);
    assert.equal((await read(response(encode('{"type":"result","status":403,"data":{"error":"Quota"}}\n')))).error, 'Quota');
    assert.equal((await read(new Response('{"error":"Busy"}', {status: 503}))).error, 'Busy');
    await assert.rejects(read(response(encode('{"type":"heartbeat"}\n'))), /without a final result/);
    await assert.rejects(read(response(encode('{"type":"result"'))), /without a final result/);
    await assert.rejects(read(response(encode('invalid\n'))));
    console.log('8 frontend checks passed: Unicode/chunks, errors, JSON fallback, missing/truncated/malformed final result.');
})().catch(error => { console.error(error); process.exitCode = 1; });
