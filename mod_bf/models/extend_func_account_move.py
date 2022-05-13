from odoo.tools.profiler import profile
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class AccountMove(models.Model):
    _inherit = "account.move"

    def fetch_values_from_invoice_lines(self):
        active_records = self.env.context.get('active_ids')
        active_objs = self.search([('id', '=', active_records)])
        for obj in active_objs:
            list = []
            if obj.invoice_line_ids  and not obj.account_move_lines_custom:
                for line in obj.invoice_line_ids:
                    list.append((0, 0, {
                        'category_id': line.product_id.categ_id.id,
                        'product_id': line.product_id.id,
                        'quantity': line.quantity,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                    }))
                obj.account_move_lines_custom = list
    # @profile
    def custom_register_payment(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 2")
        journal_id = self.env['account.journal'].search([('type', '=', 'cash')])
        for rec in self:
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

    def action_reverse_check(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 7")
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


    def button_draft(self):
        # RETURN STOCK MOVE*****************
        # condition if invoice is simple i-e out_invoice
        if self.type == "out_invoice" and self.state == 'posted':
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
        elif self.type == "out_refund" and self.state == 'posted':
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
                    'picking_type_id': 2,
                    'location_id': 8,
                    'location_dest_id': 5,
                    'partner_id': self.partner_id.id,
                    'origin': 'RETURN OF ACTUAL RETURN',
                    'related_invoice_ids': self.id,
                    'move_ids_without_package': list,
                })
                record.action_assign()
                record.button_validate()
        # ///////////////////////////////////////////////////////////////////////////////////////////

        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 9")
        AccountMoveLine = self.env['account.move.line']
        excluded_move_ids = []

        if self._context.get('suspense_moves_mode'):
            excluded_move_ids = AccountMoveLine.search(
                AccountMoveLine._get_suspense_moves_domain() + [('move_id', 'in', self.ids)]).mapped('move_id').ids

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

    @api.onchange('account_move_lines_custom')
    def compute_total_qty(self):
        # print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 10")
        qty = 0.0
        amount = 0.0
        for rec in self:
            if rec.type == "out_refund":
                rec.get_previous_and_current_balance()
            for t in rec.account_move_lines_custom:
                qty += t.quantity
                amount += t.price_subtotal

            rec.total_qty = qty
            rec.amount_total_custom = amount

            if rec.type == 'out_refund':
                rec.current_balance = rec.previous_balance - amount
            else:
                rec.current_balance = rec.previous_balance + amount
        if not qty:
            rec.total_qty = 0
        if not amount:
            rec.amount_total_custom = 0.0

    amount_total_custom = fields.Float(string="Amount Total Custom")
    total_qty = fields.Integer(string="Total Qty.", compute="compute_total_qty")
    account_move_lines_custom = fields.One2many('account.move.custom.line', 'move_id', string="Account Lines Custom")

    def action_post(self):
        self.invoice_line_ids = [(5, 0, 0)]
        lines = self.account_move_lines_custom
        list = []
        for line in lines:
            list.append((0, 0, {'product_id': line.product_id.id,
                                'quantity': line.quantity,
                                'price_unit': line.price_unit,
                                }))
        self.invoice_line_ids = list

        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 8")
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

    def clear_list_products(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 3")
        for rec in self:
            rec.line_ids = [(6, 0, 0)]

        for rec in self.invoice_line_ids:
            if rec.move_id.id == self.id:
                rec.unlink()

        for rec in self.account_move_lines_custom:
            if rec.move_id.id == self.id:
                rec.unlink()

    @api.onchange('partner_id')
    def get_previous_and_current_balance(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 1")
        all_records = self.env['account.move.line'].search([('partner_id', '=', self.partner_id.id),
                                                            ('parent_state', '=', 'posted'),
                                                            ('account_id.user_type_id.type', '=', 'receivable'),
                                                            ])
        req_records = all_records.filtered(lambda o:o.move_id != self).sorted(lambda o: o.date,
                                                    reverse=True).mapped(lambda o: o.net_balance2)
        for rec in self:
            sum_req_records = sum(req_records)
            rec.previous_balance = sum_req_records
            rec.current_balance = sum_req_records + rec.amount_total

    previous_balance = fields.Float(string="Previous Balance", default=0.0)
    current_balance = fields.Float(string="Current Balance", default=0.0)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 4")
        var_customer_name = self.env['customer.name']
        var_customer_code = self.env['customer.code']
        for rec in self:
            vn = var_customer_name.search([('related_partner_id', '=', rec.partner_id.record_id)])
            vc = var_customer_code.search([('related_partner_id', '=', rec.partner_id.record_id)])
            rec.customer_id_generated = vn.id
            rec.customer_code = vc.id
            rec.get_previous_and_current_balance()

    @api.onchange('customer_id_generated')
    def compute_customer_id(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 5")
        partner_list = self.env['res.partner']
        var_customer_code = self.env['customer.code']
        for rec in self:
            print("ITs Working")
            partner = partner_list.search([('record_id', '=', rec.customer_id_generated.related_partner_id)])
            vc = var_customer_code.search([('related_partner_id', '=', partner.record_id)])
            rec.customer_code = vc.id
            rec.partner_id = partner.id
            rec.get_previous_and_current_balance()

    customer_id_generated = fields.Many2one("customer.name", string="Customer ID")

    @api.onchange('customer_code')
    def compute_customer_code(self):
        print("file = Account_move_extend_bf.py /////////////////////////////////////// Function 6")
        partner_list = self.env['res.partner']
        var_customer_code = self.env['customer.name']
        for rec in self:
            partner = partner_list.search([('record_id', '=', rec.customer_code.related_partner_id)])
            vn = var_customer_code.search([('related_partner_id', '=', partner.record_id)])
            rec.customer_id_generated = vn.id
            rec.partner_id = partner.id
            rec.get_previous_and_current_balance()

    customer_code = fields.Many2one("customer.code", string="Customer Code")

class AccountMoveCustomLine(models.Model):
    _name = "account.move.custom.line"
    _check_company_auto = True

    @api.onchange('product_id')
    def depends_product_id(self):
        lines = self.move_id.account_move_lines_custom
        for rec in self:
            if rec.product_id and rec.move_id.type == "out_invoice":
                if rec.stock_after_reserve <= 0:
                    raise ValidationError("Stock Not Available !")
                lines_product_id = lines.mapped(lambda a: a.product_id.id)
                filter_lines = filter(lambda p: p == rec.product_id.id, lines_product_id)
                # print(lines_product_id,filter_lines)
                if len(list(filter_lines)) >= 3:
                    raise ValidationError("Product Duplication Error!!!!")

                related_last_inv_lines = rec.env['account.move.line'].search([('move_id.state', '=', 'posted'),
                                                       ('move_id.type', '=', 'out_invoice'),
                                                       ('product_id', '=', rec.product_id.id),
                                                       ('move_id.partner_id', '=', rec.move_id.partner_id.id),
                                                       ]).sorted(key=lambda r: r.date)
                if related_last_inv_lines:
                    last_line = len(related_last_inv_lines) - 1
                    rec.last_inv = "Qty." + str(related_last_inv_lines[last_line].quantity) + " @ Rs. " + str(related_last_inv_lines[last_line].price_unit)
                    print(len(lines))
            else:
                if lines:
                    length = len(lines)
                    rec.category_id = lines[length-2].category_id.id
            return False

    @api.onchange('quantity', 'price_unit')
    def onchange_quantity(self):
        for rec in self:
            if rec.quantity and rec.price_unit:
                rec.price_subtotal = rec.quantity * rec.price_unit
            if rec.stock_after_reserve < rec.quantity and rec.move_id.type == "out_invoice":
                raise ValidationError("Quantity of Stock Demanded is Greater Than Available !")
        return False

    category_id = fields.Many2one('product.category', string="Category")
    partner_id = fields.Many2one('res.partner', string="Customer", related='move_id.partner_id')
    product_id = fields.Many2one('product.product', string="Product")
    quantity = fields.Float(string="Quantity")
    price_unit = fields.Float(string="price_unit")
    price_subtotal = fields.Float(string="Subtotal")
    move_id = fields.Many2one('account.move', string="move_id")
    x_brand = fields.Many2one("product.brand", string="Brand", related="product_id.product_brand")
    last_inv = fields.Char(string="Last Inv.")
    stock_after_reserve = fields.Float(string="ST.Act.Avl", related="product_id.virtual_available")
    qty_available = fields.Float(string="ST.Avail", related="product_id.qty_available")
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
    select_invoice = fields.Many2one("account.move.line", string="Select Inv.")

    @api.onchange('select_invoice')
    def onchange_select_invoice(self):
        for rec in self:
            rec.price_unit = rec.select_invoice.price_unit