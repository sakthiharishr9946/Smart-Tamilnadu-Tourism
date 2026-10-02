import streamlit as st


def load_theme():
    """
    Apply global Streamlit theme adjustments.

    Detailed application styling is handled through:
    ui/styles/main.css
    ui/styles/cards.css
    ui/styles/navbar.css
    ui/styles/responsive.css
    """

    st.markdown(
        """
        <style>
        :root {
            /* Apple-inspired light palette, tuned to the app's teal brand accent */
            --accent: #0f766e;
            --accent-strong: #0b5c56;
            --accent-soft: #e6f7f4;
            --accent-gradient: linear-gradient(135deg, #14b8a6 0%, #0f766e 55%, #0b5c56 100%);

            --bg: #f5f5f7;
            --surface: #ffffff;
            --surface-alt: #fbfbfd;

            --text-primary: #1d1d1f;
            --text-secondary: #6e6e73;
            --text-tertiary: #94a3b8;

            --border: #e5e5ea;
            --border-strong: #d2d2d7;

            --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.04);
            --shadow-sm: 0 4px 14px rgba(0, 0, 0, 0.05);
            --shadow-md: 0 10px 30px rgba(0, 0, 0, 0.07);
            --shadow-lg: 0 20px 48px rgba(0, 0, 0, 0.10);

            --radius-sm: 12px;
            --radius-md: 18px;
            --radius-lg: 24px;
            --radius-pill: 999px;

            --ease: cubic-bezier(0.16, 1, 0.3, 1);
        }

        html,
        body {
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "SF Pro Display",
                "SF Pro Text",
                "Segoe UI",
                Inter,
                Roboto,
                Helvetica,
                Arial,
                sans-serif;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        body {
            background: var(--bg);
            color: var(--text-primary);
        }

        footer,
        #MainMenu {
            visibility: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
