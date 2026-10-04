import streamlit.components.v1 as components

# Runs inside Streamlit's component iframe, which is same-origin, so it can
# reach into the parent document to animate elements Streamlit itself
# rendered. Elements marked class="reveal" fade/slide in the first time they
# scroll into view; common page sections (cards, metrics, timeline stops,
# panels) get a subtle 3D tilt-in (.reveal-3d) on every page. If
# cross-frame access is ever blocked, the app still works: both states are
# only styled under body.js-scroll-ready, so elements simply stay visible.
_SCROLL_REVEAL_HTML = """
<script>
(function () {
    try {
        var doc = window.parent.document;
        var ParentIntersectionObserver = window.parent.IntersectionObserver;
        var ParentMutationObserver = window.parent.MutationObserver;
    } catch (err) {
        return;
    }

    doc.body.classList.add("js-scroll-ready");

    var observer = new ParentIntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add("in-view");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12, rootMargin: "0px 0px -60px 0px" });

    // Page sections that get the 3D scroll-in on every page, without each
    // page having to mark them. Only blocks below the first screen animate,
    // so nothing already visible flickers when Streamlit reruns.
    var SECTIONS = [
        ".section-title", ".info-card", ".timeline-item", ".timeline-break",
        ".festival-row", ".place-photo", ".planner-panel-title",
        "[data-testid='stMetric']", "[data-testid='stExpander']",
        "[data-testid='stAlert']", "[data-testid='stVerticalBlockBorderWrapper']",
        "[class*='st-key-planner_panel']", ".stPlotlyChart", ".place-card"
    ].join(",");

    function scan() {
        var items = doc.querySelectorAll(".reveal:not(.reveal-bound)");
        items.forEach(function (el) {
            el.classList.add("reveal-bound");
            observer.observe(el);
        });
        var fold = window.parent.innerHeight;
        doc.querySelectorAll(SECTIONS).forEach(function (el) {
            if (el.classList.contains("reveal-bound") || el.classList.contains("reveal")) return;
            el.classList.add("reveal-bound");
            if (el.closest(".reveal-3d") || el.getBoundingClientRect().top < fold) return;
            el.classList.add("reveal-3d");
            observer.observe(el);
        });
    }

    scan();

    var mutationObserver = new ParentMutationObserver(scan);
    mutationObserver.observe(doc.body, { childList: true, subtree: true });
})();
</script>
"""


def inject_scroll_reveal():
    components.html(_SCROLL_REVEAL_HTML, height=0, width=0)
