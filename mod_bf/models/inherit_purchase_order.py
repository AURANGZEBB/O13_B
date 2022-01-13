from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def assign_sale_price(self):
        for rec in self:
            for line in rec.order_line:
                line.product_id.list_price = line.sale_price

    def allocate_freight(self):
        print("Freight Computing .......")
        for rec in self:
            if rec.state == 'draft' or rec.state == 'sent':
                if rec.allocated == True:
                    raise ValidationError("Freight Already Allocated, If you want to change, First Unallocate!!!!")
                else:
                    if rec.order_line and rec.freight_other_charges > 0:
                        total_untaxed = rec.amount_untaxed
                        freight_other_charges = rec.freight_other_charges
                        rec.allocated = True
                        for line in rec.order_line:
                            if line.order_id.id == rec.id and rec.product_id.type == 'product':
                                line_total = line.price_subtotal
                                allocate = freight_other_charges * line_total / total_untaxed
                                line.price_unit = line.price_unit + allocate / line.product_qty

                    else:
                        raise ValidationError("Order Line or Freight/Other Charges is Empty !!!!!!!!!!!!")

            elif rec.state == 'purchase' or rec.state == 'done':
                if rec.allocated:
                    raise ValidationError("You have Already Allocated !!!!")
                else:
                    exist_in_picking = rec.env['stock.picking'].search([('origin', '=', rec.name),
                                                                        ('state', '!=', 'done'),
                                                                        ('state', '!=', 'cancel')])
                    done_picking = rec.env['stock.picking'].search([('origin', '=', rec.name),
                                                                        ('state', '=', 'done')])
                    if exist_in_picking:
                        raise ValidationError(str(exist_in_picking) + " Pickings are not Done, Might be some partial shipments are pending------ Process //opened pickings// first then try again !!!!!!!!!!")
                    elif done_picking:
                        if rec.order_line and rec.freight_other_charges > 0:
                            total_untaxed = rec.amount_untaxed
                            freight_other_charges = rec.freight_other_charges
                            print(freight_other_charges)
                            print(total_untaxed)
                            rec.allocated = True
                            for line in rec.order_line:
                                if line.order_id.id == rec.id and line.product_id.type == 'product':
                                    line_total = line.price_subtotal
                                    print(line_total)
                                    allocate = freight_other_charges * line_total / total_untaxed
                                    print(allocate)
                                    line.amount_to_allocate = allocate
                                    qty = line.product_id.qty_available
                                    print(qty)
                                    existing_unit_price = line.product_id.standard_price
                                    print(existing_unit_price)
                                    existing_total = qty * existing_unit_price
                                    print(existing_total)
                                    new_price = (existing_total + allocate) / qty
                                    print(new_price)
                                    # print(self.zcc)

                                    # Actual changing the cost per unit
                                    line.product_id._change_standard_price(new_price=new_price,
                                                                    counterpart_account_id=line.product_id.categ_id.property_account_expense_categ_id.id)


                        else:
                            raise ValidationError("Order Line or Freight/Other Charges is Empty !!!!!!!!!!!!")
                    else:
                        raise ValidationError("There is no Done Picking, you might have cancelled all the pickings")
    def reverse_freight(self):
        # For deducting the amount of freight added before
        for rec in self:
            if rec.allocated == True:
                total_untaxed = rec.amount_untaxed
                freight_other_charges = rec.freight_other_charges
                rec.allocated = False
                for line in rec.order_line:
                    if line.order_id.id == rec.id and line.product_id.type == 'product':
                        line_total = line.price_subtotal
                        allocate = freight_other_charges * line_total / total_untaxed
                        line.price_unit = line.price_unit - allocate / line.product_qty
            else:
                raise ValidationError("Freight Already Reversed !!!!!!!!!!!!!")

    freight_other_charges = fields.Float(string="Freight/Other Charges")
    allocated = fields.Boolean(string="Allocated")


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    category = fields.Many2one("product.category", string="Category")
    brand = fields.Many2one("product.brand", string="Brand", related="product_id.product_brand")
    sale_price = fields.Float(string="Sale_price")
    amount_to_allocate = fields.Float(string="Amount to Allocate")

