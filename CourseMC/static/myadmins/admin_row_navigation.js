(() => {
    "use strict";

    const ROW_SELECTOR = "#result_list tr.data-row";
    const CHANGE_LINK_SELECTOR = 'a[href*="/change/"]';
    const INTERACTIVE_SELECTOR = [
        "a",
        "button",
        "input",
        "select",
        "textarea",
        "label",
        "summary",
        "[role='button']",
        "[contenteditable='true']",
        "[x-sort\\:handle]",
        "[x-on\\:click]",
        ".cursor-move",
    ].join(",");

    function getChangeLink(row) {
        return row.querySelector(CHANGE_LINK_SELECTOR);
    }

    function shouldKeepNativeBehaviour(event) {
        return Boolean(
            event.defaultPrevented
            || event.target.closest(INTERACTIVE_SELECTOR)
            || window.getSelection()?.toString()
        );
    }

    function followRowLink(event, row, link) {
        if (shouldKeepNativeBehaviour(event)) {
            return;
        }

        if (event.ctrlKey || event.metaKey) {
            window.open(link.href, "_blank", "noopener");
            return;
        }

        if (event.shiftKey) {
            window.open(link.href, "_blank", "noopener");
            return;
        }

        window.location.assign(link.href);
    }

    function prepareRow(row) {
        if (row.dataset.rowNavigationReady === "true") {
            return;
        }

        const link = getChangeLink(row);
        if (!link) {
            return;
        }

        row.dataset.rowNavigationReady = "true";
        row.dataset.rowHref = link.href;
        row.classList.add("cm-clickable-row");
        row.tabIndex = 0;
        row.title = "Открыть для редактирования";

        row.addEventListener("click", (event) => {
            if (event.button !== 0) {
                return;
            }
            followRowLink(event, row, link);
        });

        row.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" || event.target !== row) {
                return;
            }
            event.preventDefault();
            window.location.assign(link.href);
        });
    }

    function prepareRows(root = document) {
        root.querySelectorAll(ROW_SELECTOR).forEach(prepareRow);
    }

    document.addEventListener("DOMContentLoaded", () => prepareRows());

    document.addEventListener("htmx:afterSwap", (event) => {
        prepareRows(event.target);
    });
})();
