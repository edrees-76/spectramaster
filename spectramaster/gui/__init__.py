"""SpectraMaster graphical interface (PySide6).

Entry point: ``spectramaster.gui.main()`` (or ``python -m spectramaster.gui``).
"""


def main(argv=None) -> int:
    from .app import main as _main
    return _main(argv)


__all__ = ["main"]
