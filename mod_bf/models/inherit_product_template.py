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

    # Overriding name_get()
    def name_get(self):
        result = []
        for rec in self:
            if self.env.context.get('show_with_qty_available'):
                name = str(rec.name) + "---- Qty.Avl.[" + str(rec.virtual_available) +"]"
            elif self.env.context.get('hide_val'):
                name = rec.name
            else:
                name = str(rec.name) + " - " + str(rec.categ_id.name) + " - " + str(rec.product_brand.name)

            result.append((rec.id, name))
        return result
    product_color = fields.Many2one("product.color", string="Color")

class ProductProduct(models.Model):
    _inherit = "product.product"

    # Overrinding name_get()
    def name_get(self):
        result = []
        for rec in self:
            if self.env.context.get('show_with_qty_available'):
                name = str(rec.name) + "---- Qty.Avl.[" + str(rec.virtual_available) +"]"
            elif self.env.context.get('hide_val'):
                name = rec.name
            else:
                name = str(rec.name) + " - " + str(rec.categ_id.name) + " - " + str(rec.product_brand.name)

            result.append((rec.id, name))
        return result
