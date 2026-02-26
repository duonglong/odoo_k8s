# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaOptionType(models.Model):
    _name = 'sofa.option.type'
    _description = 'Sofa Option Type'
    _order = 'sequence, name'

    name = fields.Char('Option Type', required=True, help='e.g., Leg Style, Foam Type')
    code = fields.Char('Code', required=True, help='e.g., leg, foam')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Option type code must be unique!')
    ]


class SofaOption(models.Model):
    _name = 'sofa.option'
    _description = 'Sofa Option'
    _order = 'option_type_id, sequence, name'

    name = fields.Char('Option Name', required=True, help='e.g., Wood Leg A')
    code = fields.Char('Code')
    
    option_type_id = fields.Many2one('sofa.option.type', 'Type', required=True)
    
    # Optional link to product (if option has material cost)
    product_id = fields.Many2one('product.product', 'Material Product',
                                 help='Odoo product if this option has a cost')
    
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
