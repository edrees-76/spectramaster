import multiprocessing
import sys
from spectramaster.cli import main
multiprocessing.freeze_support()   # archive index uses a process pool
sys.exit(main())
