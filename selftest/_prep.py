import sys, os

script_dir = sys.path[0]
top_dir = os.path.join(script_dir, '..')
src_dir = os.path.join(top_dir, 'src')

# to find the osmo_gsm_tester py module
sys.path.append(src_dir)

from osmo_gsm_tester import log

log.TestsTarget()
log.set_all_levels(log.L_DBG)

if '-v' in sys.argv:
    log.style_change(trace=True)

