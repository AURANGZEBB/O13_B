# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    related_invoice_ids = fields.Many2one('account.move', string="Related Invoice IDs")

    def mass_unreserve(self):
        active_records = self.env.context.get('active_ids')
        active_objs = self.search([('id', '=', active_records)])
        print(active_objs)
        for obj in active_objs:
            obj.do_unreserve()