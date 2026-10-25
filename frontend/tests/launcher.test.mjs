import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { createConnection, createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

const python = spawnSync('python3', ['-c', 'import sys; print(sys.executable)'], { encoding: 'utf8' });
const skip = python.status === 0 ? false : 'launcher checks require Python 3 (stdlib only)';
const scripts = new URL('../../scripts/', import.meta.url);

async function freePort() {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

async function fixture({ environment = true, frontend = true, ...overrides } = {}) {
  const root = mkdtempSync(join(tmpdir(), 'model matchmakers launch '));
  for (const dir of ['scripts', 'frontend/node_modules/vite/bin', 'backend/.venv/bin', 'bin', 'lib/node_modules/npm/bin', 'fakes']) {
    mkdirSync(join(root, dir), { recursive: true });
  }
  for (const name of ['run.sh', 'runtime.sh', 'stop.sh', 'process-identity.sh']) writeFileSync(join(root, 'scripts', name), readFileSync(new URL(name, scripts)));
  writeFileSync(join(root, 'frontend/.nvmrc'), '24.14.0\n');
  symlinkSync(process.execPath, join(root, 'bin/node'));
  if (overrides.MM_TEST_SYSTEM) {
    writeFileSync(join(root, 'bin/uname'), '#!/bin/bash\ncase "$1" in -s) printf "%s\\n" "$MM_TEST_SYSTEM" ;; -r) printf "%s\\n" "$MM_TEST_RELEASE" ;; -m) printf "%s\\n" "$MM_TEST_ARCH" ;; esac\n', { mode: 0o755 });
    // Preserve the real node symlink; select a separate native candidate wrapper.
    mkdirSync(join(root, 'platform-bin'));
    writeFileSync(join(root, 'platform-bin/node'), `#!/bin/bash\nif [ "$1" = -p ]; then printf '%s\\n' "$MM_TEST_NODE_OS"; else exec "${process.execPath}" "$@"; fi\n`, { mode: 0o755 });
  }
  writeFileSync(join(root, 'lib/node_modules/npm/bin/npm-cli.js'), 'console.log("11.9.0");');
  if (environment) {
    writeFileSync(join(root, 'backend/.venv/bin/python'), '#!/bin/bash\nexec "$MM_TEST_SYSTEM_PYTHON" "$@"\n', { mode: 0o755 });
  }
  writeFileSync(join(root, 'fakes/fastapi.py'), '# import-only dependency fixture\n');
  writeFileSync(join(root, 'fakes/uvicorn.py'), `
if __name__ == "__main__":
    import http.server, json, os, signal, subprocess, sys, time
    if os.environ.get("MM_TEST_BACKEND_FAIL"):
        raise SystemExit(17)
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1000)"])
    def stop(*args):
        worker.terminate()
        worker.wait(timeout=3)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with open(os.environ["MM_TEST_LOG"], "a") as log:
        log.write(json.dumps({"kind":"backend", "pid":os.getpid(), "worker":worker.pid,
            "development":os.environ.get("DEV_CONTROLS"), "cors":os.environ.get("CORS_ORIGINS")}) + "\\n")
    if os.environ.get("MM_TEST_BACKEND_WAIT"):
        time.sleep(1000)
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        def log_message(self, *args): pass
    port = int(sys.argv[sys.argv.index("--port") + 1])
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
`);
  if (frontend) writeFileSync(join(root, 'frontend/node_modules/vite/bin/vite.js'), `
const http = require('node:http');
const fs = require('node:fs');
fs.appendFileSync(process.env.MM_TEST_LOG, JSON.stringify({kind:'frontend',pid:process.pid,api:process.env.VITE_API_BASE_URL})+'\\n');
if (process.env.MM_TEST_FRONTEND_FAIL) process.exit(19);
const port = Number(process.argv[process.argv.indexOf('--port') + 1]);
http.createServer((req, res) => res.end('ready')).listen(port, '127.0.0.1');
`);
  return { root, env: {
    ...process.env,
    PATH: `${overrides.MM_TEST_SYSTEM ? join(root, 'platform-bin') + ':' : ''}${join(root, 'bin')}:${process.env.PATH}`,
    PYTHONPATH: join(root, 'fakes'),
    MM_TEST_SYSTEM_PYTHON: python.stdout.trim(),
    MM_TEST_LOG: join(root, 'events.jsonl'),
    MM_BACKEND_PORT: String(await freePort()),
    MM_FRONTEND_PORT: String(await freePort()),
    MM_START_TIMEOUT_SECONDS: '5',
    ...overrides,
  } };
}

function launch(f, t, args = []) {
  const child = spawn('/bin/bash', [join(f.root, 'scripts/run.sh'), ...args], {
    cwd: tmpdir(), env: f.env, stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  const exited = new Promise(resolve => child.on('exit', (code, signal) => resolve({ code, signal })));
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) { child.kill('SIGTERM'); await exited; }
  });
  return { child, exited, output: () => output };
}

async function stop(f) {
  const child = spawn('/bin/bash', [join(f.root, 'scripts/stop.sh')], { cwd: tmpdir(), env: f.env });
  let output = '';
  child.stdout.on('data', data => { output += data; });
  child.stderr.on('data', data => { output += data; });
  const code = await new Promise(resolve => child.on('exit', resolve));
  return { code, output };
}

function events(f) {
  return existsSync(f.env.MM_TEST_LOG) ? readFileSync(f.env.MM_TEST_LOG, 'utf8').trim().split('\n').map(JSON.parse) : [];
}

function assertStopped(f) {
  for (const entry of events(f)) for (const pid of [entry.pid, entry.worker].filter(Boolean)) {
    assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' }, `Process ${pid} survived launcher shutdown`);
  }
}

async function waitFor(check, detail, timeout = 10000) {
  const deadline = performance.now() + timeout;
  while (performance.now() < deadline) {
    if (await check()) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.fail(detail());
}

test('Linux exited-but-unreaped process is not treated as a running server', { skip: skip || (process.platform !== 'linux' && 'Linux zombie regression'), timeout: 10000 }, async t => {
  const parent = spawn(python.stdout.trim(), ['-u', '-c', 'import signal,subprocess,sys,time; child=subprocess.Popen([sys.executable,"-c","pass"]); signal.signal(signal.SIGTERM,lambda *args:(child.wait(),sys.exit(0))); print(child.pid,flush=True); time.sleep(30)']);
  const exited = new Promise(resolve => parent.on('exit', resolve));
  t.after(async () => { parent.kill(); await exited; });
  const pid = await new Promise(resolve => parent.stdout.once('data', chunk => resolve(Number(String(chunk).trim()))));
  await waitFor(() => readFileSync(`/proc/${pid}/stat`, 'utf8').split(') ')[1].startsWith('Z '), () => 'child did not become a zombie');
  assert.doesNotThrow(() => process.kill(pid, 0));
  const result = spawnSync('/bin/bash', ['-c', 'source "$1"; mm_process_running "$2"', 'check', new URL('process-identity.sh', scripts).pathname, String(pid)]);
  assert.equal(result.status, 1, result.stderr.toString());
});

test('combined launcher explains missing prerequisites without starting services', { skip, timeout: 15000 }, async t => {
  for (const options of [{ environment: false }, { frontend: false }]) {
    const f = await fixture(options);
    const run = launch(f, t);
    assert.equal((await run.exited).code, 1);
    assert.match(run.output(), /environment is missing|Frontend dependencies are missing/);
    assert.deepEqual(events(f), []);
  }
});

test('combined launcher rejects invalid ports before starting services', { skip, timeout: 15000 }, async t => {
  for (const overrides of [{ MM_BACKEND_PORT: 'bad' }, { MM_FRONTEND_PORT: '0' },
    { MM_BACKEND_PORT: '12345', MM_FRONTEND_PORT: '12345' }, { MM_START_TIMEOUT_SECONDS: '0' }]) {
    const f = await fixture(overrides);
    const run = launch(f, t);
    assert.equal((await run.exited).code, 1);
    assert.match(run.output(), /different integer ports/);
    assert.deepEqual(events(f), []);
  }
});

test('occupied ports fail without stopping an unrelated server', { skip, timeout: 15000 }, async t => {
  const server = createServer(socket => socket.end());
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  for (const variable of ['MM_BACKEND_PORT', 'MM_FRONTEND_PORT']) {
    const f = await fixture({ [variable]: String(server.address().port) });
    const run = launch(f, t);
    assert.equal((await run.exited).code, 1);
    assert.match(run.output(), /port .* is unavailable/);
    assert.equal(server.listening, true);
    assert.deepEqual(events(f), []);
  }
});

test('a recently closed frontend connection does not prevent immediate restart', { skip, timeout: 20000 }, async t => {
  const server = createServer(socket => socket.end('closed'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise((resolve, reject) => {
    const client = createConnection({ host: '127.0.0.1', port });
    client.on('data', () => {});
    client.on('error', reject);
    client.on('close', resolve);
  });
  await new Promise(resolve => server.close(resolve));
  const f = await fixture({ MM_FRONTEND_PORT: String(port) });
  const run = launch(f, t);
  await waitFor(async () => {
    try { return (await fetch(`http://127.0.0.1:${port}`)).ok; } catch { return false; }
  }, run.output);
  run.child.kill('SIGTERM');
  assert.equal((await run.exited).code, 143);
  assertStopped(f);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  test(`combined launcher connects API mode and cleans up both server groups on ${signal}`, { skip, timeout: 20000 }, async t => {
    const f = await fixture();
    const run = launch(f, t);
    await waitFor(async () => {
      try { return (await fetch(`http://127.0.0.1:${f.env.MM_FRONTEND_PORT}`)).ok; } catch { return false; }
    }, run.output);
    const [backend, frontend] = events(f);
    assert.equal(backend.kind, 'backend');
    assert.equal(frontend.kind, 'frontend');
    assert.equal(backend.development, 'true');
    assert.equal(backend.cors, `http://127.0.0.1:${f.env.MM_FRONTEND_PORT},http://localhost:${f.env.MM_FRONTEND_PORT}`);
    assert.equal(frontend.api, `http://127.0.0.1:${f.env.MM_BACKEND_PORT}`);
    assert.match(run.output(), /press Ctrl\+C to stop both/);
    run.child.kill(signal);
    assert.equal((await run.exited).code, signal === 'SIGINT' ? 130 : 143);
    assertStopped(f);
  });
}

test('backend startup failure never starts the frontend', { skip, timeout: 15000 }, async t => {
  const f = await fixture({ MM_TEST_BACKEND_FAIL: '1' });
  const run = launch(f, t);
  assert.equal((await run.exited).code, 1);
  assert.match(run.output(), /Backend stopped during startup/);
  assert.deepEqual(events(f), []);
});

test('backend readiness timeout cleans up its reload-worker group', { skip, timeout: 15000 }, async t => {
  const f = await fixture({ MM_TEST_BACKEND_WAIT: '1', MM_START_TIMEOUT_SECONDS: '1' });
  const run = launch(f, t);
  assert.equal((await run.exited).code, 1);
  assert.match(run.output(), /Backend did not become ready/);
  assert.deepEqual(events(f).map(entry => entry.kind), ['backend']);
  assertStopped(f);
});

test('frontend failure stops the backend and reload worker', { skip, timeout: 15000 }, async t => {
  const f = await fixture({ MM_TEST_FRONTEND_FAIL: '1' });
  const run = launch(f, t);
  assert.equal((await run.exited).code, 1);
  assert.match(run.output(), /A server exited/);
  assert.deepEqual(events(f).map(entry => entry.kind), ['backend', 'frontend']);
  assertStopped(f);
});

test('launcher platform selection supports simulated Ubuntu and macOS Intel/Apple Silicon', { skip, timeout: 20000 }, async t => {
  for (const [system, arch, os] of [['Linux', 'x86_64', 'linux'], ['Darwin', 'x86_64', 'darwin'], ['Darwin', 'arm64', 'darwin']]) {
    const f = await fixture({ MM_TEST_SYSTEM: system, MM_TEST_ARCH: arch, MM_TEST_NODE_OS: os, MM_TEST_RELEASE: 'test' });
    const run = launch(f, t);
    await waitFor(async () => {
      try { return (await fetch(`http://127.0.0.1:${f.env.MM_FRONTEND_PORT}`)).ok; } catch { return false; }
    }, run.output);
    assert.match(run.output(), system === 'Darwin' ? /macOS/ : /native Linux/);
    run.child.kill('SIGTERM');
    assert.equal((await run.exited).code, 143);
    assertStopped(f);
  }
});

test('stop command shuts down the tracked launcher and permits immediate restart', { skip, timeout: 20000 }, async t => {
  const f = await fixture();
  for (let i = 0; i < 2; i++) {
    const run = launch(f, t);
    await waitFor(async () => {
      try { return (await fetch(`http://127.0.0.1:${f.env.MM_FRONTEND_PORT}`)).ok; } catch { return false; }
    }, run.output);
    if (i === 0) {
      const duplicate = launch(f, t);
      assert.equal((await duplicate.exited).code, 1);
      assert.match(duplicate.output(), /already has a launcher running/);
    }
    const stopped = await stop(f);
    assert.equal(stopped.code, 0, stopped.output);
    assert.equal((await run.exited).code, 143);
    assertStopped(f);
  }
  const again = await stop(f);
  assert.equal(again.code, 0, again.output);
  assert.match(again.output, /No launcher is recorded/);
});

test('stop command interrupts backend startup without waiting for its long readiness timeout', { skip, timeout: 15000 }, async t => {
  const f = await fixture({ MM_TEST_BACKEND_WAIT: '1', MM_START_TIMEOUT_SECONDS: '180' });
  const run = launch(f, t);
  await waitFor(() => events(f).some(event => event.kind === 'backend'), run.output);
  const stopped = await stop(f);
  assert.equal(stopped.code, 0, stopped.output);
  assert.equal((await run.exited).code, 143);
  assert.deepEqual(events(f).map(event => event.kind), ['backend']);
  assertStopped(f);
});

test('stop refuses a stale PID identity and leaves an unrelated process running', { skip, timeout: 10000 }, async t => {
  const f = await fixture();
  const unrelated = spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)']);
  t.after(() => unrelated.kill());
  mkdirSync(join(f.root, '.tools'));
  writeFileSync(join(f.root, '.tools/dev-run.state'), `${unrelated.pid}\nlinux:old-boot:0\n`);
  const stopped = await stop(f);
  assert.equal(stopped.code, 1);
  assert.match(stopped.output, /no longer matches/);
  assert.doesNotThrow(() => process.kill(unrelated.pid, 0));
});

test('Linux stop remains valid when wall-clock ps timestamps change', { skip: skip || (process.platform !== 'linux' && 'Linux kernel identity check'), timeout: 15000 }, async t => {
  const f = await fixture();
  writeFileSync(join(f.root, 'bin/ps'), '#!/bin/bash\nprintf "earlier wall-clock time\\n"\n', { mode: 0o755 });
  const run = launch(f, t);
  await waitFor(async () => {
    try { return (await fetch(`http://127.0.0.1:${f.env.MM_FRONTEND_PORT}`)).ok; } catch { return false; }
  }, run.output);
  const identity = readFileSync(join(f.root, '.tools/dev-run.state'), 'utf8').split('\n')[1];
  assert.match(identity, /^linux:[0-9a-f-]+:\d+$/);
  writeFileSync(join(f.root, 'bin/ps'), '#!/bin/bash\nprintf "later wall-clock time\\n"\n', { mode: 0o755 });
  const stopped = await stop(f);
  assert.equal(stopped.code, 0, stopped.output);
  assert.equal((await run.exited).code, 143);
  assertStopped(f);
});

const tmuxAvailable = spawnSync('tmux', ['-V']).status === 0;
for (const action of ['stop command', 'frontend Ctrl+C', 'backend Ctrl+C']) {
  test(`tmux uses two panes and shuts down the pair with ${action}`, { skip: skip || (!tmuxAvailable && 'tmux is not installed'), timeout: 35000 }, async t => {
    const f = await fixture();
    const run = launch(f, t, ['--tmux']);
    assert.equal((await run.exited).code, 0, run.output());
    const session = run.output().match(/Started tmux session (model-matchmakers-\d+)/)?.[1];
    assert.ok(session, run.output());
    const tmux = args => spawnSync('tmux', ['-L', session, ...args], { encoding: 'utf8' });
    t.after(async () => { await stop(f); tmux(['kill-server']); });
    await waitFor(async () => {
      try { return (await fetch(`http://127.0.0.1:${f.env.MM_FRONTEND_PORT}`)).ok; } catch { return false; }
    }, () => run.output() + tmux(['capture-pane', '-p', '-t', `${session}:0.0`]).stdout);
    const panes = tmux(['list-panes', '-t', `${session}:0`, '-F', '#{pane_pid}']).stdout.trim().split('\n');
    assert.equal(panes.length, 2);
    if (action === 'stop command') {
      const stopped = await stop(f);
      assert.equal(stopped.code, 0, stopped.output);
    } else {
      const pane = action === 'frontend Ctrl+C' ? 1 : 0;
      assert.equal(tmux(['send-keys', '-t', `${session}:0.${pane}`, 'C-c']).status, 0);
    }
    await waitFor(() => tmux(['has-session', '-t', session]).status !== 0,
      () => 'tmux session survived shutdown:\n' + tmux(['capture-pane', '-p', '-t', `${session}:0.0`]).stdout
        + '\nFrontend:\n' + tmux(['capture-pane', '-p', '-t', `${session}:0.1`]).stdout
        + '\nPanes:\n' + tmux(['list-panes', '-t', `${session}:0`, '-F', '#{pane_pid} #{pane_dead} #{pane_current_command}']).stdout,
      20000);
    assertStopped(f);
  });
}
