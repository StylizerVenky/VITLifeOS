"""VIT Life OS. Start with: python3 -m streamlit run app.py."""
import csv
import io
import math
import os
import tempfile
import time
from datetime import date
from pathlib import Path

import streamlit as st
from store import Store, FIELDS, attendance_plan
from engines import daily_recommendations
from dashboard import cg_maxxing, money_maxxing, time_maxxing, purchase_maxxing, what_if_lab

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ.get('VIT_LIFE_OS_DATA', str(BASE / 'data')))
PAGES = ('Home', 'CG Maxxing', 'Money Maxxing', 'Time Maxxing', 'Purchase Maxxing', 'What-If Lab', 'Expenses', 'Courses', 'Attendance', 'Deadlines', 'Focus timer', 'Time', 'Wishlist', 'Notes')
DESCRIPTIONS = {
    'Expenses': 'Mess extras, cab splits, printouts. Keep the small spends in sight.',
    'Courses': 'Your scores, credits and the subjects that need a little more time.',
    'Attendance': 'Plan your next few classes with a course-specific attendance target.',
    'Deadlines': 'CAT prep, lab records, assignments and club work, all in one place.',
    'Time': 'Make room for focused work, classes, wandering and rest.',
    'Wishlist': 'A little breathing room between wanting something and buying it.',
    'Notes': 'A place for ideas, reminders and anything taking up space in your head.',
}


def open_store():
    return Store(DATA)


def feedback(text):
    st.session_state['notice'] = text
    st.rerun()


def reset_timer():
    st.session_state.pop('focus_session', None)


def style():
    # Native Streamlit widgets and theme handle text/input contrast. Only animate
    # buttons and an isolated decorative cup, avoiding broad widget overrides.
    st.markdown('''<style>
    .block-container {max-width: 1120px; padding-top: 2.4rem; padding-bottom: 3rem;}
    h1,h2,h3 {letter-spacing: -.025em;}
    div[data-testid="stButton"] button {border-radius: 12px; transition: transform .16s ease, box-shadow .16s ease;}
    div[data-testid="stButton"] button:hover {transform: translateY(-2px); box-shadow: 0 5px 12px #00000012;}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 18px;}
    .cafe-cup {font-size: 2.3rem; display:inline-block; animation: breathe 4s ease-in-out infinite;}
    @keyframes breathe {0%,100% {transform:translateY(0)} 50% {transform:translateY(-4px)}}
    @media (prefers-reduced-motion: reduce) {
      .cafe-cup {animation:none;}
      div[data-testid="stButton"] button {transition:none;}
      div[data-testid="stButton"] button:hover {transform:none;}
    }
    </style>''', unsafe_allow_html=True)


def auth(store):
    left, right = st.columns([1.1, 1], gap='large')
    with left:
        st.markdown('<div class="cafe-cup" aria-hidden="true">☕</div>', unsafe_allow_html=True)
        st.title('VIT Life OS')
        st.subheader('Your table is ready.')
        st.write('A calmer corner for busy campus days. Classes, spending, deadlines and small wins — together.')
        st.caption('A personal student planner. No affiliation with VIT.')
    with right:
        with st.container(border=True):
            login, register = st.tabs(['Take a seat', 'Create my corner'])
            with login:
                with st.form('login'):
                    name = st.text_input('Username', key='login_name')
                    password = st.text_input('Password', type='password', key='login_password')
                    submit = st.form_submit_button('Sign in', type='primary', use_container_width=True)
                if submit:
                    if store.login(name, password):
                        st.session_state['user'] = name.strip().lower()
                        reset_timer()
                        st.rerun()
                    st.error('Username or password did not match.')
            with register:
                with st.form('register'):
                    name = st.text_input('Choose a username', help='3–30 letters, numbers, dots, underscores or hyphens.')
                    password = st.text_input('Choose a password', type='password', help='Use at least 8 characters.')
                    confirm = st.text_input('Repeat password', type='password')
                    submit = st.form_submit_button('Create account', use_container_width=True)
                if submit:
                    try:
                        if password != confirm:
                            raise ValueError('The passwords do not match.')
                        st.session_state['user'] = store.register(name, password)
                        reset_timer()
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
        st.caption('Accounts and records are saved on the computer running this app. No cloud sync.')


def home(store, owner):
    spent, hours, pending = store.summary(owner)
    budget = store.budget(owner)
    st.title('Make yourself at home.')
    # User text is rendered through native widgets, never interpolated into HTML.
    st.write(f'Hello, {owner}. One thing at a time is a good pace.')
    cols = st.columns(3)
    values = [('Spent this month', f'₹{spent:,.0f}', f'₹{budget-spent:,.0f} remaining' if spent <= budget else f'₹{spent-budget:,.0f} over budget'),
              ('Focus today', f'{hours:g} h', 'Time deliberately set aside'),
              ('Open deadlines', str(len(pending)), 'One small task at a time')]
    for col, (label, value, note) in zip(cols, values):
        with col, st.container(border=True):
            st.metric(label, value)
            st.caption(note)
    a, b = st.columns([1.35, 1], gap='large')
    with a, st.container(border=True):
        st.subheader('The next few things')
        if not pending:
            st.info('A fresh page. Add an assignment, lab record or revision deadline.')
        for row in pending[:4]:
            days = (date.fromisoformat(row['Due']) - date.today()).days
            when = f'{-days} days overdue' if days < 0 else ('Due today' if days == 0 else f'In {days} days')
            st.write(row['Title'])
            st.caption(f"{row['Due']} · {row['Course'] or 'Personal'} · {when}")
    with b, st.container(border=True):
        st.subheader('Your next study nudge')
        courses = store.rows(owner, 'Courses')
        if courses:
            r = max(courses, key=lambda row: max(0,row['TargetMarks']-row['Marks'])*row['Credits'])
            st.write(r['Subject'])
            st.caption(f"{r['Marks']:g}/100 · {r['Credits']:g} credits · Target {r['Target']}")
        else:
            st.write('Add your courses to see what needs attention.')
        st.caption('Scores are planning notes, not an official grade or CGPA prediction.')
    st.subheader('A plan for today')
    st.caption('Data → analysis → trade-offs → recommendation. Suggestions are calculated from your own logs.')
    for item in daily_recommendations(store, owner, st.session_state.get('study_minutes',60)):
        st.write('• '+item)
    st.caption('Set your available study time in CG Maxxing. Review the four engines and the What-If Lab from the sidebar.')


def record_label(row, kind):
    key = {'Expenses':'Category', 'Courses':'Subject', 'Attendance':'Subject', 'Deadlines':'Title',
           'Time':'Activity', 'Wishlist':'Item', 'Notes':'Note'}[kind]
    text = str(row[key]).replace('\n', ' ')
    return f"#{row['id']} · {text[:75]}" + (f" · {row['Date']}" if 'Date' in row else '')


def editor(store, owner, kind, rows):
    by_id = {row['id']: row for row in rows}
    selected = st.selectbox('Add a new entry or edit an existing one', [None, *by_id],
                            format_func=lambda value: '＋ New entry' if value is None else record_label(by_id[value], kind),
                            key=f'{kind}_editor')
    old = by_id.get(selected, {})
    revision = st.session_state.get(f'{kind}_revision', 0)
    prefix = f'{kind}_{selected}_{revision}'
    defaults = {'Date':str(date.today()), 'Due':str(date.today()), 'Credits':4., 'Marks':75.,
                'Target':'A', 'TargetMarks':90., 'Added':str(date.today()), 'Hours':1., 'Type':'Focused', 'NeedScore':5., 'Status':'To do',
                'Attended':0., 'Held':0., 'Threshold':75., 'Amount':10., 'Price':0.}
    choices = {'Category':['Food & café', 'Transport', 'Printouts', 'Hostel', 'Shopping', 'Other'],
               'Target':['S','A','B','C','D','E','Pass'], 'Type':['Focused','Wandering','Rest','Classes'],
               'Status':['To do','In progress','Done']}
    numeric = {'TargetMarks':(0.,100.,1.), 'Credits':(.5,20.,.5), 'Marks':(0.,100.,1.), 'Hours':(.01,24.,.25),
               'NeedScore':(1.,10.,1.), 'Attended':(0.,10000.,1.), 'Held':(0.,10000.,1.),
               'Threshold':(1.,99.,1.), 'Amount':(.01,10000000.,10.), 'Price':(0.,10000000.,10.)}
    labels = {'Added':'First wanted on (starts the 7-day wait)', 'TargetMarks':'Personal target marks (/100)', 'Marks':'Score so far (/100)', 'Threshold':'Attendance target (%)', 'NeedScore':'Need score (1–10)',
              'Amount':'Amount (₹)', 'Price':'Price (₹)', 'Held':'Classes held', 'Attended':'Classes attended'}
    with st.form(prefix):
        data = {}
        for key in FIELDS[kind]:
            value = old.get(key, defaults.get(key, ''))
            label = labels.get(key, key)
            if key in ('Date', 'Due', 'Added'):
                data[key] = st.date_input(label, value=date.fromisoformat(str(value)), key=prefix+key).isoformat()
            elif key in choices:
                options = choices[key].copy()
                if value and value not in options:
                    options.insert(0, value)
                data[key] = st.selectbox(label, options, index=options.index(value) if value in options else 0, key=prefix+key)
            elif key in numeric:
                low, high, step = numeric[key]
                data[key] = st.number_input(label, min_value=low, max_value=high, value=float(value), step=step, key=prefix+key)
            elif key == 'Note':
                data[key] = st.text_area('What’s on your mind?', value=str(value), height=160, max_chars=4000, key=prefix+key)
            else:
                data[key] = st.text_input(label, value=str(value), max_chars=4000, key=prefix+key)
        save = st.form_submit_button('Save changes' if old else 'Save entry', type='primary', use_container_width=True)
    if save:
        try:
            store.save(owner, kind, data, selected)
            st.session_state[f'{kind}_revision'] = revision+1
            feedback('Saved. One less thing to keep in your head.')
        except (ValueError, OSError) as exc:
            st.error(str(exc))


def export_text(kind, rows):
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=FIELDS[kind])
    writer.writeheader()
    for row in rows:
        writer.writerow({key: ("'"+row[key] if isinstance(row[key],str) and row[key].startswith(('=','+','-','@')) else row[key])
                         for key in FIELDS[kind]})
    return '\ufeff'+text.getvalue()


def history(store, owner, kind, rows):
    a, b = st.columns([2, 1])
    query = a.text_input('Search this notebook', key=kind+'_search').casefold()
    period = b.selectbox('Date range', ['All dates', 'This month', 'Today'], key=kind+'_period') if kind in ('Expenses','Time','Notes','Deadlines') else 'All dates'
    visible = []
    for row in rows:
        stamp = str(row.get('Date', row.get('Due', '')))
        if query and query not in ' '.join(str(row[k]) for k in FIELDS[kind]).casefold():
            continue
        if period == 'This month' and stamp[:7] != date.today().isoformat()[:7]:
            continue
        if period == 'Today' and stamp != date.today().isoformat():
            continue
        visible.append(row)
    if visible:
        st.dataframe([{k:r[k] for k in FIELDS[kind]} for r in visible], use_container_width=True, hide_index=True)
    else:
        st.info('No entries in this view. Try another filter or add your first entry.')
    st.caption(f'{len(visible)} entries in this view')
    if kind == 'Expenses':
        st.write(f"View total: ₹{sum(r['Amount'] for r in visible):,.2f}")
        with st.expander('Monthly budget'):
            with st.form('budget'):
                budget = st.number_input('Monthly budget (₹)', min_value=1., max_value=10000000., value=float(store.budget(owner)))
                if st.form_submit_button('Update budget'):
                    store.budget(owner, budget)
                    feedback('Monthly budget updated.')
    if kind == 'Attendance':
        for row in visible:
            pct, plan = attendance_plan(row['Attended'], row['Held'], row['Threshold'])
            st.write(f"{row['Subject']} · {pct:.1f}%")
            st.caption(plan)
        st.caption('The threshold is your own planning target. Verify official course rules and records.')
    if kind == 'Wishlist':
        remaining = store.budget(owner)-store.summary(owner)[0]
        for row in visible:
            advice = 'Fits your remaining monthly budget.' if row['Price'] <= remaining else 'Above your remaining monthly budget. Consider saving for it.'
            if row['NeedScore'] < 7:
                advice += ' Not urgent? Give it a day.'
            st.caption(f"{row['Item']}: {advice}")
    st.download_button('Export this view as CSV', export_text(kind, visible).encode('utf-8'),
                       file_name=kind.lower()+'.csv', mime='text/csv', key=kind+'_download')
    by_id = {r['id']:r for r in visible}
    with st.expander('Remove logs / entries'):
        st.caption('Deletion cannot be undone. Export a copy first if you need it.')
        selected = st.multiselect('Entries to remove', list(by_id), format_func=lambda value:record_label(by_id[value],kind), key=kind+'_remove')
        confirm = st.checkbox('I confirm removal of the selected entries', key=kind+'_confirm_remove')
        if st.button('Remove selected', disabled=not selected or not confirm, key=kind+'_delete'):
            store.delete(owner, selected)
            feedback('Selected entries removed.')
    with st.expander('Clear this notebook'):
        st.warning(f'This removes all {len(rows)} {kind.lower()} entries for your account, including hidden rows.')
        phrase = st.text_input('Type CLEAR to confirm', key=kind+'_clear_phrase')
        if st.button('Clear all entries', disabled=phrase != 'CLEAR' or not rows, key=kind+'_clear'):
            store.delete(owner, [r['id'] for r in rows])
            feedback('Notebook cleared.')


def importer(store, owner, kind):
    st.write('Bring over your own CSV records from the earlier app.')
    st.caption('Columns: '+', '.join(FIELDS[kind]))
    st.caption('Older CSV files may omit TargetMarks (defaults to 90) or Added (defaults to today).')
    st.caption('Dates must use YYYY-MM-DD. If a User column exists, only rows matching your current username are imported. Exact duplicates are skipped.')
    file = st.file_uploader('Choose CSV', type=['csv'], key=kind+'_upload')
    if st.button('Import CSV', disabled=file is None, key=kind+'_import') and file is not None:
        path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp:
                path = Path(tmp.name)
                tmp.write(file.getvalue())
            count = store.import_csv(owner, kind, path)
            feedback(f'Imported {count} entries. Exact duplicates were skipped.')
        except (ValueError, OSError, UnicodeError, csv.Error) as exc:
            st.error(str(exc))
        finally:
            if path is not None:
                path.unlink(missing_ok=True)


@st.fragment(run_every=1)
def focus_panel(owner, detailed=False):
    timer = st.session_state.get('focus_session')
    if timer and timer['owner'] != owner:
        reset_timer()
        timer = None
    if timer and timer['end'] is not None:
        timer['left'] = max(0., timer['end']-time.monotonic())
        if timer['left'] <= 0 and not timer['logged']:
            store = open_store()
            try:
                store.save(owner, 'Time', {'Date':str(date.today()), 'Activity':timer['task'],
                                         'Hours':timer['seconds']/3600, 'Type':'Focused'})
                timer['logged'] = True
                timer['end'] = None
                st.session_state['notice'] = 'Focus session complete and saved. Time for a short break.'
                st.rerun()
            except (ValueError, OSError):
                st.error('Could not save this session. It will retry while this page is open.')
            finally:
                store.close()
    if not detailed:
        if timer and not timer['logged']:
            remaining = math.ceil(timer['left'])
            st.caption(f"☕ {timer['task']} · {remaining//60:02d}:{remaining%60:02d} {'remaining' if timer['end'] else 'paused'}")
            st.progress(min(1., max(0., 1-timer['left']/timer['seconds'])))
        return
    with st.container(border=True):
        st.subheader('One task on the table.')
        if timer and timer['logged']:
            st.success('Session saved. Stretch, get some water and take a short break.')
        duration = st.selectbox('Session length (minutes)', [15,25,45,60], index=1,
                                disabled=bool(timer and not timer['logged']), key='timer_minutes')
        task = st.text_input('What are you working on?', value='Study session', max_chars=120,
                             disabled=bool(timer and not timer['logged']), key='timer_task')
        left = timer['left'] if timer and not timer['logged'] else duration*60
        seconds = timer['seconds'] if timer and not timer['logged'] else duration*60
        remaining = math.ceil(left)
        st.metric('Time remaining', f'{remaining//60:02d}:{remaining%60:02d}')
        st.progress(min(1., max(0., 1-left/seconds)))
        a,b,c = st.columns(3)
        running = bool(timer and timer['end'] is not None)
        if a.button('Pause' if running else ('Resume' if timer and not timer['logged'] else 'Start session'), type='primary', use_container_width=True):
            if not timer or timer['logged']:
                timer = dict(owner=owner, task=task.strip() or 'Study session', seconds=duration*60,
                             left=duration*60, end=time.monotonic()+duration*60, logged=False)
                st.session_state['focus_session'] = timer
            elif running:
                timer['left'] = max(0., timer['end']-time.monotonic())
                timer['end'] = None
            else:
                timer['end'] = time.monotonic()+timer['left']
            st.rerun(scope='fragment')
        discard = b.checkbox('Confirm reset', key='timer_confirm_reset')
        if c.button('Reset session', disabled=not discard or timer is None, use_container_width=True):
            reset_timer()
            st.rerun(scope='fragment')
        st.caption('Completed sessions become focused-time logs. The timer continues across pages in this browser session. Keep the app open; refreshing the browser or restarting the server can discard an unfinished session.')


def main():
    st.set_page_config(page_title='VIT Life OS', page_icon='☕', layout='wide', initial_sidebar_state='expanded')
    style()
    try:
        store = open_store()
    except (OSError, ValueError) as exc:
        st.error(f'Cannot open your notebook: {exc}.  Keep the app folder writable or set VIT_LIFE_OS_DATA to a writable folder.')
        return
    try:
        owner = st.session_state.get('user')
        if not owner:
            auth(store)
            return
        with st.sidebar:
            st.title('☕ VIT Life OS')
            st.caption('A little room to reset.')
            page = st.radio('Your table', PAGES, label_visibility='collapsed')
            st.divider()
            st.caption(f'Signed in as {owner}')
            active = st.session_state.get('focus_session')
            unfinished = bool(active and not active['logged'])
            leave = st.checkbox('Discard unfinished focus session', key='logout_confirm') if unfinished else True
            if st.button('Sign out', disabled=not leave, use_container_width=True):
                # Clear this browser session, including text fields and account-specific selections.
                st.session_state.clear()
                st.rerun()
            st.caption('Python + CSV • Stored on this server\nNo online chat or cloud sync')
        st.caption(date.today().strftime('%A, %d %B').upper())
        if notice := st.session_state.pop('notice', None):
            st.success(notice)
        engines = {'CG Maxxing':cg_maxxing, 'Money Maxxing':money_maxxing,
                   'Time Maxxing':time_maxxing, 'Purchase Maxxing':purchase_maxxing, 'What-If Lab':what_if_lab}
        if page in engines:
            focus_panel(owner)
            engines[page](store, owner)
        elif page == 'Focus timer':
            st.title('A little time for one thing.')
            focus_panel(owner, detailed=True)
        else:
            focus_panel(owner)
            if page == 'Home':
                home(store, owner)
            else:
                st.title(page)
                st.caption(DESCRIPTIONS[page])
                rows = store.rows(owner, page)
                add, logs, transfer = st.tabs(['Add / edit', 'History & remove logs', 'Import CSV'])
                with add:
                    editor(store, owner, page, rows)
                with logs:
                    history(store, owner, page, rows)
                with transfer:
                    importer(store, owner, page)
        st.divider()
        st.caption('Take a breath. Small steps count. • VIT Life OS')
    except (OSError, ValueError) as exc:
        st.error(f'Could not finish that action: {exc}')
    finally:
        store.close()


if __name__ == '__main__':
    main()
