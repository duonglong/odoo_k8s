# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaQuoteMaterial(models.Model):
    _name = 'sofa.quote.material'
    _description = 'Sofa Quote Material'
    _order = 'component_id, sequence, id'

    component_id = fields.Many2one('sofa.quote.component', 'Component',
                                  required=True, ondelete='cascade')
    
    # Material product
    product_id = fields.Many2one('product.product', 'Material', required=True)
    
    quantity = fields.Float('Quantity', required=True, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', 'Unit', required=True)
    
    # Price snapshot (from spec ZCASE_ITEM)
    unit_price = fields.Monetary('Unit Price (Snapshot)',
                                 help='Price at quote creation')
    price_unit_qty = fields.Float('Price Unit', default=1.0,
                                  help='For materials priced per 10, 100, etc.')
    
    current_unit_price = fields.Monetary('Current Price',
                                        compute='_compute_current_price')
    price_changed = fields.Boolean('Price Changed',
                                   compute='_compute_price_changed')
    
    # Costs
    material_cost = fields.Monetary('Material Cost', 
                                   compute='_compute_costs', store=True)
    freight_cost = fields.Monetary('Freight Cost', 
                                  compute='_compute_costs', store=True)
    
    # Article usage (sofa-specific)
    article_usage = fields.Selection([
        ('front', 'Front Article'),
        ('back', 'Back Article'),
        ('accessory', 'Accessory'),
        ('option', 'Option'),
    ], string='Article Usage')
    
    # Additional fields from spec
    origin = fields.Char('Origin of Material')
    indicator = fields.Char('Indicator')
    vat_rate = fields.Float('VAT Rate %')
    exchange_rate = fields.Float('Exchange Rate')
    
    # Duty calculations (for export template 1)
    duty_rate = fields.Float('Duty Rate %', default=0.0)
    unit_price_with_duty = fields.Monetary('Unit Price + Duty',
                                          compute='_compute_duty_costs',
                                          store=True)
    freight_per_unit_with_duty = fields.Monetary('Freight/Unit + Duty',
                                                 compute='_compute_duty_costs',
                                                 store=True)
    
    currency_id = fields.Many2one(related='component_id.currency_id', readonly=True)
    sequence = fields.Integer(default=10)
    notes = fields.Text('Notes')
    
    @api.model
    def create(self, vals):
        """Snapshot price on create"""
        if 'product_id' in vals and 'unit_price' not in vals:
            product = self.env['product.product'].browse(vals['product_id'])
            vals['unit_price'] = product.standard_price
        return super().create(vals)
    
    @api.depends('product_id.standard_price')
    def _compute_current_price(self):
        """Get current price from product"""
        for material in self:
            if material.product_id:
                material.current_unit_price = material.product_id.standard_price
            else:
                material.current_unit_price = 0
    
    @api.depends('unit_price', 'current_unit_price')
    def _compute_price_changed(self):
        """Detect if price has changed since snapshot"""
        for material in self:
            material.price_changed = (
                material.unit_price != material.current_unit_price
            )
    
    @api.depends('quantity', 'unit_price', 'price_unit_qty')
    def _compute_costs(self):
        """Calculate material and freight costs"""
        for material in self:
            # Calculate actual unit price
            if material.price_unit_qty:
                actual_price = material.unit_price / material.price_unit_qty
            else:
                actual_price = material.unit_price
            
            # Material cost
            material.material_cost = material.quantity * actual_price
            
            # Freight cost (2.7% of material cost - from spec)
            material.freight_cost = material.material_cost * 0.027
    
    @api.depends('unit_price', 'freight_cost', 'duty_rate', 'quantity', 'price_unit_qty')
    def _compute_duty_costs(self):
        """Calculate costs with duty applied"""
        for material in self:
            duty_decimal = material.duty_rate / 100
            
            # Unit price with duty
            if material.price_unit_qty:
                base_unit_price = material.unit_price / material.price_unit_qty
            else:
                base_unit_price = material.unit_price
            material.unit_price_with_duty = base_unit_price * (1 + duty_decimal)
            
            # Freight per unit with duty
            if material.quantity:
                freight_per_unit = material.freight_cost / material.quantity
                material.freight_per_unit_with_duty = freight_per_unit * (1 + duty_decimal)
            else:
                material.freight_per_unit_with_duty = 0
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Set default UoM and price from product"""
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.standard_price
    
    def action_update_price(self):
        """Manually update price from current product price"""
        for material in self:
            if material.product_id:
                material.unit_price = material.product_id.standard_price
