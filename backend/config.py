

# ── Performance tiers ──────────────────────────────────────────────────────
FLASK_SECRET = 'mmc_scorecard_secret_2024_changeme'

TIERS = [
    {'grade':'A','label':'High Performer',       'color':'#10B981','min':90,'max':100},
    {'grade':'B','label':'Consistent Performer',  'color':'#F59E0B','min':60,'max':89.99},
    {'grade':'C','label':'Needs Improvement',     'color':'#EF4444','min':0, 'max':59.99},
]

SQL_SERVER   = r'3.226.227.21,1433\SQLEXPRESS2016'
SQL_DATABASE = 'mmcconvert_Data'
SQL_USER     = 'mmc_user'
SQL_PASSWORD = '8D9hh3d5w1o@0w2$e'
