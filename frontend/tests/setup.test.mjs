import assert from 'node:assert/strict';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const sourceDir = fileURLToPath(new URL('../../scripts/', import.meta.url));
const fakeNode = `#!/bin/bash
case "$1" in
  --version) printf '%s\\n' "$TEST_NODE_VERSION" ;;
  -p) printf '%s\\n' "$TEST_NODE_OS" ;;
  *)
    shift
    if [ "$1" = --version ]; then
      printf '11.9.0\\n'
    else
      printf '%s\\n' "$*" >> "$TEST_NPM_LOG"
    fi
    ;;
esac
`;

function executable(path, content) {
  writeFileSync(path, content, { mode: 0o755 });
}

// Each test owns a tiny isolated repository; it never changes real Node or npm.
function project(overrides = {}, native = true) {
  const root = mkdtempSync(join(tmpdir(), 'model-matchmakers setup '));
  for (const dir of ['scripts', 'frontend/node_modules', 'bin']) {
    mkdirSync(join(root, dir), { recursive: true });
  }
  for (const name of ['runtime.sh', 'setup.sh', 'frontend.sh']) {
    writeFileSync(join(root, 'scripts', name), readFileSync(join(sourceDir, name)));
  }
  writeFileSync(join(root, 'frontend/.nvmrc'), '24.14.0\n');
  const env = {
    ...process.env,
    PATH: `${join(root, 'bin')}:/usr/bin:/bin`,
    TEST_SYSTEM: 'Linux',
    TEST_RELEASE: '6.8.0-generic',
    TEST_ARCH: 'x86_64',
    TEST_NODE_VERSION: 'v24.14.0',
    TEST_NODE_OS: 'linux',
    TEST_NPM_LOG: join(root, 'npm-calls.txt'),
    ...overrides,
  };
  executable(join(root, 'bin/uname'), '#!/bin/bash\ncase "$1" in -s) printf "%s\\n" "$TEST_SYSTEM" ;; -r) printf "%s\\n" "$TEST_RELEASE" ;; -m) printf "%s\\n" "$TEST_ARCH" ;; esac\n');
  executable(join(root, 'bin/git'), '#!/bin/bash\nprintf "git version test\\n"\n');
  // An inherited npm must never be invoked by setup or the launcher.
  executable(join(root, 'bin/npm'), '#!/bin/bash\nprintf "WRONG NPM\\n" >&2; exit 99\n');
  executable(join(root, 'bin/node'), native ? fakeNode : '#!/bin/bash\nexit 1\n');
  if (native) {
    mkdirSync(join(root, 'lib/node_modules/npm/bin'), { recursive: true });
    writeFileSync(join(root, 'lib/node_modules/npm/bin/npm-cli.js'), '// fixture\n');
  }
  return { root, env };
}

function run(fixture, name = 'setup.sh', args = ['--check']) {
  return spawnSync('/bin/bash', [join(fixture.root, 'scripts', name), ...args], {
    cwd: tmpdir(), encoding: 'utf8', env: fixture.env,
  });
}

function mockDownload(fixture, { mismatch = false, failure = false } = {}) {
  const os = fixture.env.TEST_SYSTEM === 'Darwin' ? 'darwin' : 'linux';
  const arch = ['arm64', 'aarch64'].includes(fixture.env.TEST_ARCH) ? 'arm64' : 'x64';
  const dist = `node-v24.14.0-${os}-${arch}`;
  const payload = join(fixture.root, 'payload');
  mkdirSync(join(payload, dist, 'bin'), { recursive: true });
  mkdirSync(join(payload, dist, 'lib/node_modules/npm/bin'), { recursive: true });
  executable(join(payload, dist, 'bin/node'), fakeNode);
  writeFileSync(join(payload, dist, 'lib/node_modules/npm/bin/npm-cli.js'), '// fixture\n');
  const archive = join(fixture.root, `${dist}.tar.gz`);
  const tar = spawnSync('tar', ['-czf', archive, '-C', payload, dist]);
  assert.equal(tar.status, 0, tar.stderr.toString());
  fixture.env.TEST_ARCHIVE = archive;
  fixture.env.TEST_DOWNLOAD_LOG = join(fixture.root, 'downloads.txt');
  fixture.env.TEST_CHECKSUM = mismatch ? 'f'.repeat(64) : createHash('sha256').update(readFileSync(archive)).digest('hex');
  fixture.env.TEST_ARCHIVE_NAME = `${dist}.tar.gz`;
  executable(join(fixture.root, 'bin/curl'), failure ? '#!/bin/bash\nexit 22\n' : `#!/bin/bash
while [ "$#" -gt 0 ]; do
  case "$1" in
    https://*) url="$1" ;;
    --output) shift; output="$1" ;;
  esac
  shift
done
printf '%s\\n' "$url" >> "$TEST_DOWNLOAD_LOG"
case "$url" in
  */SHASUMS256.txt) printf '%s  %s\\n' "$TEST_CHECKSUM" "$TEST_ARCHIVE_NAME" > "$output" ;;
  *) /bin/cp "$TEST_ARCHIVE" "$output" ;;
esac
`);
  return dist;
}

test('native Linux check works from another directory and with spaces in its path', () => {
  const fixture = project();
  const result = run(fixture);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /native Linux/);
  assert.match(result.stdout, /No dependencies were installed/);
  assert.equal(existsSync(fixture.env.TEST_NPM_LOG), false);
  assert.equal(existsSync(join(fixture.root, '.tools')), false);
});

test('recognizes WSL and uses selected bundled npm instead of inherited npm', () => {
  const result = run(project({ TEST_RELEASE: 'microsoft-standard-WSL2' }));
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /WSL/);
  assert.match(result.stdout, /npm 11\.9\.0/);
});

test('recognizes simulated macOS arm64', () => {
  const result = run(project({ TEST_SYSTEM: 'Darwin', TEST_NODE_OS: 'darwin', TEST_ARCH: 'arm64' }));
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /macOS \(arm64\)/);
});

test('rejects unsupported platform and architecture', () => {
  for (const overrides of [{ TEST_SYSTEM: 'MINGW64_NT' }, { TEST_ARCH: 'armv7l' }]) {
    const result = run(project(overrides));
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Unsupported/);
  }
});

test('check-only rejects wrong-version and Windows Node without downloading', () => {
  for (const overrides of [{ TEST_NODE_VERSION: 'v20.0.0' }, { TEST_NODE_OS: 'win32' }]) {
    const fixture = project(overrides);
    const result = run(fixture);
    assert.equal(result.status, 1);
    assert.match(result.stderr, /Run bash scripts\/setup\.sh/);
    assert.equal(existsSync(join(fixture.root, '.tools')), false);
  }
});

test('missing Node check-only explains automatic setup rather than requiring manual Node', () => {
  const result = run(project({ TEST_RELEASE: 'microsoft-standard-WSL2' }, false));
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Run bash scripts\/setup\.sh/);
  assert.match(result.stderr, /development-setup\.md#wsl2-ubuntu/);
});

test('setup downloads, verifies, installs and reuses a local runtime', () => {
  const fixture = project({}, false);
  const dist = mockDownload(fixture);
  const first = run(fixture, 'setup.sh', []);
  assert.equal(first.status, 0, first.stderr);
  assert.match(first.stdout, /Verified and installed local runtime/);
  assert.equal(existsSync(join(fixture.root, '.tools', dist, 'bin/node')), true);
  assert.deepEqual(readFileSync(fixture.env.TEST_NPM_LOG, 'utf8').trim().split('\n'), ['ci', 'run build']);
  const downloads = readFileSync(fixture.env.TEST_DOWNLOAD_LOG, 'utf8');
  const second = run(fixture, 'setup.sh', []);
  assert.equal(second.status, 0, second.stderr);
  assert.match(second.stdout, /Using existing project-local Node/);
  assert.equal(readFileSync(fixture.env.TEST_DOWNLOAD_LOG, 'utf8'), downloads);
  const launch = run(fixture, 'frontend.sh', ['dev', '--host', '127.0.0.1']);
  assert.equal(launch.status, 0, launch.stderr);
  assert.match(readFileSync(fixture.env.TEST_NPM_LOG, 'utf8'), /run dev -- --host 127\.0\.0\.1/);
});

test('checksum mismatch blocks extraction and dependency installation', () => {
  const fixture = project({}, false);
  const dist = mockDownload(fixture, { mismatch: true });
  const result = run(fixture, 'setup.sh', []);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /checksum mismatch/);
  assert.equal(existsSync(join(fixture.root, '.tools', dist)), false);
  assert.equal(existsSync(fixture.env.TEST_NPM_LOG), false);
});

test('download failure gives retry guidance without installing', () => {
  const fixture = project({}, false);
  mockDownload(fixture, { failure: true });
  const result = run(fixture, 'setup.sh', []);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Check network access and rerun setup/);
  assert.equal(existsSync(fixture.env.TEST_NPM_LOG), false);
});

test('launcher never downloads Node automatically', () => {
  const fixture = project({}, false);
  const result = run(fixture, 'frontend.sh', ['dev']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Run bash scripts\/setup\.sh/);
  assert.equal(existsSync(join(fixture.root, '.tools')), false);
});
