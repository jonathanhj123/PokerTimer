import { describe, expect, it } from 'vitest';
import { mergeRows } from '../src/lib/structure.js';

const L = (sb, bb, minutes = 15) => ({ type: 'level', sb, bb, ante: 0, minutes });

describe('mergeRows', () => {
  it('keeps unsaved edits in other rows when one row is saved', () => {
    const oldServer = [L(25, 50), L(50, 100), L(100, 200)];
    // admin edited rows 0 and 2 locally (inputs give strings)
    const local = [{ ...L(25, 50), sb: '30' }, L(50, 100), { ...L(100, 200), minutes: '20' }];
    // row 0 saved -> server now has it
    const newServer = [L(30, 50), L(50, 100), L(100, 200)];
    const rows = mergeRows(local, oldServer, newServer);
    expect(rows[0]).toEqual(L(30, 50));
    expect(rows[2].minutes).toBe('20');     // unsaved edit survives
  });

  it('takes the server row when the server changed that row', () => {
    const oldServer = [L(25, 50)];
    const local = [{ ...L(25, 50), sb: '30' }];
    const newServer = [L(40, 80)];          // another admin saved something else
    expect(mergeRows(local, oldServer, newServer)).toEqual([L(40, 80)]);
  });

  it('starts fresh from the server when rows were added, removed or moved', () => {
    const oldServer = [L(25, 50), L(50, 100)];
    const local = [{ ...L(25, 50), sb: '30' }, L(50, 100)];
    const newServer = [L(25, 50), L(50, 100), L(100, 200)];
    expect(mergeRows(local, oldServer, newServer)).toEqual(newServer);
  });

  it('returns copies, not the server objects', () => {
    const newServer = [L(25, 50)];
    const rows = mergeRows([], [], newServer);
    rows[0].sb = 99;
    expect(newServer[0].sb).toBe(25);
  });
});
