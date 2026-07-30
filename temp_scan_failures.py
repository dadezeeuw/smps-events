import re
import pathlib
import collections
import datetime

p = pathlib.Path('scraper-task-log.txt')
lines = p.read_text(encoding='utf-8', errors='replace').splitlines()


def parse_date(s):
    return datetime.datetime.strptime(s, '%a %m/%d/%Y')

excluded_start = parse_date('Tue 07/27/2026')
excluded_end = parse_date('Thu 07/29/2026')
counts = collections.Counter()
dates = collections.defaultdict(list)
cur_run = None

for line in lines:
    m = re.match(r'^Run started:\s+(\w{3}\s+\d{2}/\d{2}/\d{4})', line)
    if m:
        cur_run = parse_date(m.group(1))
        continue
    if cur_run is None:
        continue
    if excluded_start <= cur_run <= excluded_end:
        continue
    if 'Failed to load' in line:
        m2 = re.search(r'Failed to load (.+?):', line)
        if m2:
            chap = m2.group(1).strip()
            counts[chap] += 1
            dates[chap].append(cur_run)
    elif 'Load attempt' in line and 'failed for' in line:
        m2 = re.search(r'failed for (.+?):', line)
        if m2:
            chap = m2.group(1).strip()
            counts[chap] += 1
            dates[chap].append(cur_run)

print('REPEATED FAILURES OUTSIDE EXCLUDED WINDOW')
for chap, count in counts.most_common():
    if count >= 2:
        ds = sorted(set(dates[chap]))
        print(f'{chap}\t{count}\t{len(ds)}\t{ds}')
