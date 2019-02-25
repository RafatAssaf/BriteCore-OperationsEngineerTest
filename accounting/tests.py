#!/user/bin/env python2.7

import unittest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from random import randint

from accounting import db
from models import Contact, Invoice, Payment, Policy
from utils import PolicyAccounting

"""
#######################################################
Test Suite for Accounting
#######################################################
"""

class TestBillingSchedules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)

    def setUp(self):
        # define a test policy before each test function
        self.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        db.session.add(self.policy)
        self.policy.named_insured = self.test_insured.id
        self.policy.agent = self.test_agent.id
        db.session.commit()

    def tearDown(self):
        # clean test data after each function
        for invoice in self.policy.invoices:
            db.session.delete(invoice)

        # clear payments
        payments = Payment.query.filter_by(policy_id=self.policy.id).all()
        for payment in payments:
            db.session.delete(payment)

        db.session.commit()
        db.session.delete(self.policy)
        db.session.commit()

    def test_annual_billing_schedule(self):
        self.policy.billing_schedule = "Annual"
        # No invoices currently exist
        self.assertFalse(self.policy.invoices)
        # Invoices should be made when the class is initiated
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(len(self.policy.invoices), 1)
        self.assertEquals(self.policy.invoices[0].amount_due, self.policy.annual_premium)

    def test_monthly_billing_schedule(self):
        self.policy.billing_schedule = "Monthly"
        self.assertFalse(self.policy.invoices)
        # create policy accounting
        pa = PolicyAccounting(self.policy.id)

        self.assertEquals(len(self.policy.invoices), 12)

        # all invoices should have an amount due equals one 12th of the annual premium (tests make_invoices)
        for invoice in self.policy.invoices:
            self.assertEqual(invoice.amount_due, self.policy.annual_premium / 12)

        # before making any payment, the account balance should equal the annual premium
        self.assertEquals(pa.return_account_balance(), self.policy.annual_premium)

        amount_to_pay = randint(1, self.policy.annual_premium)

        # make a payment
        pa.make_payment(self.policy.agent,  # contact id
                        self.policy.effective_date + relativedelta(months=2),  # date cursor
                        amount_to_pay)

        # the amount paid should be deducted from the balance
        self.assertEquals(pa.return_account_balance(), self.policy.annual_premium - amount_to_pay)


class TestReturnAccountBalance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        self.payments = []

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        for payment in self.payments:
            db.session.delete(payment)
        db.session.commit()

    def test_annual_on_eff_date(self):
        self.policy.billing_schedule = "Annual"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 1200)

    def test_quarterly_on_eff_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 300)

    def test_quarterly_on_last_installment_bill_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .order_by(Invoice.bill_date).all()
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[3].bill_date), 1200)

    def test_quarterly_on_second_installment_bill_date_with_full_payment(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[1].bill_date, amount=600))
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[1].bill_date), 0)
