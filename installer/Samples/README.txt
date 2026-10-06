SpectraMaster - sample spectra
==============================
Public example spectra from open-source projects, for trying out SpectraMaster (open, view,
analyse, convert). They are NOT certified reference measurements. Each file keeps the license
of the project it comes from; the license texts are in the "licenses" sub-folder.

File                              Format                     Content
--------------------------------  -------------------------  -------------------------------------------
Eu152_HPGe.spe                    ORTEC/IAEA ASCII SPE       Eu-152 calibration source, HPGe, 16384 ch
Eu152_HPGe.chn                    ORTEC CHN (MAESTRO)        the same spectrum converted by SpectraMaster
Eu152_HPGe.s0                     APTEC S0 v6.3              the same spectrum converted by SpectraMaster
Ba133_HPGe.cnf                    Canberra CAM (Genie CNF)   Ba-133 source, HPGe, 8192 ch
Environmental_HPGe_Alcatraz.spc   ORTEC integer SPC          outdoor measurement (K-40, U/Th series), HPGe
HPGe_test_spectrum.iec            IEC 1455 ASCII             synthetic HPGe test spectrum with Co-60 lines
Ba133_Cs137_CsI.spe               IAEA ASCII SPE             Ba-133 + Cs-137, Kromek D3S CsI (uncalibrated)
Co60_NaI.n42                      ANSI N42.42-2012           Co-60, generic 2x2" NaI base spectrum
Cs137_NaI.n42                     ANSI N42.42-2012           Cs-137, generic 2x2" NaI base spectrum
Background_NaI.n42                ANSI N42.42-2012           natural background, generic 2x2" NaI

Sources and licenses
--------------------
Eu152_HPGe.spe
    curie - https://github.com/jtmorrell/curie, examples/eu_calib_7cm.Spe (commit 261832fb)
    License: MIT (licenses/curie_MIT.txt).
Eu152_HPGe.chn, Eu152_HPGe.s0
    Converted from Eu152_HPGe.spe with SpectraMaster 1.0.0 (format conversion only).
    License: MIT, as the original (licenses/curie_MIT.txt).
Ba133_HPGe.cnf
    InterSpec - https://github.com/sandialabs/InterSpec,
    target/testing/test_data/CamLibrary/Ba-133.cnf (commit 24307caa)
    License: GNU LGPL 2.1 (licenses/InterSpec_LGPL-2.1.txt).
Environmental_HPGe_Alcatraz.spc   (original name Alcatraz14.Spc)
HPGe_test_spectrum.iec            (original name hpge_dummy_test_01.iec)
Ba133_Cs137_CsI.spe               (original name SGM102432.spe)
    becquerel (Lawrence Berkeley National Laboratory) - https://github.com/lbl-anp/becquerel,
    tests/samples/ (commit c8ef15ad)
    License: BSD-3-Clause-LBNL (licenses/becquerel_BSD-3-Clause-LBNL.txt).
Co60_NaI.n42, Cs137_NaI.n42, Background_NaI.n42
    (original names VGeneric_MNaI2x2_Co60.n42, VGeneric_MNaI2x2_Cs137.n42, VGeneric_MNaI2x2_Bgnd.n42)
    RASE (Lawrence Livermore National Laboratory) - https://github.com/llnl/RASE,
    baseSpectra/genericNaI/ (commit 7f8e0741)
    License: MIT (dual MIT / LGPL 2.1 project; licenses/RASE_MIT.txt).

Tips
----
* Double-click a file (if the file associations were installed) or drag it onto the window.
* Analyze > Peak search / nuclide identification works best on the calibrated HPGe spectra
  (Eu152, Ba133, Alcatraz). Ba133_Cs137_CsI.spe has no energy calibration: calibrate it first.
* The folder is read-only for normal users; copy files elsewhere before modifying them.
