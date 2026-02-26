# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SofaQuoteComponent(models.Model):
    _name = 'sofa.quote.component'
    _description = 'Sofa Quote Component'
    _order = 'quote_id, sequence, id'

    quote_id = fields.Many2one('sofa.price.quote', 'Quote',
                              required=True, ondelete='cascade')
    
    # Based on template
    template_id = fields.Many2one('sofa.component.template', 'Template', required=True)
    component_code = fields.Char(related='template_id.code', store=True, readonly=True)
    component_name = fields.Char(related='template_id.name', store=True, readonly=True)
    component_type_id = fields.Many2one(related='template_id.component_type_id', store=True, readonly=True)
    
    # Sofa-specific article selection (front/back)
    article_front_id = fields.Many2one('sofa.article', 'Front Article',
                                      help='Front-facing fabric/leather')
    article_back_id = fields.Many2one('sofa.article', 'Back Article',
                                     help='Back-facing fabric/leather (optional)')
    
    # Options - flexible Many2many relationship
    option_type_ids = fields.Many2many(
        'sofa.option.type',
        related='template_id.option_type_ids',
        string='Available Option Types',
        readonly=True,
        help='Option types available for this template'
    )
    option_ids = fields.Many2many(
        'sofa.option',
        'sofa_component_option_rel',
        'component_id',
        'option_id',
        string='Options',
        help='Selected options for this component'
    )
    
    # STD/FR
    std_fr = fields.Selection([
        ('std', 'Standard'),
        ('fr', 'Fire Resistant'),
    ], string='STD/FR', default='std')
    
    # Article group (derived from article selection)
    article_group = fields.Selection([
        ('fabric', 'Fabric'),
        ('leather', 'Leather'),
    ], compute='_compute_article_group', store=True)
    
    article_category_id = fields.Many2one('sofa.article.category', 
                                         'Article Category',
                                         compute='_compute_article_category',
                                         store=True)
    
    # Materials (copied from template, can be customized)
    material_ids = fields.One2many('sofa.quote.material', 'component_id', 'Materials')
    
    # Computed costs
    material_cost = fields.Monetary('Material Cost', 
                                   compute='_compute_costs', store=True)
    freight_cost = fields.Monetary('Freight Cost',
                                  compute='_compute_costs', store=True)
    total_cost = fields.Monetary('Total Cost', 
                                compute='_compute_costs', store=True)
    
    # Computed cost breakdowns (from spec ZCASE_H2)
    front_article_qty = fields.Float('Front Article Qty',
                                     compute='_compute_article_costs',
                                     store=True)
    front_material_cost = fields.Monetary('Front Material Cost',
                                         compute='_compute_article_costs',
                                         store=True)
    back_article_qty = fields.Float('Back Article Qty',
                                    compute='_compute_article_costs',
                                    store=True)
    back_material_cost = fields.Monetary('Back Material Cost',
                                        compute='_compute_article_costs',
                                        store=True)
    accessory_qty = fields.Float('Accessory Qty',
                                 compute='_compute_article_costs',
                                 store=True)
    accessory_cost = fields.Monetary('Accessory Cost',
                                    compute='_compute_article_costs',
                                    store=True)
    
    currency_id = fields.Many2one(related='quote_id.currency_id', readonly=True)
    sequence = fields.Integer(default=10)

    
    @api.depends('article_front_id', 'article_back_id')
    def _compute_article_group(self):
        """Determine if fabric or leather based on articles"""
        for comp in self:
            if comp.article_front_id:
                comp.article_group = comp.article_front_id.category_id.article_type
            else:
                comp.article_group = False
    
    @api.depends('article_front_id')
    def _compute_article_category(self):
        """Get article category from front article"""
        for comp in self:
            if comp.article_front_id:
                comp.article_category_id = comp.article_front_id.category_id
            else:
                comp.article_category_id = False
    
    @api.depends('material_ids.material_cost', 'material_ids.freight_cost')
    def _compute_costs(self):
        """Sum costs from materials"""
        for comp in self:
            comp.material_cost = sum(comp.material_ids.mapped('material_cost'))
            comp.freight_cost = sum(comp.material_ids.mapped('freight_cost'))
            comp.total_cost = comp.material_cost + comp.freight_cost
    
    @api.depends('material_ids.article_usage', 
                 'material_ids.quantity',
                 'material_ids.material_cost')
    def _compute_article_costs(self):
        """Compute costs by article usage (front/back/accessory)"""
        for comp in self:
            # Front article
            front_materials = comp.material_ids.filtered(
                lambda m: m.article_usage == 'front'
            )
            comp.front_article_qty = sum(front_materials.mapped('quantity'))
            comp.front_material_cost = sum(front_materials.mapped('material_cost'))
            
            # Back article
            back_materials = comp.material_ids.filtered(
                lambda m: m.article_usage == 'back'
            )
            comp.back_article_qty = sum(back_materials.mapped('quantity'))
            comp.back_material_cost = sum(back_materials.mapped('material_cost'))
            
            # Accessory
            accessory_materials = comp.material_ids.filtered(
                lambda m: m.article_usage == 'accessory' or not m.article_usage
            )
            comp.accessory_qty = sum(accessory_materials.mapped('quantity'))
            comp.accessory_cost = sum(accessory_materials.mapped('material_cost'))
    
    
    def _recompute_materials(self):
        """Centralized function to rebuild materials from all sources"""
        self.ensure_one()
        
        # Dictionary to aggregate materials by product: {product_id: {data}}
        material_dict = {}
        
        # 1. Add materials from template BOM
        if self.template_id:
            for bom_line in self.template_id.bom_line_ids:
                product_id = bom_line.product_id.id
                if product_id not in material_dict:
                    material_dict[product_id] = {
                        'product_id': product_id,
                        'product': bom_line.product_id,
                        'quantity': bom_line.quantity,
                        'uom_id': bom_line.uom_id.id,
                        'article_usage': bom_line.article_usage,
                        'sequence': bom_line.sequence,
                        'unit_price': bom_line.product_id.standard_price,
                        'sources': ['bom'],
                    }
                else:
                    # Aggregate quantity if product already exists
                    material_dict[product_id]['quantity'] += bom_line.quantity
                    material_dict[product_id]['sources'].append('bom')
        
        # 2. Add/update materials from front article
        if self.article_front_id and self.article_front_id.product_id:
            product_id = self.article_front_id.product_id.id
            if product_id not in material_dict:
                material_dict[product_id] = {
                    'product_id': product_id,
                    'product': self.article_front_id.product_id,
                    'quantity': 1.0,
                    'uom_id': self.article_front_id.product_id.uom_id.id,
                    'article_usage': 'front',
                    'sequence': 5,
                    'unit_price': self.article_front_id.product_id.standard_price,
                    'sources': ['article_front'],
                }
            else:
                # Product already exists (from BOM or other source), aggregate quantity
                material_dict[product_id]['quantity'] += 1.0
                material_dict[product_id]['sources'].append('article_front')
        
        # 3. Add/update materials from back article
        if self.article_back_id and self.article_back_id.product_id:
            product_id = self.article_back_id.product_id.id
            if product_id not in material_dict:
                material_dict[product_id] = {
                    'product_id': product_id,
                    'product': self.article_back_id.product_id,
                    'quantity': 1.0,
                    'uom_id': self.article_back_id.product_id.uom_id.id,
                    'article_usage': 'back',
                    'sequence': 6,
                    'unit_price': self.article_back_id.product_id.standard_price,
                    'sources': ['article_back'],
                }
            else:
                # Product already exists (from BOM, front article, or other source), aggregate quantity
                material_dict[product_id]['quantity'] += 1.0
                material_dict[product_id]['sources'].append('article_back')
        
        # 4. Add/update materials from options
        for option in self.option_ids:
            if option.product_id:
                product_id = option.product_id.id
                if product_id not in material_dict:
                    material_dict[product_id] = {
                        'product_id': product_id,
                        'product': option.product_id,
                        'quantity': 1.0,
                        'uom_id': option.product_id.uom_id.id,
                        'article_usage': 'option',
                        'sequence': 100,
                        'unit_price': option.product_id.standard_price,
                        'sources': ['option'],
                    }
                else:
                    # Aggregate quantity
                    material_dict[product_id]['quantity'] += 1.0
                    material_dict[product_id]['sources'].append('option')
        
        # 5. Rebuild material_ids from aggregated data
        material_lines = []
        for mat_data in sorted(material_dict.values(), key=lambda x: x['sequence']):
            material_lines.append((0, 0, {
                'product_id': mat_data['product_id'],
                'quantity': mat_data['quantity'],
                'uom_id': mat_data['uom_id'],
                'article_usage': mat_data['article_usage'],
                'sequence': mat_data['sequence'],
                'unit_price': mat_data['unit_price'],
            }))
        
        # Clear and set new materials
        self.material_ids = [(5, 0, 0)] + material_lines
    
    @api.onchange('article_front_id', 'article_back_id', 'option_ids')
    def _onchange_materials_sources(self):
        """Recompute materials when articles or options change"""
        self._recompute_materials()
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load BOM and default options when template changes"""
        if self.template_id:
            # Load default options from template
            if self.template_id.default_option_ids:
                self.option_ids = [(6, 0, self.template_id.default_option_ids.ids)]
            
            # Recompute materials (will load BOM + defaults)
            self._recompute_materials()
