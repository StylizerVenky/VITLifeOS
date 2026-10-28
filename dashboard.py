"""Streamlit views for the four decision engines and the What-If Lab."""
from datetime import date
import streamlit as st
from engines import allocate_minutes, money_report, time_report, purchase_verdict, simulate_savings


def plan_table(courses, minutes, key):
    plan = allocate_minutes(courses,minutes)
    if not courses:
        st.info('Add subjects, credits, scores and target marks in Courses first.')
    elif not plan:
        st.success('Your recorded subjects meet their targets, or no study time is allocated. Keep a revision buffer.')
    else:
        st.dataframe(plan,hide_index=True,use_container_width=True, key=key)
    return plan


def cg_maxxing(store, owner):
    st.title('CG Maxxing')
    st.caption('A study plan built around your own target marks.')
    courses = store.rows(owner,'Courses')
    minutes = st.slider('Study time available today (minutes)',0,480,120,15)
    st.session_state['study_minutes'] = minutes
    st.subheader('Your suggested allocation')
    plan = plan_table(courses,minutes,'cg_plan')
    if plan:
        st.write(f"Start with {plan[0]['Subject']}; work through the highest-priority gap first.")
        st.caption(f"{sum(r['Minutes'] for r in plan)} minutes allocated out of {minutes} available.")
    with st.expander('How this plan works'):
        st.write('Priority = subject credits × max(target marks − current marks, 0). Time is shared in proportion to those priorities. Whole-minute rounding preserves the total time budget.')
        st.write('Higher-credit subjects with larger target gaps receive more time. Subjects already at target get no catch-up time; add revision separately. Deadlines and attendance alerts appear on Home.')
    st.info('This is a planning heuristic. Marks must use the same /100 scale. Target marks are personal goals, not official S/A grade cutoffs or a CGPA prediction.')


def money_maxxing(store, owner):
    st.title('Money Maxxing')
    st.caption('Spot repeated spends, then choose what you actually want to change.')
    report = money_report(store.rows(owner,'Expenses'))
    a,b,c = st.columns(3)
    a.metric('Logged in 30 days',f"₹{report['Total']:,.0f}")
    b.metric('Possible flexible spending',f"₹{report['Optional']:,.0f}")
    c.metric('Transactions logged',report['Count'])
    st.caption(f"Window: {report['Start']} to {report['End']}. Incomplete logs give an incomplete picture. Future-dated entries are excluded.")
    if not report['Count']:
        st.info('Add expenses first. Repeated café snacks, coffee, takeaway and shopping will become easier to spot.')
        return
    st.subheader('Where the money went')
    st.dataframe(report['Categories'],hide_index=True,use_container_width=True)
    st.subheader('Repeat-spend check')
    if report['Repeats']:
        for row in report['Repeats']:
            st.write(f"{row['Category']}: {row['Count']} entries, ₹{row['Amount']:,.0f} in 30 days.")
    else:
        st.write('No category has reached three logged purchases in this window.')
    st.caption('Three or more entries flags a repeated pattern, not proof of waste. Food, travel and other necessities may be essential.')
    cut = st.slider('If the flagged flexible spending is optional, how much could you reduce?',0,100,25,5,format='%d%%')
    st.metric('Kept from the same spending pattern',f"₹{report['Optional']*cut/100:,.0f}")
    st.caption('Scenario based only on the last 30 days of logged food/café/snack/coffee/takeaway/shopping descriptions. Review the entries before deciding; essential meals should stay covered.')


def time_maxxing(store, owner):
    st.title('Time Maxxing')
    st.caption('Turn a little drift into a useful study block, without taking time from rest.')
    report = time_report(store.rows(owner,'Time'))
    a,b,c = st.columns(3)
    a.metric('Wandering logged · 7 days',f"{report['Wandering']:g} h")
    b.metric('Focused logged · 7 days',f"{report['Totals'].get('Focused',0):g} h")
    c.metric('Rest logged · 7 days',f"{report['Totals'].get('Rest',0):g} h")
    if report['Drift']:
        st.dataframe(report['Drift'],hide_index=True,use_container_width=True)
    fraction = st.slider('Share of wandering time you could realistically reclaim',0,100,25,5,format='%d%%')
    recovered = report['Wandering']*fraction/100
    st.metric('Recovered in a comparable week',f'{recovered:.2f} h')
    st.caption('A planning scenario using the previous 7 days of logs; it assumes a similar future week. Rest and classes are not counted as wasted time.')
    # Allocate the average daily portion, keeping a simple 24-hour daily bound.
    minutes = min(1440,round(recovered*60/7))
    st.subheader(f'How the average {minutes} extra minutes/day could help')
    plan_table(store.rows(owner,'Courses'),minutes,'time_plan')
    st.info('Academic impact here means study time redirected toward target-mark gaps. The app cannot infer a reliable marks-per-hour improvement.')


def purchase_maxxing(store, owner):
    st.title('Purchase Maxxing')
    st.caption('Seven days of breathing room before an impulse buy.')
    wishes = store.rows(owner,'Wishlist')
    budget = store.budget(owner)
    spent = store.summary(owner)[0]
    if not wishes:
        st.info('Add an item, price, utility score and wish date in Wishlist to start the seven-day wait.')
        return
    reports = [purchase_verdict(wish,budget,spent) for wish in wishes]
    for report in reports:
        with st.container(border=True):
            st.subheader(report['Item'])
            a,b,c = st.columns(3)
            a.metric('Decision score / 100',report['Score'])
            b.metric('Days since wish',report['DaysWaited'])
            c.metric('Share of monthly budget',f"{report['BudgetImpact']:.1f}%")
            st.progress(min(1.,report['DaysWaited']/7),text=f"{min(report['DaysWaited'],7)} / 7 days waited")
            st.write(report['Verdict'])
    with st.expander('How the score works'):
        st.write('Utility contributes 70% of the score. Budget headroom after the purchase contributes 30%. Headroom = max(0, 1 − price / remaining monthly budget). A free item has full headroom even when the remaining budget is zero.')
        st.write('The seven-day wait and affordability are separate gates: a high score does not override them. Utility below 7/10 triggers a reconsideration message. Advice uses your current budget and logs; it does not reserve money or place orders.')
        st.write('Older wishes imported without a wish date start their wait on the import/migration day, because the app cannot know when you first wanted them.')


def what_if_lab(store, owner):
    st.title('The What-If Lab')
    st.caption('Small daily changes, made visible. Change the inputs before changing your habits.')
    money, study = st.tabs(['If I spend a little less…','If I study a little more…'])
    with money:
        daily = st.number_input('Reduce optional spending per day (₹)',min_value=0.,max_value=1000000.,value=40.,step=10.)
        a,b,c = st.columns(3)
        a.metric('30 days',f'₹{simulate_savings(daily,30):,.0f}')
        b.metric('6 months · 180 days',f'₹{simulate_savings(daily,180):,.0f}')
        c.metric('1 year · 365 days',f'₹{simulate_savings(daily,365):,.0f}')
        st.bar_chart([{'Days':d,'Savings (₹)':simulate_savings(daily,d)} for d in (30,180,365)],x='Days',y='Savings (₹)')
        st.caption('Daily reduction × days. Assumes the reduction happens every day; no investment returns or price changes. Reduce genuinely optional spending, not essential food or transport.')
    with study:
        extra = st.slider('Extra study minutes per day',0,240,60,15)
        days = st.selectbox('Keep it up for', [7,30,180,365],index=1,format_func=lambda value:f'{value} days')
        st.metric('Additional study time',f'{extra*days/60:g} h')
        st.subheader('Where that extra time could go')
        plan = plan_table(store.rows(owner,'Courses'),extra,'whatif_plan')
        if plan:
            st.dataframe([{'Subject':r['Subject'],'Extra minutes/day':r['Minutes'],
                           f'Hours over {days} days':round(r['Minutes']*days/60,2)} for r in plan],hide_index=True,use_container_width=True)
        st.caption('This allocates your extra hour to the weakest high-credit target gaps. It does not predict marks or alter saved logs. Reassess the plan as scores change.')
