# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaComponentType(models.Model):
    _name = 'sofa.component.type'
    _description = 'Sofa Component Type'
    _order = 'sequence, name'

    name = fields.Char('Type Name', required=True, help='e.g., Back, Seat, Arm')
    code = fields.Char('Code', required=True, help='e.g., back, seat, arm')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Relations
    option_type_ids = fields.Many2many('sofa.option.type', 
                                       'sofa_component_option_type_rel',
                                       'component_type_id', 'option_type_id',
                                       string='Available Option Types')
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Component type code must be unique!')
    ]


class SofaComponentTemplate(models.Model):
    _name = 'sofa.component.template'
    _description = 'Sofa Component Template'
    _order = 'series_id, component_type_id, sequence, name'

    name = fields.Char('Component Name', required=True, help='e.g., Arm1, Seat1')
    code = fields.Char('Component Code', required=True, help='e.g., SM3368-A001')
    sap_bom_code = fields.Char('SAP BOM Code', help='For future SAP integration')
    
    component_type_id = fields.Many2one('sofa.component.type', 'Component Type', required=True)
    series_id = fields.Many2one('sofa.series', 'Series')
    style_id = fields.Many2one('sofa.style', 'Style', domain="[('series_id', '=', series_id)]")
    
    # Template BOM
    bom_line_ids = fields.One2many('sofa.component.bom.line', 'template_id', 'BOM Lines')
    
    # Options Configuration
    option_type_ids = fields.Many2many(
        'sofa.option.type',
        'sofa_template_option_type_rel',
        'template_id',
        'option_type_id',
        string='Required Option Types',
        help='Option types that must be selected for this component template'
    )
    default_option_ids = fields.Many2many(
        'sofa.option',
        'sofa_template_default_option_rel',
        'template_id',
        'option_id',
        string='Default Options',
        help='Default option selections for this template'
    )
    
    # Visual
    image = fields.Binary('Component Image')
    description = fields.Text('Description')
    
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Component code must be unique!')
    ]


class SofaComponentBOMLine(models.Model):
    _name = 'sofa.component.bom.line'
    _description = 'Component Template BOM Line'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one('sofa.component.template', 'Template',
                                  required=True, ondelete='cascade')
    
    # Material (THIS is an Odoo product)
    product_id = fields.Many2one('product.product', 'Material', required=True,
                                 domain=[('type', 'in', ['product', 'consu'])])
    
    quantity = fields.Float('Quantity', required=True, default=1.0, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', 'Unit', required=True)
    
    # Article assignment (sofa-specific)
    article_usage = fields.Selection([
        ('front', 'Front Article'),
        ('back', 'Back Article'),
        ('accessory', 'Accessory'),
    ], string='Article Usage', help='For fabric/leather materials')
    
    sequence = fields.Integer(default=10)
    notes = fields.Text('Notes')
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Set default UoM from product"""
        if self.product_id:
            self.uom_id = self.product_id.uom_id
