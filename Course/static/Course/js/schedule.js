(() => {
    let activeRequest = null;

    function getResults() {
        return document.getElementById("schedule-results");
    }

    function setLoading(isLoading) {
        const results = getResults();
        if (!results) {
            return;
        }
        results.classList.toggle("loading", isLoading);
        results.setAttribute("aria-busy", String(isLoading));
    }

    function showRequestError() {
        const error = getResults()?.querySelector(".schedule-request-error");
        if (!error) {
            return;
        }
        error.textContent = (
            "Не удалось загрузить страницу расписания. "
            + "Проверьте соединение и попробуйте ещё раз."
        );
        error.hidden = false;
    }

    function updateFilterState(url) {
        const selectedType = new URL(url, window.location.href).searchParams.get(
            "lesson_type",
        );
        document.querySelectorAll("[data-schedule-filter]").forEach((button) => {
            const buttonType = new URL(
                button.dataset.url,
                window.location.href,
            ).searchParams.get("lesson_type");
            const isActive = buttonType === selectedType;
            button.parentElement?.classList.toggle("active", isActive);
            if (isActive) {
                button.setAttribute("aria-pressed", "true");
            } else {
                button.setAttribute("aria-pressed", "false");
            }
        });
    }

    async function loadSchedule(url, options = {}) {
        const {
            updateHistory = true,
        } = options;

        activeRequest?.abort();
        const request = new AbortController();
        activeRequest = request;
        setLoading(true);

        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                signal: request.signal,
            });

            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }
            if (!response.ok) {
                throw new Error(`Schedule request failed: ${response.status}`);
            }

            const template = document.createElement("template");
            template.innerHTML = (await response.text()).trim();
            const replacement = template.content.querySelector(
                "#schedule-results",
            );
            const currentResults = getResults();
            if (!replacement || !currentResults || activeRequest !== request) {
                throw new Error("Invalid schedule response");
            }

            currentResults.replaceWith(replacement);
            if (updateHistory) {
                window.history.pushState({}, "", url);
            }
            updateFilterState(url);
        } catch (error) {
            if (error.name !== "AbortError") {
                showRequestError();
            }
        } finally {
            if (activeRequest === request) {
                activeRequest = null;
                setLoading(false);
            }
        }
    }

    document.addEventListener("click", (event) => {
        const navigationLink = event.target.closest(
            "[data-schedule-page], [data-schedule-filter]",
        );
        if (navigationLink) {
            if (
                event.button !== 0
                || event.metaKey
                || event.ctrlKey
                || event.shiftKey
                || event.altKey
            ) {
                return;
            }
            event.preventDefault();
            const targetUrl = (
                navigationLink.dataset.url || navigationLink.href
            );
            loadSchedule(targetUrl);
            return;
        }

        const toggle = event.target.closest("[data-schedule-toggle]");
        if (!toggle) {
            return;
        }
        const item = toggle.closest(".schedule-item");
        const isExpanded = item?.classList.toggle("active") || false;
        toggle.setAttribute("aria-expanded", String(isExpanded));
        window.setTimeout(() => window.ScrollTrigger?.refresh(), 500);
    }, true);

    document.addEventListener("keydown", (event) => {
        const toggle = event.target.closest("[data-schedule-toggle]");
        if (!toggle || !["Enter", " "].includes(event.key)) {
            return;
        }
        event.preventDefault();
        toggle.click();
    });

    window.addEventListener("popstate", () => {
        loadSchedule(window.location.href, {
            updateHistory: false,
        });
    });

    updateFilterState(window.location.href);
})();
