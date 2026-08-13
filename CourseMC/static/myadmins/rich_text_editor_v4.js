(function () {
    "use strict";

    function getCookie(name) {
        const prefix = name + "=";
        return document.cookie
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith(prefix))
            ?.slice(prefix.length) || "";
    }

    function initialiseEditor(textarea) {
        if (!window.Jodit || textarea.dataset.editorInitialised === "true") {
            return;
        }

        textarea.dataset.editorInitialised = "true";
        const uploadUrl = textarea.dataset.editorUploadUrl;
        const editor = Jodit.make(textarea, {
            language: "ru",
            theme: (
                document.documentElement.classList.contains("dark")
                || document.body.classList.contains("dark")
                || document.body.classList.contains("black")
            ) ? "dark" : "default",
            height: 430,
            minHeight: 280,
            toolbarAdaptive: true,
            toolbarSticky: true,
            showCharsCounter: true,
            showWordsCounter: true,
            askBeforePasteHTML: false,
            askBeforePasteFromWord: false,
            defaultActionOnPaste: "insert_clear_html",
            buttons: [
                "source", "|", "undo", "redo", "|", "paragraph", "brush",
                "|", "bold", "italic", "underline", "strikethrough", "|",
                "ul", "ol", "outdent", "indent", "|", "left", "center",
                "right", "justify", "|", "link", "image", "table", "hr",
                "|", "eraser", "copyformat", "fullsize", "preview"
            ],
            uploader: uploadUrl ? {
                url: uploadUrl,
                method: "POST",
                format: "json",
                filesVariableName: function () { return "files"; },
                headers: {"X-CSRFToken": decodeURIComponent(getCookie("csrftoken"))},
                isSuccess: function (response) { return response.success === true; },
                getMessage: function (response) { return response.message || ""; },
                process: function (response) {
                    return {
                        files: response.files || [],
                        path: response.path || "",
                        baseurl: response.baseurl || "",
                        error: response.success ? 0 : 1,
                        msg: response.message || ""
                    };
                }
            } : undefined
        });

        function syncEditorTheme() {
            const dark = (
                document.documentElement.classList.contains("dark")
                || document.body.classList.contains("dark")
                || document.body.classList.contains("black")
            );
            editor.container.classList.toggle("jodit_theme_dark", dark);
            editor.container.classList.toggle("jodit_theme_default", !dark);
        }
        syncEditorTheme();
        window.setTimeout(syncEditorTheme, 500);
        new MutationObserver(syncEditorTheme).observe(
            document.documentElement,
            {attributes: true, attributeFilter: ["class"]}
        );

        const form = textarea.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                textarea.value = editor.value;
            });
        }
    }

    function initialiseAll(root) {
        (root || document)
            .querySelectorAll("textarea.cm-rich-text-editor")
            .forEach(initialiseEditor);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            window.setTimeout(function () { initialiseAll(document); }, 100);
        });
    } else {
        window.setTimeout(function () { initialiseAll(document); }, 100);
    }

    document.addEventListener("formset:added", function (event) {
        initialiseAll(event.target);
    });
})();
