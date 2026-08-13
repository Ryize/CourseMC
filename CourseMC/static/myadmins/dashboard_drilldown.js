(function () {
    "use strict";

    function attachDrilldown(wrapper) {
        if (wrapper.dataset.drilldownReady === "true") {
            return true;
        }

        const canvas = wrapper.querySelector("canvas.chart");
        if (!canvas || !window.Chart || !Chart.getChart(canvas)) {
            return false;
        }

        let links = [];
        try {
            links = JSON.parse(wrapper.dataset.chartLinks || "[]");
        } catch (_error) {
            return true;
        }
        if (!links.length) {
            return true;
        }

        wrapper.dataset.drilldownReady = "true";
        canvas.classList.add("cm-chart-clickable");
        canvas.title = "Нажмите на сегмент, чтобы открыть связанные записи";
        canvas.addEventListener("click", function (event) {
            const chart = Chart.getChart(canvas);
            const points = chart.getElementsAtEventForMode(
                event,
                "nearest",
                {intersect: true},
                true
            );
            if (!points.length) {
                return;
            }
            const target = links[points[0].index];
            if (target) {
                window.location.assign(target);
            }
        });
        return true;
    }

    function initialiseDrilldowns(attempt) {
        const wrappers = Array.from(document.querySelectorAll(".cm-drilldown-chart"));
        const waiting = wrappers.some((wrapper) => !attachDrilldown(wrapper));
        if (waiting && attempt < 20) {
            window.setTimeout(function () {
                initialiseDrilldowns(attempt + 1);
            }, 150);
        }
    }

    window.addEventListener("load", function () {
        initialiseDrilldowns(0);
    });
})();
