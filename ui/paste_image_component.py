from pathlib import Path

import streamlit.components.v1 as components


_COMPONENT_DIR = Path(__file__).resolve().parent / "components" / "paste_image"
_paste_image_component = components.declare_component(
    "paste_image",
    path=str(_COMPONENT_DIR),
)


def paste_image_box(key: str):
    """Return pasted image metadata from a small local Streamlit component."""
    return _paste_image_component(default=None, key=key)
