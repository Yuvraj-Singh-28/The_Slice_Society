document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('.site-header');

    if (!header) return;

    const updateHeader = () => {
        header.classList.toggle('scrolled', window.scrollY > 12);
    };

    updateHeader();
    window.addEventListener('scroll', updateHeader, { passive: true });
});
