import { describe, expect, it } from 'vitest';
import { formatChips, formatClock, formatMoney, ordinal } from '../src/lib/format.js';

describe('formatMoney', () => {
  it('shows whole amounts clean', () => {
    expect(formatMoney('110', '$')).toBe('$110');
    expect(formatMoney('110.00', '$')).toBe('$110');
  });
  it('pads a single decimal to two', () => {
    expect(formatMoney('112.5', '$')).toBe('$112.50');
    expect(formatMoney('112.50', '$')).toBe('$112.50');
  });
  it('never rounds longer decimals', () => {
    expect(formatMoney('112.375', '$')).toBe('$112.375');
  });
  it('suffixes alphabetic currencies', () => {
    expect(formatMoney('110', 'kr')).toBe('110 kr');
    expect(formatMoney('110', '€')).toBe('€110');
  });
  it('works without a currency', () => {
    expect(formatMoney('110')).toBe('110');
  });
});

describe('formatClock', () => {
  it('formats minutes and padded seconds', () => {
    expect(formatClock(754)).toBe('12:34');
    expect(formatClock(59)).toBe('0:59');
    expect(formatClock(0)).toBe('0:00');
    expect(formatClock(3600)).toBe('60:00');
  });
});

describe('formatChips', () => {
  it('adds thousands separators', () => {
    expect(formatChips(10000)).toBe('10,000');
    expect(formatChips(950)).toBe('950');
  });
});

describe('ordinal', () => {
  it('handles standard and teen cases', () => {
    expect(['1st', '2nd', '3rd', '4th']).toEqual([1, 2, 3, 4].map(ordinal));
    expect(['11th', '12th', '13th', '21st']).toEqual([11, 12, 13, 21].map(ordinal));
  });
});
