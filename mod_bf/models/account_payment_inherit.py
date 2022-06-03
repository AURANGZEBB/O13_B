from odoo.tools.profiler import profile
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class AccountPayment(models.Model):
    _inherit = "account.payment"

    def post(self):
        res = super(AccountPayment, self).post()
        for rec in self.move_line_ids:
            rec.net_balance2 = rec.debit - rec.credit
            rec.net_balance3 = rec.debit - rec.credit
        return res