// Poker night: launches the backend the same way `uvicorn app.main:app
// --host 0.0.0.0 --port 8000` from an activated venv would, without
// requiring the venv to actually be activated in the current shell.
const { spawn } = require('node:child_process');
const { existsSync } = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const backendDir = path.join(__dirname, '..', 'backend');
const python = path.join(backendDir, '.venv', 'Scripts', 'python.exe');

if (!existsSync(python)) {
  console.error(
    'Backend venv not found at backend/.venv — run the one-time setup first (see README).'
  );
  process.exit(1);
}

const PORT = 8000;

// Print the LAN address(es) so phones/TVs know where to point, no ipconfig needed.
const lanUrls = Object.entries(os.networkInterfaces()).flatMap(([name, addrs]) =>
  (addrs ?? [])
    .filter((a) => a.family === 'IPv4' && !a.internal)
    .map((a) => `  ${name}: http://${a.address}:${PORT}`)
);
console.log(
  lanUrls.length
    ? `PokerTimer reachable on your network at:\n${lanUrls.join('\n')}\n`
    : 'No LAN IPv4 address found — are you connected to a network?\n'
);

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', String(PORT)],
  { cwd: backendDir, stdio: 'inherit' }
);

child.on('exit', (code) => process.exit(code ?? 0));
