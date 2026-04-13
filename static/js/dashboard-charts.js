function formatCurrency(value) {
    return new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 }).format(value);
}
function formatNumber(value) {
    return new Intl.NumberFormat('ru-RU').format(value);
}
