"""Convert a Fraudit .tbl table into intermediate files, using a restricted unpickler.

A .tbl file is gzip-compressed and contains a stream of Python 2 pickles:
  [0] format header, [1] table header (column definitions), [2:] flat stream of cell values.

Only whitelisted classes can be loaded, so a tampered file cannot run arbitrary code.

Usage:
    python -I src/parse_tbl.py data/je.tbl data/je
Writes data/je.cols.json (column names) and data/je.vals.pkl (flat value list).
"""
import gzip
import json
import pickle
import sys


class Col:
    """Stand-in for fraudit.base.Column: keeps only its attribute dict."""
    def __init__(self, *args):
        pass

    def __setstate__(self, state):
        self.__dict__.update(state)


class DT:
    """Stand-in for fraudit.base.Calendar.DateTime: keeps the raw value."""
    def __init__(self, s=None):
        self.s = s


BUILTINS = {'long': int, 'unicode': str, 'int': int, 'float': float, 'str': str}


class SafeUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'fraudit.base' and name in ('Column', 'Column\n_ColumnLoader'):
            return Col  # the second spelling appears as-is in the course file
        if module == 'fraudit.base.Column' and name == '_ColumnLoader':
            return Col
        if module == 'fraudit.base.Calendar' and name == 'DateTime':
            return DT
        if module == '__builtin__' and name in BUILTINS:
            return BUILTINS[name]
        raise pickle.UnpicklingError(f'blocked: {module}.{name}')


def open_table(path):
    with open(path, 'rb') as f:
        gzipped = f.read(2) == b'\x1f\x8b'
    return gzip.open(path, 'rb') if gzipped else open(path, 'rb')


def main(src, out_prefix):
    objs = []
    with open_table(src) as f:
        while True:
            try:
                objs.append(SafeUnpickler(f, encoding='utf-8').load())
            except EOFError:
                break

    header = objs[1]
    cols = [c.__dict__['name'] for c in header['columns']]
    vals = [v.s if isinstance(v, DT) else v for v in objs[2:]]

    with open(out_prefix + '.cols.json', 'w', encoding='utf-8') as f:
        json.dump([cols], f, ensure_ascii=False)
    with open(out_prefix + '.vals.pkl', 'wb') as f:
        pickle.dump(vals, f)
    print(f'{len(cols)} columns, {len(vals)} values -> {out_prefix}.*')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
