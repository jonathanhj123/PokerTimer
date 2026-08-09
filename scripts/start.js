// Poker night: launches the backend the same way `uvicorn app.main:app
// --host 0.0.0.0 --port 8000` from an activated venv would, without
// requiring the venv to actually be activated in the current shell.
const { spawn } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

const backendDir = path.join(__dirname, '..', 'backend');
const python = path.join(backendDir, '.venv', 'Scripts', 'python.exe');

if (!existsSync(python)) {
  console.error(
    'Backend venv not found at backend/.venv — run the one-time setup first (see README).'
  );
  process.exit(1);
}

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'],
  { cwd: backendDir, stdio: 'inherit' }
);

child.on('exit', (code) => process.exit(code ?? 0));
