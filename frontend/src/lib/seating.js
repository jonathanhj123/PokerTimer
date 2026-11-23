// Turn the server's flat player list into per-table seat rows for display.
export function seatingTables(players, tableCount, seatsPerTable) {
  const tables = [];
  for (let table = 1; table <= tableCount; table++) {
    const seats = [];
    for (let seat = 1; seat <= seatsPerTable; seat++) {
      const player = players.find((p) => p.table === table && p.seat === seat);
      seats.push({ seat, name: player ? player.name : null });
    }
    tables.push({ table, seats });
  }
  const unseated = players.filter((p) => p.table == null).map((p) => p.name);
  const drawn = players.some((p) => p.table != null);
  return { tables, unseated, drawn };
}

// Same rule as the server: names match ignoring case and surrounding spaces.
const nameKey = (name) => name.trim().toLowerCase();

export function isRegular(name, regulars) {
  const key = nameKey(name);
  return regulars.some((r) => nameKey(r.name) === key);
}

// Regulars as tappable chips; `playing` = already on tonight's list.
export function regularChips(regulars, players) {
  const tonight = new Set(players.map((p) => nameKey(p.name)));
  return regulars.map((r) => ({ id: r.id, name: r.name, playing: tonight.has(nameKey(r.name)) }));
}
