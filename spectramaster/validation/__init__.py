"""Reproducible validation baseline for the analysis engine (Release A, stage one).

This package measures how the *existing* peak search / fitting and nuclide identification
behave on spectra whose truth is known:

* ``synthetic``  - seeded HPGe and NaI spectra (Poisson counts) with known peaks, including
                   deliberate model mismatch (low-energy tails, Compton edges, low counts);
* ``reference``  - the public IAEA G-1 and EML (Sanderson) test spectra, read from a local
                   directory when it exists (they are not redistributed in this repository);
* ``acceptance`` - acceptance limits fixed *before* the first benchmark run (see the git
                   history of that module) with the reasoning behind each limit;
* ``benchmark``  - runs everything and writes a JSON + Markdown report.

Nothing here is used by the GUI or the converter, and nothing here claims laboratory
validation: passing synthetic tests is evidence about the algorithm, not about a laboratory
measurement chain.
"""
