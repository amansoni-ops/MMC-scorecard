from kpis.base import BaseKPI

class ReviewsKPI(BaseKPI):
    def fetch(self, month, year):
        print(f'[ReviewsKPI] DISABLED — awaiting OrderID in Table_Review')
        return []
    def aggregate(self, rows):
        return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
