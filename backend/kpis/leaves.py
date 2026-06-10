from kpis.base import BaseKPI
from viasocket   import get_leaves_for_month, get_working_days
from name_mapper import resolve, init_name_map_table

class LeavesKPI(BaseKPI):
    def fetch(self, month, year):
        init_name_map_table()
        rows = get_leaves_for_month(month, year)
        wdays = get_working_days(year, month)
        result = []
        for row in rows:
            name = (row.get('name') or '').strip()
            if not name: continue
            mapped = resolve(name)
            leave  = min(int(row.get('month_leave_count',0)), wdays)
            result.append({'AdminID':mapped['admin_id'],'EmployeeName':name,
                'Department':row.get('dept_normalized'),'WorkingDays':wdays,
                'LeaveDays':leave,'LeaveDates':row.get('month_leave_dates',[]),
                'MatchMethod':mapped['match_method'],'Month':month,'Year':year})
        print(f'[LeavesKPI] {month}/{year} → {len(result)} employees')
        return result

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
        row  = rows[0]; wdays=row.get('WorkingDays',0); leave=row.get('LeaveDays',0)
        pres = max(0, wdays-leave)
        ratio= round(pres/wdays*100,2) if wdays else None
        return {'numerator':pres,'denominator':wdays,'success_ratio':ratio,
                'orders':[{'working_days':wdays,'leave_days':leave,
                           'present_days':pres,'leave_dates':row.get('LeaveDates',[])}]}
