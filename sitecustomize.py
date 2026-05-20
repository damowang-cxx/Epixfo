"""Local Python startup tweaks for this workspace.

Some Windows/Anaconda environments can hang when ``platform`` queries WMI while
libraries are importing. SQLAlchemy asks ``platform.machine()`` during import,
so keep that path deterministic for local development and tests.
"""

import platform


platform.machine = lambda: "AMD64"
platform.system = lambda: "Windows"
