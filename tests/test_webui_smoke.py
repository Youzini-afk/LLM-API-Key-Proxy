from pathlib import Path
import shutil
import subprocess

import pytest


def test_webui_app_module_imports_cleanly():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")

    app_js = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "proxy_app"
        / "webui"
        / "js"
        / "app.js"
    )

    script = f"""
globalThis.window = {{
  location: {{ origin: 'http://localhost', hash: '#/' }},
  addEventListener() {{}},
}};

const storage = new Map();
globalThis.localStorage = {{
  getItem(key) {{ return storage.has(key) ? storage.get(key) : ''; }},
  setItem(key, value) {{ storage.set(key, String(value)); }},
  removeItem(key) {{ storage.delete(key); }},
}};
window.localStorage = globalThis.localStorage;

globalThis.Node = class {{}};
globalThis.document = {{
  addEventListener() {{}},
  querySelector() {{ return null; }},
  getElementById() {{ return null; }},
  createElement() {{ return {{ appendChild() {{}}, setAttribute() {{}}, style: {{}}, className: '', innerHTML: '' }}; }},
  createElementNS() {{ return {{ appendChild() {{}}, setAttribute() {{}}, style: {{}}, className: '', innerHTML: '' }}; }},
  createTextNode(text) {{ return {{ textContent: String(text) }}; }},
  body: {{ appendChild() {{}} }},
}};

await import({app_js.as_uri()!r});
"""

    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
