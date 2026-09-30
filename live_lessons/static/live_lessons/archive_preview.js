(() => {
    document.addEventListener("click", async (event) => {
        const button = event.target.closest("[data-archive-preview-url]");
        if (!button) return;

        const preview = button.closest(".lesson-chat-archive-card")?.querySelector(
            ".lesson-chat-archive-preview",
        );
        if (!preview) return;

        const opening = preview.hidden;
        preview.hidden = !opening;
        button.setAttribute("aria-expanded", String(opening));
        button.textContent = opening ? "Скрыть переписку" : "Показать переписку";
        if (!opening || preview.dataset.loaded === "true" || preview.dataset.loading === "true") return;

        preview.dataset.loading = "true";
        preview.textContent = "Загружаем историю чата…";
        try {
            const response = await fetch(button.dataset.archivePreviewUrl, {
                cache: "no-store",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (response.redirected) {
                window.location.assign(response.url);
                return;
            }
            if (!response.ok) throw new Error(`Archive request failed: ${response.status}`);
            preview.innerHTML = await response.text();
            preview.dataset.loaded = "true";
        } catch (_error) {
            preview.textContent = "Не удалось загрузить переписку. Попробуйте ещё раз.";
        } finally {
            delete preview.dataset.loading;
        }
    });
})();
