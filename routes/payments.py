from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import datetime
from app import mongo
from bson import ObjectId

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')

def login_required(f):
    """Decorator to check if user is logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@payments_bp.route('/')
@login_required
def list_payments():
    """List all payments"""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page
    
    payments = list(mongo.db.payments.find().skip(skip).limit(per_page).sort('date', -1))
    total = mongo.db.payments.count_documents({})
    
    for payment in payments:
        payment['_id'] = str(payment['_id'])
    
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('payments/list.html',
                          payments=payments,
                          page=page,
                          total_pages=total_pages)

@payments_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_payment():
    """Add new payment"""
    if request.method == 'POST':
        payment_data = {
            'member_id': request.form.get('member_id'),
            'amount': float(request.form.get('amount', 0)),
            'date': datetime.now(),
            'payment_method': request.form.get('payment_method'),
            'description': request.form.get('description'),
            'status': 'completed',
            'transaction_id': request.form.get('transaction_id', ''),
            'recorded_by': session.get('user_id')
        }
        
        if not payment_data['member_id'] or payment_data['amount'] <= 0:
            flash('Member and amount are required', 'danger')
            return redirect(url_for('payments.add_payment'))
        
        result = mongo.db.payments.insert_one(payment_data)
        
        if result.inserted_id:
            flash('Payment recorded successfully', 'success')
            return redirect(url_for('payments.list_payments'))
        else:
            flash('Failed to record payment', 'danger')
    
    members = list(mongo.db.members.find({'status': 'active'}))
    for member in members:
        member['_id'] = str(member['_id'])
    
    return render_template('payments/add.html', members=members)

@payments_bp.route('/<payment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    """Edit payment"""
    payment = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
    
    if not payment:
        flash('Payment not found', 'danger')
        return redirect(url_for('payments.list_payments'))
    
    if request.method == 'POST':
        update_data = {
            'amount': float(request.form.get('amount', 0)),
            'payment_method': request.form.get('payment_method'),
            'description': request.form.get('description'),
            'status': request.form.get('status'),
            'transaction_id': request.form.get('transaction_id', '')
        }
        
        mongo.db.payments.update_one(
            {'_id': ObjectId(payment_id)},
            {'$set': update_data}
        )
        
        flash('Payment updated successfully', 'success')
        return redirect(url_for('payments.list_payments'))
    
    payment['_id'] = str(payment['_id'])
    
    members = list(mongo.db.members.find({'status': 'active'}))
    for member in members:
        member['_id'] = str(member['_id'])
    
    return render_template('payments/edit.html', payment=payment, members=members)

@payments_bp.route('/<payment_id>/delete', methods=['POST'])
@login_required
def delete_payment(payment_id):
    """Delete payment"""
    result = mongo.db.payments.delete_one({'_id': ObjectId(payment_id)})
    
    if result.deleted_count:
        flash('Payment deleted successfully', 'success')
    else:
        flash('Failed to delete payment', 'danger')
    
    return redirect(url_for('payments.list_payments'))

@payments_bp.route('/receipt/<payment_id>')
@login_required
def payment_receipt(payment_id):
    """Generate payment receipt"""
    payment = mongo.db.payments.find_one({'_id': ObjectId(payment_id)})
    
    if not payment:
        flash('Payment not found', 'danger')
        return redirect(url_for('payments.list_payments'))
    
    payment['_id'] = str(payment['_id'])
    
    # Get member info
    member = mongo.db.members.find_one({'_id': ObjectId(payment['member_id'])})
    if member:
        member['_id'] = str(member['_id'])
    
    return render_template('payments/receipt.html', payment=payment, member=member)
