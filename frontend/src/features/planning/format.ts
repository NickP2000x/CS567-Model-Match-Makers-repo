const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export function money(cents: number) {
  return currency.format(cents / 100);
}
