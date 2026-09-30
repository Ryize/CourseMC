(() => {
    'use strict';

    const audience = document.querySelectorAll('input[name="audience"]');
    if (!audience.length) return;
    const groupFields = document.querySelectorAll('[data-groups-only]');

    function updateGroupFields() {
        const open = document.querySelector('input[name="audience"]:checked')?.value === 'open';
        for (const field of groupFields) field.hidden = open;
    }

    for (const radio of audience) radio.addEventListener('change', updateGroupFields);
    updateGroupFields();
})();
