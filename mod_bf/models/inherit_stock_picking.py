# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    related_invoice_ids = fields.Many2one('account.move', string="Related Invoice IDs")


