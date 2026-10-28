"""Explainable decision engines using lists, dictionaries, loops and arithmetic."""
from collections import defaultdict
from datetime import date, timedelta
import math
from store import attendance_plan, number


def allocate_minutes(courses, minutes):
    """Credit × target-gap priority; largest remainder preserves the time budget."""
    minutes = int(round(number(minutes, 0, 1440, 'Available minutes')))
    ranked = []
    for r in courses:
        gap = max(0., float(r.get('TargetMarks',90))-r['Marks'])
        weight = gap*r['Credits']
        if weight > 0:
            ranked.append(dict(Subject=r['Subject'], Credits=r['Credits'], Current=r['Marks'],
                               Target=float(r.get('TargetMarks',90)), Gap=gap, Priority=weight))
    ranked.sort(key=lambda r:(-r['Priority'],r['Subject'].casefold()))
    total = sum(r['Priority'] for r in ranked)
    if not total or not minutes:
        return []
    shares = [minutes*r['Priority']/total for r in ranked]
    allocations = [math.floor(x) for x in shares]
    spare = minutes-sum(allocations)
    for i in sorted(range(len(shares)), key=lambda i:shares[i]-allocations[i], reverse=True)[:spare]:
        allocations[i] += 1
    for row, count in zip(ranked,allocations):
        row['Minutes'] = count
    return ranked


def money_report(expenses, today=None):
    today = today or date.today()
    start = today-timedelta(days=29)
    recent = [r for r in expenses if start <= date.fromisoformat(r['Date']) <= today]
    groups = defaultdict(lambda:dict(Amount=0., Count=0))
    optional = []
    for r in recent:
        key = r['Category'].strip().casefold()
        groups[key]['Amount'] += r['Amount']
        groups[key]['Count'] += 1
        text = (r['Category']+' '+r['Description']).casefold()
        if any(word in text for word in ('snack','café','cafe','cafeteria','coffee','tea','food','shopping','takeaway','swiggy','zomato')):
            optional.append(r)
    categories = [dict(Category=k.title(), **v) for k,v in groups.items()]
    categories.sort(key=lambda r:r['Amount'],reverse=True)
    optional_total = sum(r['Amount'] for r in optional)
    repeats = [r for r in categories if r['Count'] >= 3]
    return dict(Total=sum(r['Amount'] for r in recent), Categories=categories, Repeats=repeats,
                Optional=optional_total, Count=len(recent), Daily=sum(r['Amount'] for r in recent)/30,
                Start=str(start), End=str(today))


def time_report(logs, today=None):
    today = today or date.today()
    recent = [r for r in logs if today-timedelta(days=6) <= date.fromisoformat(r['Date']) <= today]
    groups = defaultdict(float)
    drift = defaultdict(float)
    for r in recent:
        groups[r['Type']] += r['Hours']
        if r['Type'] == 'Wandering':
            drift[r['Activity']] += r['Hours']
    return dict(Totals=dict(groups), Wandering=groups['Wandering'],
                Drift=sorted([dict(Activity=k,Hours=v) for k,v in drift.items()],key=lambda r:r['Hours'],reverse=True),
                Count=len(recent))


def purchase_verdict(wish, budget, spent, today=None):
    today = today or date.today()
    age = max(0,(today-date.fromisoformat(wish.get('Added',str(today)))).days)
    remaining = max(0., budget-spent)
    price = wish['Price']
    headroom = max(0.,1-price/remaining) if remaining else (1. if price == 0 else 0.)
    utility = wish['NeedScore']/10
    score = round(100*(.7*utility+.3*headroom))
    if age < 7:
        verdict = f'Wait {7-age} more day(s) before deciding.'
    elif price > remaining:
        verdict = 'Save first: this exceeds your remaining monthly budget.'
    elif wish['NeedScore'] < 7:
        verdict = 'Reconsider: it fits, but your utility score is low.'
    else:
        verdict = 'Worth considering: the wait is over and it fits your budget.'
    return dict(Item=wish['Item'], Score=score, DaysWaited=age, DaysLeft=max(0,7-age),
                BudgetImpact=100*price/budget if budget else 0., Remaining=remaining,
                Affordable=price<=remaining, Verdict=verdict)


def simulate_savings(daily, days):
    return round(number(daily,0,1000000,'Daily savings')*number(days,1,3650,'Days'),2)


def daily_recommendations(store, owner, study_minutes=60, today=None):
    today = today or date.today()
    spent, hours, deadlines = store.summary(owner,today)
    budget = store.budget(owner)
    recs = []
    if deadlines:
        r = deadlines[0]
        days = (date.fromisoformat(r['Due'])-today).days
        when = 'overdue' if days < 0 else ('due today' if days == 0 else f'due in {days} days')
        recs.append(f"First on your plate: {r['Title']} is {when}. Give it a defined work block.")
    plan = allocate_minutes(store.rows(owner,'Courses'),study_minutes)
    if plan:
        r = plan[0]
        recs.append(f"Study nudge: reserve {r['Minutes']} of your {study_minutes:g} planned minutes for {r['Subject']} (credit × target-gap priority {r['Priority']:g}).")
    if spent > budget:
        recs.append(f'You are ₹{spent-budget:,.0f} above your monthly budget. Pause optional purchases and review Money Maxxing.')
    else:
        recs.append(f'₹{budget-spent:,.0f} remains in this month’s budget. Keep essentials covered before allocating it to wishes.')
    money = money_report(store.rows(owner,'Expenses'),today)
    if money['Optional']:
        recs.append(f"Review ₹{money['Optional']:,.0f} of possible flexible spending logged over the last 30 days. A 25% cut would keep ₹{money['Optional']*.25:,.0f}, if those purchases are optional.")
    drift = time_report(store.rows(owner,'Time'),today)
    if drift['Wandering']:
        recs.append(f"You logged {drift['Wandering']:g} wandering hours in 7 days. Reclaim a manageable part in Time Maxxing; keep proper rest in your plan.")
    for row in store.rows(owner,'Attendance'):
        pct, advice = attendance_plan(row['Attended'],row['Held'],row['Threshold'])
        if pct < row['Threshold']:
            recs.append(f"Attendance: {row['Subject']} is at {pct:.1f}%. {advice}")
    for wish in store.rows(owner,'Wishlist')[:2]:
        verdict = purchase_verdict(wish,budget,spent,today)
        if verdict['DaysLeft'] or not verdict['Affordable']:
            recs.append(f"Purchase pause — {wish['Item']}: {verdict['Verdict']}")
    return recs
