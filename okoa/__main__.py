"""Einstiegspunkt.

Ohne Argumente startet die Oberflaeche, mit Argumenten die Kommandozeile.
"""

import sys

if len(sys.argv) > 1:
    from .cli import main

    sys.exit(main())
else:
    from .gui import starten

    sys.exit(starten())
