// Money arrives from the server as exact decimal strings ("110", "112.5").
export function formatMoney(value, currency = '') {
  let [whole, frac = ''] = String(value).split('.');
  frac = frac.replace(/0+$/, '');
  if (frac.length === 1) frac += '0';
  const amount = frac ? `${whole}.${frac}` : whole;
  if (!currency) return amount;
  return /^[a-zA-Z]+$/.test(currency) ? `${amount} ${currency}` : `${currency}${amount}`;
}

export function formatClock(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

export function formatChips(n) {
  return n.toLocaleString('en-US');
}

export function ordinal(n) {
  const rem10 = n % 10;
  const rem100 = n % 100;
  if (rem10 === 1 && rem100 !== 11) return `${n}st`;
  if (rem10 === 2 && rem100 !== 12) return `${n}nd`;
  if (rem10 === 3 && rem100 !== 13) return `${n}rd`;
  return `${n}th`;
}
