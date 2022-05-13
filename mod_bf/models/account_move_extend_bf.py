# -*- coding: utf-8 -*-
import time
from odoo.tools.profiler import profile
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split, email_escape_char, email_re
from odoo.tools.misc import formatLang, format_date, get_lang
from datetime import date, timedelta
from itertools import groupby
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import json
import re


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    category_id = fields.Many2one("product.category", string="Category", related="product_id.categ_id", readonly=False)
    x_color = fields.Many2one("product.color", string="Color", related="product_id.product_color")

    # @profile
    @api.depends('account_id')
    def compute_net_balance(self):
        for rec in self:
            if rec.parent_state == "posted":
                rec.net_balance = rec.debit - rec.credit

                last_line = []
                last_balance = rec.search([('partner_id', '=', rec.partner_id.id),
                                           ('parent_state', '=', 'posted'),
                                           ('account_id.user_type_id.type', 'in', ('payable', 'receivable')),
                                           ('create_date', '<=', rec.create_date),
                                           ('id', '!=', rec.id),
                                           ]).sorted(key='create_date')
                if last_balance:
                    index = len(last_balance) - 1
                    print(last_balance[index].date, last_balance[index].id)
                    rec.cumulated_balance = last_balance[index].cumulated_balance + rec.net_balance
                    # rec.write({'cumulated_balance': last_balance[index].cumulated_balance + rec.net_balance2})
                    last_line.append(last_balance[index].id)
                else:
                    rec.cumulated_balance = rec.net_balance
                    # rec.write({'cumulated_balance': rec.net_balance2})
            else:
                rec.net_balance = 0.0

    net_balance = fields.Float(string="Net (+)Debit/(-)Credit", compute="compute_net_balance")
    net_balance2 = fields.Float(string="Net (+)Debit/(-)Credit", related="net_balance")
    cumulated_balance = fields.Float(string="Cumulated Balance", group_operator=False)

    # Overriding name_get()
    def name_get(self):
        result = []
        for rec in self:
            if self.env.context.get('show_rate_qty'):
                name = str(rec.move_id.name) + " ---Date: " + str(rec.move_id.invoice_date) + "---- Qty.[" + str(rec.quantity) +"]" + " ---- Rate Rs. " + str(rec.price_unit)
            else:
                name = str(rec.name)

            result.append((rec.id, name))
        return result