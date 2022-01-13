from odoo import models, fields, api, _

class CustomerName(models.Model):
    _name = "customer.name"
    _rec_name = "name_id"

    name_id = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    name = fields.Char(string="Name Id", required=True)
    related_partner_id = fields.Char(string="Related Partner", required=True)

    @api.model
    def create(self, vals):
        if vals.get('name_id', _('New')) == _('New'):
            var = self.env['ir.sequence'].next_by_code('customer.name') or _('New')
            vals['name_id'] = vals['name'][0] + var or _('New')
        res = super(CustomerName, self).create(vals)
        return res

class CustomerCode(models.Model):
    _name = "customer.code"

    _rec_name = "name_code"
    name_code = fields.Char(string="Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    name = fields.Char(string="Code", required=True)
    related_partner_id = fields.Char(string="Related Partner", required=True)

    @api.model
    def create(self, vals):
        if vals.get('name_id', _('New')) == _('New'):
            var = self.env['ir.sequence'].next_by_code('customer.id') or _('New')
            vals['name_code'] = var or _('New')
        res = super(CustomerCode, self).create(vals)
        return res


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_cash = fields.Boolean(string="Is Cash Customer")
    record_id = fields.Char(string="Record ID", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    name_id = fields.Char(string="Customer ID", readonly=True)
    name_code = fields.Char(string="Customer Code", readonly=True)
    property_account_payable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Payable",
        domain="[('internal_type', 'in', ('payable', 'liquidity')), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the payable account for the current partner",
        required=True)
    property_account_receivable_id = fields.Many2one('account.account', company_dependent=True,
        string="Account Receivable",
        domain="[('internal_type', '=', ('receivable', 'liquidity')), ('deprecated', '=', False)]",
        help="This account will be used instead of the default one as the receivable account for the current partner",
        required=True)

    @api.model
    def create(self, vals):
        if vals.get('record_id', _('New')) == _('New'):
            var = self.env['ir.sequence'].next_by_code('sequence.res.partner.record.id') or _('New')
            vals['record_id'] = var or _('New')

        env_customer_id = self.env['customer.name']
        env_customer_code = self.env['customer.code']

        customer_id = env_customer_id.create({
                                                'name': vals['name'],
                                                'related_partner_id': var,
                                            })
        customer_code = env_customer_code.create({
                                                    'name': vals['name'],
                                                    'related_partner_id': var,
                                                })

        vals['name_id'] = customer_id.name_id
        vals['name_code'] = customer_code.name_code

        res = super(ResPartner, self).create(vals)
        return res

class ProductColor(models.Model):
    _name = "product.color"

    name = fields.Char(string="Color")
    related_product_id = fields.Many2many("product.template", string="Related Product")



class ProductBrand(models.Model):
    _name = "product.brand"

    name = fields.Char(string="Brand")
    related_product_id = fields.Many2many("product.template", string="Related Product")