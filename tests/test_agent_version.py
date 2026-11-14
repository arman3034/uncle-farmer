"""The Java agent and the Python client must agree on the wire protocol.

StateServer.VERSION says what the jar can do. Every AGENT_* gate in runner.py says what the Python
client expects before sending a command. If Python expects a newer protocol than the jar provides,
the app can ship commands the agent does not understand; comparing the two here makes that a red
test instead of a failed run.
"""

import re
from pathlib import Path

from unclefarmer import messages
from unclefarmer.engine import runner

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "agent" / "src" / "unclefarmer" / "agent" / "StateServer.java"


def _java_version() -> int:
    text = JAVA.read_text(encoding="utf-8")
    found = re.search(r"static\s+final\s+int\s+VERSION\s*=\s*(\d+)\s*;", text)
    assert found is not None, "StateServer.VERSION not found in %s" % JAVA
    return int(found.group(1))


def _python_gates() -> dict[str, int]:
    gates = {name: value for name, value in vars(runner).items()
             if name.startswith("AGENT_") and type(value) is int}
    gates.update({"messages." + name: value for name, value in vars(messages).items()
                  if name.startswith("AGENT_") and type(value) is int})
    assert gates, "no AGENT_* version gates found"
    return gates


def test_java_agent_version_covers_every_python_gate() -> None:
    version = _java_version()
    gates = _python_gates()
    newest, needed = max(gates.items(), key=lambda pair: pair[1])
    assert version >= needed, (
        "StateServer.VERSION is %d but Python expects %s = %d: ship a newer agent jar or lower the gate"
        % (version, newest, needed))


def test_automatic_login_has_its_own_protocol_version() -> None:
    from unclefarmer.engine.runner import AGENT_LOGIN
    assert AGENT_LOGIN == _java_version()
