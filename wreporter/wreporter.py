"""Wreporter — Reflex 앱 엔트리포인트."""

import reflex as rx

# 페이지 등록을 위해 import
import wreporter.pages.index  # noqa: F401
import wreporter.pages.admin  # noqa: F401

app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="teal",
        radius="medium",
    ),
    style={
        "font_family": "'IBM Plex Sans KR', -apple-system, sans-serif",
        "background": "#0a0a0f",
        "color": "#e8e8f0",
        "::selection": {
            "background": "rgba(19, 222, 185, 0.3)",
        },
    },
)
