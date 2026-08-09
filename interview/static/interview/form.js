'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const amountInput = document.getElementById('question-amount');
    const pythonCheckbox = document.getElementById('python-technology');
    const randomCheckbox = document.querySelector(
        '[name="technologies"][value="random"]'
    );
    const categoryCheckboxes = document.querySelectorAll(
        '[name="technologies"]:not([value="random"])'
    );
    const complexityBlock = document.getElementById('python-complexity');
    const startInput = document.querySelector('[name="start"]');
    const endInput = document.querySelector('[name="end"]');
    const submitButton = document.getElementById('button');

    const clampAmount = () => {
        if (!amountInput || amountInput.value === '') {
            return;
        }

        const value = Number.parseInt(amountInput.value, 10);
        const minimum = Number.parseInt(amountInput.min, 10);
        const maximum = Number.parseInt(amountInput.max, 10);

        if (value < minimum) {
            amountInput.value = minimum;
        } else if (value > maximum) {
            amountInput.value = maximum;
        }
    };

    const rangeIsValid = () => {
        if (!startInput || !endInput) {
            return true;
        }

        const start = Number.parseInt(startInput.value, 10);
        const end = Number.parseInt(endInput.value, 10);

        return Number.isInteger(start)
            && Number.isInteger(end)
            && start >= 1
            && end <= 10
            && start <= end;
    };

    const updateSubmitState = () => {
        if (!submitButton) {
            return;
        }

        submitButton.disabled = Boolean(
            pythonCheckbox?.checked && !rangeIsValid()
        );
    };

    const updateComplexityVisibility = () => {
        if (!pythonCheckbox || !complexityBlock) {
            return;
        }

        complexityBlock.hidden = !pythonCheckbox.checked;
        pythonCheckbox.setAttribute(
            'aria-expanded',
            String(pythonCheckbox.checked)
        );
        updateSubmitState();
    };

    const levelRanges = {
        Junior: [1, 5],
        Middle: [5, 7],
        Senior: [7, 9],
    };

    amountInput?.addEventListener('change', clampAmount);
    amountInput?.addEventListener('blur', clampAmount);
    randomCheckbox?.addEventListener('change', () => {
        if (randomCheckbox.checked) {
            categoryCheckboxes.forEach((checkbox) => {
                checkbox.checked = false;
            });
        }
        updateComplexityVisibility();
    });
    categoryCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener('change', () => {
            if (checkbox.checked && randomCheckbox) {
                randomCheckbox.checked = false;
            }
            updateComplexityVisibility();
        });
    });
    startInput?.addEventListener('input', updateSubmitState);
    endInput?.addEventListener('input', updateSubmitState);

    document.querySelectorAll('[name="experience_level"]').forEach(
        (levelInput) => {
            levelInput.addEventListener('change', () => {
                const range = levelRanges[levelInput.value];
                if (!range || !startInput || !endInput) {
                    return;
                }

                [startInput.value, endInput.value] = range;
                updateSubmitState();
            });
        }
    );

    updateComplexityVisibility();
});
