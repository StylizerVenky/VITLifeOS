"""Local storage and calculations for VIT Life OS. Python standard library only."""
import csv
import hashlib
import hmac
import math
import re
import secrets
from datetime import date
from pathlib import Path
from contextlib import contextmanager
import os
import tempfile
import threading
try:
    import fcntl
except ImportError:
    fcntl = None

_LOCK = threading.RLock()

KINDS = ('Expenses', 'Courses', 'Time', 'Wishlist', 'Notes', 'Deadlines', 'Attendance')
FIELDS = {
    'Expenses': ('Date', 'Category', 'Amount', 'Description'),
    'Courses': ('Subject', 'Credits', 'Marks', 'Target', 'TargetMarks'),
    'Time': ('Date', 'Activity', 'Hours', 'Type'),
    'Wishlist': ('Item', 'Price', 'NeedScore', 'Added'),
    'Notes': ('Date', 'Note'),
    'Deadlines': ('Title', 'Due', 'Course', 'Status'),
    'Attendance': ('Subject', 'Attended', 'Held', 'Threshold'),
}

def number(value, low, high, label):
    try:
        n = float(value)
    except (ValueError, TypeError):
        raise ValueError(f'{label}: enter a number.') from None
    if not math.isfinite(n) or not low <= n <= high:
        raise ValueError(f'{label}: use a value from {low:g} to {high:g}.')
    return n

def validate(kind, values):
    if kind not in KINDS:
        raise ValueError('Unknown notebook.')
    defaults = {'TargetMarks': 90, 'Added': str(date.today())}
    data = {k: str(defaults[k] if values.get(k) in (None, '') else values[k]).strip() if k in defaults
            else str(values.get(k, '')).strip() for k in FIELDS[kind]}
    for key, value in data.items():
        if not value and key not in ('Description', 'Course'):
            raise ValueError(f'Please fill in {key}.')
        if len(value) > 4000:
            raise ValueError(f'{key} is too long (maximum 4000 characters).')
    for key in ('Date', 'Due', 'Added'):
        if key in data:
            try:
                date.fromisoformat(data[key])
            except ValueError:
                raise ValueError(f'{key}: use YYYY-MM-DD, for example {date.today()}.') from None
    bounds = {'Amount': (.01, 10000000), 'Credits': (.5, 20), 'Marks': (0, 100),
              'TargetMarks': (0, 100), 'Hours': (.01, 24), 'Price': (0, 10000000), 'NeedScore': (1, 10),
              'Attended': (0, 10000), 'Held': (0, 10000), 'Threshold': (1, 99)}
    for key, (low, high) in bounds.items():
        if key in data:
            n = number(data[key], low, high, key)
            if key in ('Attended', 'Held', 'NeedScore') and n != int(n):
                raise ValueError(f'{key}: enter a whole number.')
            data[key] = n
    if kind == 'Wishlist' and date.fromisoformat(data['Added']) > date.today():
        raise ValueError('The wish date cannot be in the future.')
    if kind == 'Attendance' and data['Attended'] > data['Held']:
        raise ValueError('Attended classes cannot exceed classes held.')
    for key, choices in {'Target': ('S', 'A', 'B', 'C', 'D', 'E', 'Pass'),
                         'Status': ('To do', 'In progress', 'Done'),
                         'Type': ('Focused', 'Wandering', 'Rest', 'Classes')}.items():
        if key in data and data[key] not in choices:
            raise ValueError(f'Choose a valid {key}.')
    return data

def attendance_plan(attended, held, threshold=75):
    ratio = threshold / 100
    pct = 100 * attended / held if held else 0
    if attended < ratio * held:
        needed = math.ceil((ratio * held - attended) / (1 - ratio) - 1e-9)
        return pct, f'Attend the next {needed} classes to reach {threshold:g}%.'
    can_miss = max(0, math.floor(attended / ratio - held + 1e-9))
    return pct, f'You can miss {can_miss} more classes at a {threshold:g}% target.'


RECORD_COLUMNS = list(dict.fromkeys(['id', 'User', 'Kind'] + [key for columns in FIELDS.values() for key in columns]))
USER_COLUMNS = ['name', 'salt', 'digest', 'budget']

class Store:
    """Lists/dictionaries backed by CSV files; atomic replacement, never truncation.

    A process-wide lock protects Streamlit sessions. Advisory file locks also
    protect separate processes on macOS/Linux. Windows uses the thread lock.
    """
    def __init__(self, path):
        path = Path(path)
        # Accept the old Store(file_path) convention for the migration and tests.
        self.root = path if not path.suffix else path.parent
        self.root.mkdir(parents=True, exist_ok=True)
        with self.guard():
            self._migrate_legacy()
            for name, columns in [('users.csv', USER_COLUMNS), ('records.csv', RECORD_COLUMNS)]:
                if not (self.root/name).exists():
                    self._write(name, columns, [])
                self._read(name, columns)

    @contextmanager
    def guard(self):
        with _LOCK, (self.root/'storage_lock.txt').open('a') as lock:
            if fcntl:
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def _read(self, name, columns):
        try:
            with (self.root/name).open(newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, strict=True)
                if reader.fieldnames != columns:
                    raise ValueError('Unexpected CSV columns')
                rows = list(reader)
                if any(None in r or any(v is None for v in r.values()) for r in rows):
                    raise ValueError('Incomplete CSV row')
                return rows
        except (csv.Error, UnicodeError, ValueError) as exc:
            raise ValueError(f'{name} is damaged or uses another format. Keep a backup and restore a valid copy. It has not been overwritten. ({exc})') from None

    def _write(self, name, columns, rows):
        # A same-directory temporary file makes the final replace atomic.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w', newline='', encoding='utf-8',
                                             dir=self.root, delete=False) as f:
                temporary = Path(f.name)
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.root/name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _migrate_legacy(self):
        old = self.root/'campus_cafe.sqlite3'
        if (self.root/'users.csv').exists() or not old.exists():
            return
        # Read-only, one-time bridge; the running application stores only CSV.
        import sqlite3
        import json
        db = sqlite3.connect(old.resolve().as_uri()+'?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        try:
            users = [dict(r) for r in db.execute('SELECT name,salt,digest,budget FROM users')]
            records = []
            for r in db.execute('SELECT id,owner,kind,payload FROM records'):
                payload = validate(r['kind'], json.loads(r['payload']))
                records.append(self._record(r['id'], r['owner'], r['kind'], payload))
            # users.csv is the completion marker; retries before this write rebuild
            # the same records safely. The source database is never modified.
            self._write('records.csv', RECORD_COLUMNS, records)
            self._write('users.csv', USER_COLUMNS, users)
        finally:
            db.close()

    def _record(self, record_id, owner, kind, data):
        return {key: {'id':record_id, 'User':owner, 'Kind':kind, **data}.get(key, '') for key in RECORD_COLUMNS}

    def _records(self):
        rows = self._read('records.csv', RECORD_COLUMNS)
        seen = set()
        for r in rows:
            try:
                record_id = int(r['id'])
                if record_id <= 0 or record_id in seen or not r['User']:
                    raise ValueError('Invalid or repeated record ID')
                seen.add(record_id)
                validate(r['Kind'], r)
            except (ValueError, KeyError) as exc:
                raise ValueError(f'records.csv contains an invalid entry: {exc}. Original file kept.') from None
        return rows

    def _users(self):
        rows = self._read('users.csv', USER_COLUMNS)
        seen = set()
        for r in rows:
            try:
                if not r['name'] or r['name'] in seen or len(bytes.fromhex(r['salt'])) != 16 or len(bytes.fromhex(r['digest'])) != 32:
                    raise ValueError('Invalid account fields')
                seen.add(r['name'])
                number(r['budget'], 1, 10000000, 'Budget')
            except ValueError:
                raise ValueError('users.csv contains invalid account data. Original file kept.') from None
        return rows

    def register(self, name, password):
        name = name.strip().lower()
        if not re.fullmatch(r'[a-z0-9_.-]{3,30}', name):
            raise ValueError('Use 3–30 letters, numbers, dots, underscores or hyphens for your username.')
        if len(password) < 8:
            raise ValueError('Choose a password with at least 8 characters.')
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 300000).hex()
        with self.guard():
            rows = self._users()
            if any(r['name'] == name for r in rows):
                raise ValueError('That username is already taken.')
            rows.append(dict(name=name, salt=salt, digest=digest, budget=5000))
            self._write('users.csv', USER_COLUMNS, rows)
        return name

    def login(self, name, password):
        with self.guard():
            row = next((r for r in self._users() if r['name'] == name.strip().lower()), None)
        if not row:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(row['salt']), 300000).hex()
        return hmac.compare_digest(digest, row['digest'])

    def rows(self, owner, kind=None):
        with self.guard():
            return sorted([dict(id=int(r['id']), kind=r['Kind'], **validate(r['Kind'], r))
                           for r in self._records() if r['User'] == owner and (kind is None or r['Kind'] == kind)],
                          key=lambda r:r['id'], reverse=True)

    def save(self, owner, kind, values, record_id=None):
        data = validate(kind, values)
        with self.guard():
            if not any(r['name'] == owner for r in self._users()):
                raise ValueError('Sign in to an existing account first.')
            rows = self._records()
            if kind in ('Courses', 'Attendance'):
                if any(r['User'] == owner and r['Kind'] == kind and int(r['id']) != record_id
                       and r['Subject'].casefold() == data['Subject'].casefold() for r in rows):
                    raise ValueError('This subject already exists. Edit it instead.')
            if record_id is not None:
                index = next((i for i,r in enumerate(rows) if int(r['id']) == record_id and r['User'] == owner and r['Kind'] == kind), None)
                if index is None:
                    raise ValueError('This record is no longer available.')
                rows[index] = self._record(record_id, owner, kind, data)
            else:
                record_id = max((int(r['id']) for r in rows), default=0)+1
                rows.append(self._record(record_id, owner, kind, data))
            self._write('records.csv', RECORD_COLUMNS, rows)
        return record_id

    def delete(self, owner, ids):
        with self.guard():
            rows = self._records()
            self._write('records.csv', RECORD_COLUMNS, [r for r in rows if not (r['User'] == owner and int(r['id']) in ids)])

    def budget(self, owner, value=None):
        with self.guard():
            rows = self._users()
            row = next((r for r in rows if r['name'] == owner), None)
            if row is None:
                raise ValueError('Account is no longer available. Sign in again.')
            if value is not None:
                row['budget'] = number(value, 1, 10000000, 'Budget')
                self._write('users.csv', USER_COLUMNS, rows)
            return float(row['budget'])

    def summary(self, owner, today=None):
        today = today or date.today()
        rows = self.rows(owner)
        spent = sum(r['Amount'] for r in rows if r['kind'] == 'Expenses' and r['Date'][:7] == today.isoformat()[:7] and r['Date'] <= str(today))
        focused = sum(r['Hours'] for r in rows if r['kind'] == 'Time' and r['Date'] == str(today) and r['Type'] == 'Focused')
        pending = [r for r in rows if r['kind'] == 'Deadlines' and r['Status'] != 'Done']
        return spent, focused, sorted(pending, key=lambda r:r['Due'])

    def import_csv(self, owner, kind, path):
        legacy = [k for k in FIELDS[kind] if k not in ('Added', 'TargetMarks')]
        with open(path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, strict=True)
            if not set(legacy).issubset(reader.fieldnames or []):
                raise ValueError('CSV columns must include: '+', '.join(legacy))
            prepared = []
            for line, r in enumerate(reader, 2):
                if (r.get('User') or owner).strip().lower() != owner:
                    continue
                try:
                    prepared.append(validate(kind, r))
                except ValueError as exc:
                    raise ValueError(f'CSV line {line}: {exc}') from None
        with self.guard():
            rows = self._records()
            existing = [validate(kind,r) for r in rows if r['User'] == owner and r['Kind'] == kind]
            next_id = max((int(r['id']) for r in rows), default=0)+1
            count = 0
            for data in prepared:
                if data in existing:
                    continue
                if kind in ('Courses','Attendance') and any(r['Subject'].casefold() == data['Subject'].casefold() for r in existing):
                    raise ValueError('CSV has a duplicate subject. Edit that subject instead.')
                rows.append(self._record(next_id,owner,kind,data))
                existing.append(data)
                next_id += 1
                count += 1
            self._write('records.csv', RECORD_COLUMNS, rows)
        return count

    def close(self):
        pass  # Files are opened only for the duration of each operation.
