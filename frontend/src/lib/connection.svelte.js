// Shared WebSocket connection. The server is the single source of truth:
// this store only mirrors broadcast state and forwards commands.
export const conn = $state({
  connected: false,
  isAdmin: false,
  state: null,
  soundEnabled: false,
  levelChangeAt: 0,
  lastError: null,
});

let ws = null;
let audioCtx = null;

export function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onopen = () => {
    conn.connected = true;
  };
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'state' || msg.type === 'level_change') {
      conn.state = msg.state;
      if ('is_admin' in msg) conn.isAdmin = msg.is_admin;
      if (msg.type === 'level_change') {
        conn.levelChangeAt = Date.now();
        playAlert();
      }
    } else if (msg.type === 'error') {
      conn.lastError = { message: msg.message, at: Date.now() };
    }
  };
  ws.onclose = () => {
    conn.connected = false;
    setTimeout(connect, 2000);
  };
}

export function send(action, payload = {}) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'command', action, payload }));
  }
}

// Browsers block audio until a user gesture; call this from a click handler.
export function enableSound() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  conn.soundEnabled = true;
}

function playAlert() {
  if (!audioCtx) return;
  // two short rising beeps
  for (const [freq, delay] of [[880, 0], [1175, 0.25]]) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.4, audioCtx.currentTime + delay);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + delay + 0.2);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(audioCtx.currentTime + delay);
    osc.stop(audioCtx.currentTime + delay + 0.22);
  }
}
