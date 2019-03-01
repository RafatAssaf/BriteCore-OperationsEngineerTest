# You will probably need more methods from flask but this one is a good start.
from flask import render_template, redirect, url_for, request, jsonify

# Import things from Flask that we need.
from accounting import app, db

# Import PolicyAccounting Class to return account balance for requested policy
from utils import PolicyAccounting

# Import our models
from models import Contact, Invoice, Policy

policies = [
    {
        "number": "policy one",
        "billing_schedule": "Monthly"
    },
    {
        "number": "policy two",
        "billing_schedule": "Quarterly"
    }
]


# Routing for the server.
@app.route("/")
@app.route("/home")
def index():
    # You will need to serve something up here.
    return render_template('home.html')


# Data endpoint
@app.route("/policy", methods=['GET'])
def policy():
    policy_number = request.args.get('policyNumber')
    date_cursor = request.args.get('dateCursor')

    if not policy_number:  # just in case..
        return jsonify({
            'message': "No policy number was provided."
        })

    policy = Policy.query.filter(Policy.policy_number == policy_number).one()
    pa = PolicyAccounting(policy.id)
    invoices = Invoice.query.filter_by(policy_id=policy.id).all()

    policy_agent_name = None
    # TODO: not so efficient, refactor to use exists()
    if Contact.query.filter_by(id=policy.agent).filter(Contact.role == "Named Insured").count():
        policy_agent_name = Contact.query.filter_by(id=policy.named_insured).filter(Contact.role == "Named Insured").one()

    policy_named_insured_name = None
    # TODO: not so efficient, refactor to use exists()
    if Contact.query.filter_by(id=policy.named_insured).filter(Contact.role == "Agent").count():
        policy_agent_name = Contact.query.filter_by(id=policy.agent).filter(Contact.role == "Agent").one()

    def package_invoice(a):
        return {'id': a.id,
                'policy_id': a.policy_id,
                'amount_due': a.amount_due,
                'bill_date': a.bill_date.strftime("%Y-%m-%d"),
                'due_date': a.due_date.strftime("%Y-%m-%d"),
                'cancel_date': a.cancel_date.strftime("%Y-%m-%d"),
                'deleted': a.deleted}
    response = {
        'policy': {
            'id': policy.id,
            'policy_number': policy.policy_number,
            'effective_date': policy.effective_date.strftime("%Y-%m-%d"),
            'status': policy.status,
            'billing_schedule': policy.billing_schedule,
            'annual_premium': policy.annual_premium,
            'named_insured': policy_named_insured_name,
            'agent': policy_agent_name,
            'status_info': policy.status_info,
            'cancellation_date': policy.cancellation_date,
            'account_balance': pa.return_account_balance(date_cursor)
        },
        'invoices': map(package_invoice, invoices)
    }
    return jsonify(response)


@app.route("/about")
def about():
    return render_template('about.html')

