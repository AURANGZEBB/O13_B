# -*- coding: utf-8 -*-
import time

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


class AccountMove(models.Model):
    _inherit = "account.move"

    def get_previous_and_current_balance(self):
        for rec in self:
            previous = rec.search([('state', '=', 'posted'), ('invoice_payment_state', '!=', 'paid'),
                                   ('partner_id', '=', rec.partner_id.id), ('id', '!=', rec.id)])
            if previous:
                for r in previous:
                    rec.previous_balance += r.amount_residual_signed
                    rec.current_balance = rec.previous_balance + rec.amount_residual

            else:
                rec.previous_balance = 0.0
                rec.current_balance = rec.previous_balance + rec.amount_residual

    previous_balance = fields.Float(string="Previous Balance", compute="get_previous_and_current_balance")
    current_balance = fields.Float(string="Current Balance", compute="get_previous_and_current_balance")

    def custom_register_payment(self):
        for rec in self:
            journal_id = rec.env['account.journal'].search([('type', '=', 'cash')])
            print(journal_id)
            account_payment = rec.env['account.payment'].with_context(default_invoice_ids=[(4, rec.id, False)])
            account_payment.create({
                'amount': rec.amount_total,
                'communication': rec.name,
                'partner_type': 'customer',
                'partner_id': rec.partner_id.id,
                'currency_id': rec.currency_id.id or rec.company_currency_id.id,
                # 'invoice_ids': rec.id,
                'journal_id': journal_id.id,
                'payment_date': rec.invoice_date,
                'payment_method_id': 1,
                'payment_type': 'inbound' if rec.type == 'out_invoice' else 'outbound' if rec.type == 'out_refund' else None,
                # 'payment_difference_handling': 'reconcile',
            }).post()

    def clear_list_products(self):
        for rec in self:
            rec.line_ids = [(6,0,0)]

        for rec in self.invoice_line_ids:
            # print(rec.move_id, self.id)
            if rec.move_id.id == self.id:
                rec.unlink()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        var_customer_name = self.env['customer.name']
        var_customer_code = self.env['customer.code']
        for rec in self:
            vn = var_customer_name.search([('related_partner_id', '=', rec.partner_id.record_id)])
            vc = var_customer_code.search([('related_partner_id', '=', rec.partner_id.record_id)])
            rec.customer_id_generated = vn.id
            rec.customer_code = vc.id

    @api.onchange('customer_id_generated')
    def compute_customer_id(self):
        partner_list = self.env['res.partner']
        var_customer_code = self.env['customer.code']
        for rec in self:
            print("ITs Working")
            partner = partner_list.search([('record_id', '=', rec.customer_id_generated.related_partner_id)])
            vc = var_customer_code.search([('related_partner_id', '=', partner.record_id)])
            rec.customer_code = vc.id
            rec.partner_id = partner.id

    customer_id_generated = fields.Many2one("customer.name", string="Customer ID")

    @api.onchange('customer_code')
    def compute_customer_code(self):
        partner_list = self.env['res.partner']
        var_customer_code = self.env['customer.name']
        for rec in self:
            partner = partner_list.search([('record_id', '=', rec.customer_code.related_partner_id)])
            vn = var_customer_code.search([('related_partner_id', '=', partner.record_id)])
            rec.customer_id_generated = vn.id
            rec.partner_id = partner.id

    customer_code = fields.Many2one("customer.code", string="Customer Code")

    def action_reverse_check(self):
        action = self.env.ref('account.action_view_account_move_reversal').read()[0]
        if self.is_invoice():
            action['name'] = _('Credit Note')

            # create Journal if not exist
            journals = self.env['account.journal'].search([('name', '=', 'Return Inward')])
            if not journals:
                journals.create({
                    'name': 'Return Inward',
                    'type': 'sale',
                    'code': 'RI/SR',
                })
            # create operation type in inventory
            operation_type = self.env['stock.picking.type'].search([('name', '=', 'Return Inward')])
            if not operation_type:
                created = operation_type.create({
                                    'name': 'Return Inward',
                                    'code': 'incoming',
                                    'sequence_code': 'ST/RI',
                                    'warehouse_id': 1,
                                })
        return action

    is_return = fields.Boolean(string="IS Return")

    # Overriding action_post method.....
    def action_post(self):
        if self.filtered(lambda x: x.journal_id.post_at == 'bank_rec').mapped('line_ids.payment_id').filtered(
                lambda x: x.state != 'reconciled'):
            raise UserError(
                _("A payment journal entry generated in a journal configured to post entries only when payments are reconciled with a bank statement cannot be manually posted. Those will be posted automatically after performing the bank reconciliation."))
        # print(self.env.with_context)
        # print(self.abc)
    # adding inventory move ---------------------------------------
    #     record = None
        if self.is_return and self.type == "out_refund" and self.state == 'draft':
            picking = self.env['stock.picking']
            lines = self.invoice_line_ids
            print(lines, self.id)
            list = []
            for line in lines:
                if line.product_id.type == 'product':
                    vals = {
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id,
                        'quantity_done': line.quantity,
                    }
                    list.append((0, 0, vals))
            record = picking.create({
                'picking_type_id': 7,
                'location_id': 5,
                'location_dest_id': 8,
                'partner_id': self.partner_id.id,
                'origin': 'ACTUAL RETURN',
                'related_invoice_ids': self.id,
                'move_ids_without_package': list,
            })
            record.action_assign()
            record.button_validate()

        elif self.type == "out_invoice":
            picking = self.env['stock.picking']
            lines = self.invoice_line_ids.search([('move_id', '=', self.id)])

            list = []
            for line in lines:
                if line.product_id.type == 'product':
                    vals = {
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id,
                        'quantity_done': line.quantity,
                    }
                    list.append((0, 0, vals))
            if list:
                record = picking.create({
                            'picking_type_id': 2,
                            'location_id': 8,
                            'location_dest_id': 5,
                            'partner_id': self.partner_id.id,
                            'origin': self.name,
                            'related_invoice_ids': self.id,
                            'move_ids_without_package': list,
                })
                record.action_assign()
                record.button_validate()

    # added inventory move -----------------------------

        return {
            self.post(),
            self.custom_register_payment() if self.partner_id.is_cash else ""
        }

    def button_draft(self):
        AccountMoveLine = self.env['account.move.line']
        excluded_move_ids = []

        if self._context.get('suspense_moves_mode'):
            excluded_move_ids = AccountMoveLine.search(AccountMoveLine._get_suspense_moves_domain() + [('move_id', 'in', self.ids)]).mapped('move_id').ids

        for move in self:
            if move in move.line_ids.mapped('full_reconcile_id.exchange_move_id'):
                raise UserError(_('You cannot reset to draft an exchange difference journal entry.'))
            if move.tax_cash_basis_rec_id:
                raise UserError(_('You cannot reset to draft a tax cash basis journal entry.'))
            if move.restrict_mode_hash_table and move.state == 'posted' and move.id not in excluded_move_ids:
                raise UserError(_('You cannot modify a posted entry of this journal because it is in strict mode.'))
            # We remove all the analytics entries for this journal
            move.mapped('line_ids.analytic_line_ids').unlink()

        self.mapped('line_ids').remove_move_reconcile()
        self.write({'state': 'draft'})

        # RETURN STOCK MOVE*****************
        if self.type == "out_invoice" and self.state == 'draft':
            picking = self.env['stock.picking']
            lines = self.invoice_line_ids
            list = []
            for line in lines:
                if line.product_id.type == 'product':
                    vals = {
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.quantity,
                        'name': line.product_id.name,
                        'product_uom': line.product_id.uom_id,
                        'quantity_done': line.quantity,
                    }
                    list.append((0, 0, vals))
            if list:
                record = picking.create({
                    'picking_type_id': 7,
                    'location_id': 5,
                    'location_dest_id': 8,
                    'partner_id': self.partner_id.id,
                    'origin': 'NOT ACTUAL RETURN',
                    'related_invoice_ids': self.id,
                    'move_ids_without_package': list,
                })
                record.action_assign()
                record.button_validate()
        elif self.type == "out_refund":
            raise ValidationError("You Cannot Reset the Return Invoice")

    def compute_total_qty(self):
        for rec in self:
            for t in rec.invoice_line_ids:
                rec.total_qty += t.quantity

    total_qty = fields.Integer(string="Total Qty.", compute="compute_total_qty")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.depends('product_id')
    def get_last_invoice_rate(self):
        for rec in self:
            # this piece of code is for copying category from previous line to current line
            lines = rec.move_id.invoice_line_ids
            if lines:
                print("line number -------- 263 ------")
                second_last_line = len(lines) - 2
                rec.category_id = lines[second_last_line].category_id.id
            # this piece of code is for copying category from previous line to current line

            if rec.product_id:
                print("line number ----- 267 -------")
                rec.category_id = rec.product_id.categ_id.id
                var = rec.search([('partner_id', '=', rec.partner_id.id), ('product_id', '=', rec.product_id.id)])
                date_list = []
                for date in var:
                    date_list.append(date.create_date)

                if date_list:
                    max_date = max(date_list)

                    for record in var:
                        if record.create_date == max_date:
                            print("True")
                            record_text = "qty : " + str(record.quantity) + "@ Rs. " + str(record.price_unit)
                            rec.last_inv = record_text
                else:
                    rec.last_inv = None

            else:
                rec.last_inv = None

    last_inv = fields.Char(string="Last Inv.", compute="get_last_invoice_rate")
    category_id = fields.Many2one("product.category", string="Category",
                                  readonly=False)
    x_color = fields.Many2one("product.color", string="Color", related="product_id.product_color")
    x_brand = fields.Many2one("product.brand", string="Brand", related="product_id.product_brand")

    @api.onchange('quantity', 'product_id')
    def onchange_quantity_value(self):
        print("line number ------ 302 ---------------")
        for rec in self:
            lines = rec.move_id.invoice_line_ids
            index = len(lines) - 2
            print(index)
            if index >= 1:
                for r in range(index):
                    print("#########################",r)
                    if lines[r].category_id.id == rec.category_id.id and lines[r].product_id.id == rec.product_id.id:
                        raise ValidationError("Product Duplication Error !!!!")

            if rec.product_id:
                if rec.qty_available < rec.stock_after_reserve:
                    if rec.qty_available < rec.quantity:
                        raise ValidationError(rec.product_id.name + " is Out of Stock !!!!!!!!!!!!!!!!!!!!!!")
                else:
                    if rec.stock_after_reserve and rec.stock_after_reserve < rec.quantity:
                        raise ValidationError(rec.product_id.name + " is Out of Stock !!!!!!!!!!!!!!!!!!!!!!")

    qty_available = fields.Float(string="ST.Avail", related="product_id.qty_available")
    stock_after_reserve = fields.Float(string="ST.Act.Avl", related="product_id.virtual_available")
    type_custom = fields.Selection(selection=[
            ('entry', 'Journal Entry'),
            ('out_invoice', 'Customer Invoice'),
            ('out_refund', 'Customer Credit Note'),
            ('in_invoice', 'Vendor Bill'),
            ('in_refund', 'Vendor Credit Note'),
            ('out_receipt', 'Sales Receipt'),
            ('in_receipt', 'Purchase Receipt'),
        ], string='Type', store=True, index=True, readonly=True, tracking=True,
        default="entry", change_default=True, related="move_id.type")

    def _compute_net_balance(self):
        for rec in self:
            if rec.parent_state == "posted":
                rec.net_balance = rec.debit - rec.credit
                rec.write({'net_balance2': rec.net_balance})

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

    net_balance = fields.Float(string="Net (+)Debit/(-)Credit", compute='_compute_net_balance')
    net_balance2 = fields.Float(string="Net (+)Debit/(-)Credit", related='net_balance', store=True)
    cumulated_balance = fields.Float(string="Cumulated Balance", readonly=True, store=False)


    


