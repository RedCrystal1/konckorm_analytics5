document.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'calendar-grid') {
        var tips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tips.map(function(el) { return new bootstrap.Tooltip(el); });
    }
});
