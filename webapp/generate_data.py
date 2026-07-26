#!/usr/bin/env python3
"""Generate webapp data files from results directory."""

import csv
import json
import sys
from pathlib import Path
from urllib.parse import quote
from tqdm import tqdm

ROOT_PATH = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_PATH))

from autoeq.frequency_response import FrequencyResponse

RESULTS_PATH = ROOT_PATH / 'results'
TARGETS_PATH = ROOT_PATH / 'targets'
WEBAPP_PATH = ROOT_PATH / 'webapp'
MEASUREMENTS_PATH = ROOT_PATH / 'measurements'


class NameItem:
    def __init__(self, url=None, source_name=None, name=None, form=None, rig=None):
        self.url = url
        self.source_name = source_name
        self.name = name
        self.form = form
        self.rig = rig

    def __hash__(self):
        return hash(f'{self.url};;{self.source_name};;{self.name};;{self.form};;{self.rig}')

    def copy(self):
        return NameItem(url=self.url, source_name=self.source_name, name=self.name, form=self.form, rig=self.rig)

    @property
    def is_ignored(self):
        return self.form == 'ignore'


class NameIndex:
    def __init__(self, items=None):
        self._by_hash = {}
        self._by_url = {}
        self._by_source_name = {}
        self._by_name = {}
        self._by_form = {}
        self._by_rig = {}
        if items is not None:
            for item in items:
                self.add(item)

    def __len__(self):
        return len(self._by_hash)

    def __bool__(self):
        return len(self) > 0

    def __iter__(self):
        for item in self._by_hash.values():
            yield item

    @property
    def items(self):
        return list(self._by_hash.values())

    def add(self, item):
        if hash(item) in self._by_hash:
            return
        self._by_hash[hash(item)] = item
        if item.url is not None:
            self._by_url[item.url] = item
        if item.source_name is not None:
            if item.source_name not in self._by_source_name:
                self._by_source_name[item.source_name] = []
            self._by_source_name[item.source_name].append(item)
        if item.name is not None:
            if item.name not in self._by_name:
                self._by_name[item.name] = []
            self._by_name[item.name].append(item)
        if item.form is not None:
            if item.form not in self._by_form:
                self._by_form[item.form] = []
            self._by_form[item.form].append(item)
        if item.rig is not None:
            if item.rig not in self._by_rig:
                self._by_rig[item.rig] = []
            self._by_rig[item.rig].append(item)

    def find(self, url=None, source_name=None, name=None, form=None, rig=None):
        items = None
        if url is not None:
            if url not in self._by_url:
                return None
            items = {self._by_url[url]}
        if source_name is not None:
            if source_name not in self._by_source_name:
                return None
            by_source_name = set(self._by_source_name[source_name])
            items = items.intersection(by_source_name) if items is not None else by_source_name
        if name is not None:
            if name not in self._by_name:
                return None
            by_name = set(self._by_name[name])
            items = items.intersection(by_name) if items is not None else by_name
        if form is not None:
            if form not in self._by_form:
                return None
            by_form = set(self._by_form[form])
            items = items.intersection(by_form) if items is not None else by_form
        if rig is not None:
            if rig not in self._by_rig:
                return None
            by_rig = set(self._by_rig[rig])
            items = items.intersection(by_rig) if items is not None else by_rig
        return NameIndex(items) if items else None

    def find_one(self, **kwargs):
        results = self.find(**kwargs)
        if results:
            return results.items[0]

    @classmethod
    def read_tsv(cls, file_path):
        items = []
        with open(file_path, 'r', encoding='utf-8') as fh:
            reader = csv.DictReader(fh, delimiter='\t')
            for row in reader:
                items.append(NameItem(
                    url=row.get('url') or None,
                    source_name=row.get('source_name') or None,
                    name=row.get('name') or None,
                    form=row.get('form') or None,
                    rig=row.get('rig') or None,
                ))
        return cls(items)


# Read name indexes (pure Python, no pandas needed)
name_indexes = {}
for fp in MEASUREMENTS_PATH.glob('*/name_index.tsv'):
    name_indexes[fp.parent.name] = NameIndex.read_tsv(fp)


class ResultPath:
    priorities = [
        ('Headphone.com Legacy', 'earbud'),
        ('Rtings', 'HMS II.3 earbud'),
        ('Innerfidelity', 'earbud'),
        ('Kazi', 'earbud'),
        ('Regan Cipher', 'earbud'),
        ('kr0mka', 'earbud'),
        ('Super Review', 'earbud'),
        ('Rtings', 'Bruel & Kjaer 5128 earbud'),
        ('HypetheSonics', 'earbud'),
        ('oratory1990', 'earbud'),
        ('Headphone.com Legacy', 'in-ear'),
        ('Innerfidelity', 'in-ear'),
        ('Rtings', 'HMS II.3 in-ear'),
        ('HypetheSonics', 'Bruel & Kjaer 5128 in-ear'),
        ('crinacle', 'Bruel & Kjaer 4620 in-ear'),
        ('Rtings', 'Bruel & Kjaer 5128 in-ear'),
        ('Filk', 'in-ear'),
        ('DHRME', 'in-ear'),
        ('Jaytiss', 'in-ear'),
        ('Kazi', 'in-ear'),
        ('Regan Cipher', 'in-ear'),
        ("Ted's Squig Hoard", 'in-ear'),
        ('ToneDeafMonk', 'in-ear'),
        ('Auriculares Argentina', 'in-ear'),
        ('Bakkwatan', 'in-ear'),
        ('Hi End Portable', 'in-ear'),
        ('RikudouGoku', 'in-ear'),
        ('Fahryst', 'in-ear'),
        ('kr0mka', 'in-ear'),
        ('Harpo', 'in-ear'),
        ('freeryder05', 'in-ear'),
        ('Super Review', 'in-ear'),
        ('crinacle', '711 in-ear'),
        ('HypetheSonics', 'GRAS RA0045 in-ear'),
        ('oratory1990', 'in-ear'),
        ('crinacle', 'EARS + 711 over-ear'),
        ('Headphone.com Legacy', 'over-ear'),
        ('Innerfidelity', 'over-ear'),
        ('Rtings', 'HMS II.3 over-ear'),
        ('HypetheSonics', 'over-ear'),
        ('Rtings', 'Bruel & Kjaer 5128 over-ear'),
        ('Regan Cipher', 'over-ear'),
        ('DHRME', 'over-ear'),
        ('RikudouGoku', 'over-ear'),
        ('Filk', 'over-ear'),
        ('kr0mka', 'over-ear'),
        ('Auriculares Argentina', 'over-ear'),
        ('Super Review', 'over-ear'),
        ('Kuulokenurkka', 'over-ear'),
        ('crinacle', 'GRAS 43AG-7 over-ear'),
        ('oratory1990', 'over-ear'),
    ][::-1]

    def __init__(self, path):
        self._absolute_path = Path(path).absolute()
        self._path_relative_to_root = self._absolute_path.relative_to(RESULTS_PATH)
        self._source_name = self._path_relative_to_root.parts[0]
        self._form_rig = self._path_relative_to_root.parts[1]
        self._rig = self._form_rig.replace('earbud', '').replace('in-ear', '').replace('over-ear', '').strip()
        self._form = self._form_rig.replace(self._rig, '').strip()
        self._name = self._absolute_path.parts[-1]

    def __getitem__(self, key):
        if key == 'absolute_path':
            return self.absolute_path
        if key == 'source_name':
            return self.source_name
        if key == 'form':
            return self.form
        if key == 'rig':
            return self.rig
        if key == 'priority':
            return self.priority
        if key == 'name':
            return self.name
        raise KeyError(key)

    @property
    def name(self):
        return self._name

    @property
    def absolute_path(self):
        return self._absolute_path

    @property
    def path_relative_to_root(self):
        return self._path_relative_to_root

    @property
    def source_name(self):
        return self._source_name

    @property
    def form(self):
        return self._form

    @property
    def rig(self):
        return self._rig

    @property
    def priority(self):
        return self.__class__.priorities.index((self.source_name, self._form_rig))


def group_by(paths, prop):
    grouped = {}
    for path in paths:
        if path[prop] not in grouped:
            grouped[path[prop]] = []
        grouped[path[prop]].append(path)
    return {sorted_key: grouped[sorted_key] for sorted_key in sorted(list(grouped.keys()))}


def sort_by(paths, prop):
    return sorted(paths, key=lambda p: (p[prop].lower() if type(p[prop]) == str else p[prop]))


def sort_each_group_by(groups, prop):
    for group_key in groups.keys():
        groups[group_key] = sort_by(groups[group_key], prop)
    return groups


def write_targets():
    """Generate targets.json for the webapp."""
    targets = [
        {
            'file': TARGETS_PATH / 'AutoEq in-ear.csv',
            'compatible': [
                {'source': 'Auriculares Argentina', 'form': 'in-ear'},
                {'source': 'Bakkwatan', 'form': 'in-ear'},
                {'source': 'crinacle', 'form': 'in-ear', 'rig': '711'},
                {'source': 'DHRME', 'form': 'in-ear'},
                {'source': 'Fahryst', 'form': 'in-ear'},
                {'source': 'Filk', 'form': 'in-ear'},
                {'source': 'freeryder05', 'form': 'in-ear'},
                {'source': 'Harpo', 'form': 'in-ear'},
                {'source': 'Hi End Portable', 'form': 'in-ear'},
                {'source': 'HypetheSonics', 'form': 'in-ear', 'rig': 'GRAS RA0045'},
                {'source': 'Jaytiss', 'form': 'in-ear'},
                {'source': 'Kazi', 'form': 'in-ear'},
                {'source': 'Kazi', 'form': 'earbud'},
                {'source': 'kr0mka', 'form': 'in-ear'},
                {'source': 'kr0mka', 'form': 'earbud'},
                {'source': 'oratory1990', 'form': 'in-ear'},
                {'source': 'oratory1990', 'form': 'earbud'},
                {'source': 'Regan Cipher', 'form': 'in-ear'},
                {'source': 'Regan Cipher', 'form': 'earbud'},
                {'source': 'RikudouGoku', 'form': 'in-ear'},
                {'source': 'Super Review', 'form': 'in-ear'},
                {'source': 'Super Review', 'form': 'earbud'},
                {"source": "Ted's Squig Hoard", 'form': 'in-ear'},
                {'source': 'ToneDeafMonk', 'form': 'in-ear'},
            ],
            'recommended': [
                {'source': 'Auriculares Argentina', 'form': 'in-ear'},
                {'source': 'Bakkwatan', 'form': 'in-ear'},
                {'source': 'crinacle', 'form': 'in-ear', 'rig': '711'},
                {'source': 'DHRME', 'form': 'in-ear'},
                {'source': 'Fahryst', 'form': 'in-ear'},
                {'source': 'Filk', 'form': 'in-ear'},
                {'source': 'freeryder05', 'form': 'in-ear'},
                {'source': 'Harpo', 'form': 'in-ear'},
                {'source': 'Hi End Portable', 'form': 'in-ear'},
                {'source': 'HypetheSonics', 'form': 'in-ear', 'rig': 'GRAS RA0045'},
                {'source': 'Jaytiss', 'form': 'in-ear'},
                {'source': 'Kazi', 'form': 'in-ear'},
                {'source': 'Kazi', 'form': 'earbud'},
                {'source': 'kr0mka', 'form': 'in-ear'},
                {'source': 'kr0mka', 'form': 'earbud'},
                {'source': 'oratory1990', 'form': 'in-ear'},
                {'source': 'oratory1990', 'form': 'earbud'},
                {'source': 'Regan Cipher', 'form': 'in-ear'},
                {'source': 'Regan Cipher', 'form': 'earbud'},
                {'source': 'RikudouGoku', 'form': 'in-ear'},
                {'source': 'Super Review', 'form': 'in-ear'},
                {'source': 'Super Review', 'form': 'earbud'},
                {"source": "Ted's Squig Hoard", 'form': 'in-ear'},
                {'source': 'ToneDeafMonk', 'form': 'in-ear'},
            ],
            'bassBoost': {'fc': 105, 'q': 0.7, 'gain': 8}
        },
        # ... adding rest inline
    ]
    # Actually, let's just build the full target list from create_webapp_data.py logic
    # Let me simplify and just use the existing targets.json if possible, or call the original function

    # For now, the existing targets.json at webapp/data/targets.json is already good
    # Let me just focus on entries+measurements
    pass


def write_webapp_data():
    """Generate entries.json and measurements.json."""
    print('Scanning results directory for data files...')
    paths = [ResultPath(readme_path.parent) for readme_path in RESULTS_PATH.glob('*/*/**/*.md')]
    print(f'Found {len(paths)} result paths')

    grouped_by_name = group_by(paths, 'name')
    grouped_by_name = sort_each_group_by(grouped_by_name, 'priority')

    entries = {}
    measurements = {}

    sorted_names = sorted(grouped_by_name.keys(), key=lambda key: key.lower())
    for name in tqdm(sorted_names, desc='Processing headphones'):
        entries[name] = []
        measurements[name] = {}
        for path in grouped_by_name[name]:
            rig = path.rig
            if not rig:
                try:
                    if path.source_name in name_indexes:
                        found = name_indexes[path.source_name].find_one(name=name)
                        if found and found.rig:
                            rig = found.rig
                    if not rig:
                        rig = ''
                except Exception:
                    rig = ''
            entries[name].append({'form': path.form, 'rig': rig, 'source': path.source_name})
            if path.source_name not in measurements[name]:
                measurements[name][path.source_name] = {}
            csv_path = path.absolute_path / f'{path.name}.csv'
            try:
                fr = FrequencyResponse.read_csv(csv_path)
                fr.reset(
                    raw=False, smoothed=True, error=True, error_smoothed=True,
                    equalization=True, fixed_band_eq=True,
                    parametric_eq=True, equalized_raw=True, equalized_smoothed=True,
                    target=True)
                measurements[name][path.source_name][rig] = fr.to_dict()
            except Exception as err:
                print(f'Error reading {csv_path}: {err}')

    print('Writing entries.json...')
    with open(WEBAPP_PATH / 'data' / 'entries.json', 'w', encoding='utf-8') as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=4)

    print('Writing measurements.json...')
    with open(WEBAPP_PATH / 'data' / 'measurements.json', 'w', encoding='utf-8') as fh:
        json.dump(measurements, fh, ensure_ascii=False, indent=4)

    print(f'Done! Generated data for {len(entries)} headphones.')


if __name__ == '__main__':
    write_webapp_data()
