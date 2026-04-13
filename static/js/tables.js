document.addEventListener('htmx:afterSwap', function(event) {
    var tips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tips.map(function(el) { return new bootstrap.Tooltip(el); });
});
