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
  return { tables, unseated };
}
