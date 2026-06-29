# tipmip-gwl

Re-index TIPMIP ramp-up output from a **time** axis onto a common **global warming level (GWL)** axis.

1. Weighted annual-mean GMSAT for ramp-up and piControl
2. 31-yr centred piControl baseline at the branch year
3. Anomaly → smooth → enforce monotonicity → invert onto a common T-grid

```bash
pip install -e ".[plot]"
tipmip-gwl-diagnostics --up2p0-dir <dir> --picontrol-dir <dir> --plot
```
