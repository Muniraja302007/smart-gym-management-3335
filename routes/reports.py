from flask import Blueprint, render_template, request, session, redirect, url_for
from functools import wraps
from datetime import datetime, date, timedelta
from app import mongo
from bson import ObjectId

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@reports_bp.route('/revenue')
@login_required
def revenue_report():
    """Revenue report"""
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    
    try:
        year, month_num = map(int, month.split('-'))
    except:
        year, month_num = date.today().year, date.today().month
    
    from datetime import datetime as dt
    start_date = dt(year, month_num, 1)
    if month_num == 12:
        end_date = dt(year + 1, 1, 1)
    else:
        end_date = dt(year, month_num + 1, 1)
    
    payments = list(mongo.db.payments.find({
        'date': {'$gte': start_date, '$lt': end_date},
        'status': 'completed'
    }).sort('date', -1))
    
    for payment in payments:
        payment['_id'] = str(payment['_id'])
    
    total_revenue = sum(p['amount'] for p in payments)
    average_payment = total_revenue / len(payments) if payments else 0
    
    stats = {
        'total_revenue': total_revenue,
        'total_payments': len(payments),
        'average_payment': average_payment
    }
    
    return render_template('reports/revenue.html',
                          payments=payments,
                          stats=stats,
                          month=month)

@reports_bp.route('/membership')
@login_required
def membership_report():
    """Membership report"""
    members = list(mongo.db.members.find())
    
    for member in members:
        member['_id'] = str(member['_id'])
    
    # Categorize members
    active = sum(1 for m in members if m.get('status') == 'active')
    inactive = sum(1 for m in members if m.get('status') == 'inactive')
    expired = sum(1 for m in members if m.get('membership_expiry', datetime.now()) < datetime.now())
    
    stats = {
        'total_members': len(members),
        'active_members': active,
        'inactive_members': inactive,
        'expired_memberships': expired
    }
    
    return render_template('reports/membership.html',
                          members=members,
                          stats=stats)

@reports_bp.route('/trainer')
@login_required
def trainer_report():
    """Trainer performance report"""
    trainers = list(mongo.db.trainers.find())
    
    for trainer in trainers:
        trainer['_id'] = str(trainer['_id'])
        # Count assigned members
        trainer['assigned_members'] = mongo.db.members.count_documents({
            'trainer_id': str(trainer['_id']),
            'status': 'active'
        })
    
    total_trainers = len(trainers)
    active_trainers = sum(1 for t in trainers if t.get('status') == 'active')
    
    stats = {
        'total_trainers': total_trainers,
        'active_trainers': active_trainers,
        'average_members': sum(t['assigned_members'] for t in trainers) / len(trainers) if trainers else 0
    }
    
    return render_template('reports/trainer.html',
                          trainers=trainers,
                          stats=stats)

@reports_bp.route('/attendance-monthly')
@login_required
def monthly_attendance_report():
    """Monthly attendance report"""
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    
    try:
        year, month_num = map(int, month.split('-'))
    except:
        year, month_num = date.today().year, date.today().month
    
    from datetime import datetime as dt
    start_date = dt(year, month_num, 1)
    if month_num == 12:
        end_date = dt(year + 1, 1, 1)
    else:
        end_date = dt(year, month_num + 1, 1)
    
    attendance_records = list(mongo.db.attendance.find({
        'date': {'$gte': start_date, '$lt': end_date}
    }).sort('date', -1))
    
    for record in attendance_records:
        record['_id'] = str(record['_id'])
    
    total_records = len(attendance_records)
    present = sum(1 for r in attendance_records if r.get('status') == 'present')
    absent = sum(1 for r in attendance_records if r.get('status') == 'absent')
    
    stats = {
        'total_records': total_records,
        'present': present,
        'absent': absent,
        'attendance_rate': (present / total_records * 100) if total_records > 0 else 0
    }
    
    return render_template('reports/attendance_monthly.html',
                          attendance=attendance_records,
                          stats=stats,
                          month=month)

@reports_bp.route('/dashboard')
@login_required
def reports_dashboard():
    """Reports dashboard"""
    today = date.today()
    
    # Today's stats
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    today_attendance = mongo.db.attendance.count_documents({
        'date': {'$gte': today_start, '$lte': today_end}
    })
    
    today_payments = mongo.db.payments.find({
        'date': {'$gte': today_start, '$lte': today_end}
    })
    today_revenue = sum(p['amount'] for p in today_payments)
    
    # This month stats
    start_of_month = today.replace(day=1)
    month_start = datetime.combine(start_of_month, datetime.min.time())
    
    month_payments = mongo.db.payments.find({
        'date': {'$gte': month_start}
    })
    month_revenue = sum(p['amount'] for p in month_payments)
    
    stats = {
        'today_attendance': today_attendance,
        'today_revenue': today_revenue,
        'month_revenue': month_revenue,
        'total_members': mongo.db.members.count_documents({'status': 'active'}),
        'total_trainers': mongo.db.trainers.count_documents({'status': 'active'})
    }
    
    return render_template('reports/dashboard.html', stats=stats)
