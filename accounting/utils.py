#!/user/bin/env python2.7

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from accounting import db
from models import Contact, Invoice, Payment, Policy
from sqlalchemy.exc import IntegrityError

"""
#######################################################
This is the base code for the engineer project.
#######################################################
"""

class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """
    def __init__(self, policy_id):
        # grabbing the policy we're accounting for this instance
        self.policy = Policy.query.filter_by(id=policy_id).one()

        if not self.policy.invoices:
            # if the policy doesn't have invoices, generate invoices according to it's billing schedule
            self.make_invoices()

    def return_account_balance(self, date_cursor=None):
        if not date_cursor:
            # default time cursor is current date
            date_cursor = datetime.now().date()

        # get all invoices for this policy with billing date before the date cursor (ordered by billing date)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
                                .filter_by(deleted=0) \
                                .filter(Invoice.bill_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        due_now = 0  # balance accumulator
        for invoice in invoices:
            # add up all invoices amount_due
            due_now += invoice.amount_due

        # get all payments for this policy that happened before the date cursor
        payments = Payment.query.filter_by(policy_id=self.policy.id)\
                                .filter(Payment.transaction_date <= date_cursor)\
                                .all()

        for payment in payments:
            # subtract all the amounts already paid
            due_now -= payment.amount_paid

        # gives back net amount due
        return due_now

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        if not date_cursor:
            # default date cursor is current date
            date_cursor = datetime.now().date()

        if contact_id:
            # create the payment instance
            payment = Payment(self.policy.id,
                              contact_id,
                              amount,
                              date_cursor)
            # update DB
            db.session.add(payment)
            db.session.commit()
            return payment
        else:
            if self.evaluate_cancellation_pending_due_to_non_pay(date_cursor):
                print("This policy is pending cancellation due to non-pay, only an agent can make payments on it.")
            else:
                try:
                    contact_id = self.policy.named_insured  # named insured id instead of agent id ?
                    # create the payment instance
                    payment = Payment(self.policy.id,
                                      contact_id,
                                      amount,
                                      date_cursor)
                    # update DB
                    db.session.add(payment)
                    db.session.commit()
                    return payment
                except IntegrityError:
                    db.session.rollback()
                    raise ValueError("This Policy has no named insured registered, you should specify (contact_id)")

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """ Returns (True) if the policy has in invoice pending cancellation due to non-pay, and (False) otherwise """
        return len(Invoice.query.filter_by(policy_id=self.policy.id)\
            .filter(Invoice.due_date <= date_cursor)\
            .filter(date_cursor < Invoice.cancel_date)\
            .all()) > 0

    def evaluate_cancel(self, date_cursor=None):
        if not date_cursor:
            # default date cursor is current date
            date_cursor = datetime.now().date()

        # get all invoices for this policy that are past the cancellation date, ordered by billing date
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        # checking invoices
        for invoice in invoices:
            if not self.return_account_balance(invoice.cancel_date):
                continue  # if all the invoices before the cancel date were paid by the time cursor..
            else:
                # if an invoice was not paid before it's cancellation date, then the policy should cancel
                print "THIS POLICY SHOULD HAVE CANCELED"
                break
        else:
            print "THIS POLICY SHOULD NOT CANCEL"

    def make_invoices(self):
        # clear policy's invoices
        for invoice in self.policy.invoices:
            invoice.delete()

        # the divisor by which the amount_due value (total amount) should be divided
        billing_schedules = {'Annual': None, 'Semi-Annual': 3, 'Quarterly': 4, 'Monthly': 12}

        invoices = []

        # the first invoice is the starting point for scheduling
        first_invoice = Invoice(self.policy.id,
                                self.policy.effective_date,  # bill_date
                                self.policy.effective_date + relativedelta(months=1),  # due after a month
                                self.policy.effective_date + relativedelta(months=1, days=14),  # cancel after 6 weeks
                                self.policy.annual_premium)  # amount due
        invoices.append(first_invoice)

        if self.policy.billing_schedule == "Annual":
            print "Annual billing schedule invoice has been created!"
            pass
        elif self.policy.billing_schedule == "Two-Pay":
            # due amount is 1 Nth of the total amount where N is the value of the policy's billing schedule
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)

            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                # for Semi-Annual scheduling, we have 6 months between invoices. that is: (12 months / 2 invoices)
                months_after_eff_date = i*6
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),  # due after a month from billing
                                  bill_date + relativedelta(months=1, days=14),  # cancels after 6 weeks from billing
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
            print "Semi-Annual billing schedule invoices have been created!"

        elif self.policy.billing_schedule == "Quarterly":
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                # For Quarterly billing schedules, we have 3 months between each 2 consecutive invoices
                months_after_eff_date = i*3
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),  # due after a month from billing
                                  bill_date + relativedelta(months=1, days=14),  # cancels after 6 weeks form billing
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
            print "Quarterly billing schedule invoices have been created!"

        elif self.policy.billing_schedule == "Monthly":
            # setting amount due for the first invoice
            first_invoice.amount_due = first_invoice.amount_due / billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
            print "Monthly billing schedule invoices have been created"
        else:
            print "You have chosen a bad billing schedule."

        # update DB
        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()

    def change_schedule(self, date_cursor, new_billing_schedule):
        """This function transfers the policy to new billing schedule"""
        if not date_cursor:
            # default date cursor is current date
            date_cursor = datetime.now().date()

        amount_to_reschedule = self.return_account_balance()  # amount left from old billing schedule

        try:
            # try to extract rescheduling factor
            reschedule_factor = ({"Annual": 12, "Two-Pay": 6, "Quarterly": 3, "Monthly": 1})[new_billing_schedule]
        except KeyError:
            raise ValueError("Billing schedule: {} is not defined".format(new_billing_schedule))

        months_left_count = ((self.policy.effective_date + relativedelta(months=12)) - date_cursor).days / 30

        # a policy should not convert to schedule the number of months left < rescheduling factor
        # i.e. a Monthly policy cannot convert to Quarterly policy if the policy has 2 months left before it ends
        if months_left_count < reschedule_factor or date_cursor > self.policy.effective_date + relativedelta(years=1):
            raise ValueError("Could not convert policy to billing schedule: {}, date cursor is too late"
                             .format(new_billing_schedule))
        if date_cursor < self.policy.effective_date:
            raise ValueError("Could not convert policy to billing schedule: {}, policy is not effective at date cursor"
                             .format(new_billing_schedule))

        # how many new invoices should be created
        invoices_left_count = months_left_count / reschedule_factor
        new_invoices = []
        for i in range(1, invoices_left_count + 1):
            cursor = (date_cursor + relativedelta(months=i*reschedule_factor))
            bill_date = date(cursor.year, cursor.month, self.policy.effective_date.day)
            invoice = Invoice(self.policy.id,
                              bill_date,
                              bill_date + relativedelta(months=1),
                              bill_date + relativedelta(months=1, days=14),
                              amount_to_reschedule / float(invoices_left_count))
            new_invoices.append(invoice)

        for invoice in new_invoices:
            db.session.add(invoice)

        for invoice in self.policy.invoices:
            invoice.deleted = 1

        self.policy.billing_schedule = new_billing_schedule
        db.session.commit()
        print("Policy schedule was successfully changed to {} billing schedule".format(new_billing_schedule))

################################
# The functions below are for the db and 
# shouldn't need to be edited.
################################
def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print "DB Ready!"

def insert_data():
    #Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()

