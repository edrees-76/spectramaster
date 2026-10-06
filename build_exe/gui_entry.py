import multiprocessing
import sys
from spectramaster.gui.app import main
multiprocessing.freeze_support()   # archive index uses a process pool
sys.exit(main(sys.argv))
