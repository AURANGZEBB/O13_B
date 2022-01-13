# -*- coding: utf-8 -*-
import time

from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_code = fields.Char(string="Code")
    product_brand = fields.Many2one("product.brand", string="Brand")

    @api.onchange('product_color')
    def color_changeon(self):
        print("ITs working")
        for rec in self:
            # rec.product_color.related_product_id = rec.ids[0]
            self.default_code = (self.product_color.name if self.product_color else "") + self.default_code if self.default_code else ""

    product_color = fields.Many2one("product.color", string="Color")

    def both_functions_execute(self):
        print(self.virtual_available)
        print(self.qty_available)