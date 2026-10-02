import streamlit.components.v1 as components

# Runs inside Streamlit's component iframe, which is same-origin, so it can
# reach into the parent document to animate elements Streamlit itself
# rendered. Elements marked class="reveal" fade/slide in the first time they
# scroll into view. If cross-frame access is ever blocked, the app still
# works: reveal.in-view is only required by CSS scoped under
# body.js-scroll-ready, so unstyled elements simply stay visible.
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

    function scan() {
        var items = doc.querySelectorAll(".reveal:not(.reveal-bound)");
        items.forEach(function (el) {
            el.classList.add("reveal-bound");
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
