import os
import sys

__slicer_module__ = os.path.dirname(os.path.abspath(__path__[0]))
# print "Path to module: %s" % __slicer_module__

import _ssl  #JC hack for pg8000v1.08

try:
    import pg8000
except ImportError:
    pg8kDir = [os.path.join(__slicer_module__, 'Resources', 'Python', 'pg8000')]
    newSysPath = pg8kDir + sys.path
    sys.path = newSysPath
    import pg8000

sql = pg8000.DBAPI
