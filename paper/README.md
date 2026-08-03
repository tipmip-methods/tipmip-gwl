# Paper figures and tables

Committed outputs: [`figures/`](figures/), [`tables/`](tables/).

**Full reproduction guide** (staged data layout, `build_all.py`, script ↔ figure mapping):
[`docs/paper_reproduction.md`](../docs/paper_reproduction.md).

Quick start (requires TIPMIP data on disk):

```bash
pip install -e ".[paper]"
python paper/build_all.py   # defaults to ~/data/tipmip/ — see --help
```
