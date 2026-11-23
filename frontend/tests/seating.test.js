import { describe, expect, it } from 'vitest';
import { seatingTables } from '../src/lib/seating.js';

describe('seatingTables', () => {
  it('lays out seats per table with empties', () => {
    const { tables, unseated } = seatingTables(
      [{ name: 'Anna', table: 1, seat: 2 }, { name: 'Mads', table: 2, seat: 1 }], 2, 3);
    expect(tables).toEqual([
      { table: 1, seats: [{ seat: 1, name: null }, { seat: 2, name: 'Anna' }, { seat: 3, name: null }] },
      { table: 2, seats: [{ seat: 1, name: 'Mads' }, { seat: 2, name: null }, { seat: 3, name: null }] },
    ]);
    expect(unseated).toEqual([]);
  });

  it('lists players not seated yet', () => {
    const { unseated } = seatingTables(
      [{ name: 'Anna', table: null, seat: null }, { name: 'Mads', table: null, seat: null }], 1, 9);
    expect(unseated).toEqual(['Anna', 'Mads']);
  });

  it('reports whether a draw has happened', () => {
    expect(seatingTables([{ name: 'Anna', table: null, seat: null }], 1, 9).drawn).toBe(false);
    expect(seatingTables([{ name: 'Anna', table: 1, seat: 4 }], 1, 9).drawn).toBe(true);
    expect(seatingTables([], 1, 9).drawn).toBe(false);
  });
});
