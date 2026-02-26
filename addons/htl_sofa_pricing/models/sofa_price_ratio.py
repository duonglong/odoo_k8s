# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaPriceRatio(models.Model):
    _name = 'sofa.price.ratio'
    _description = 'Sofa Price Ratio'
    _order = 'quote_id, article_group, category_id'

    quote_id = fields.Many2one('sofa.price.quote', 'Quote', 
                              required=True, ondelete='cascade')
    
    article_group = fields.Selection([
        ('fabric', 'Fabric'),
        ('leather', 'Leather'),
    ], string='Article Group', required=True)
    
    category_id = fields.Many2one('sofa.article.category', 'Category', required=True)
    category_name = fields.Char(related='category_id.name', readonly=True)
    
    ratio = fields.Float('Ratio', default=1.0, digits=(5, 2))
    
    # Computed price
    selling_price = fields.Monetary('Selling Price', 
                                   compute='_compute_selling_price',
                                   store=True)
    
    currency_id = fields.Many2one(related='quote_id.currency_id', readonly=True)
    
    @api.depends('quote_id.selling_price_full', 'ratio')
    def _compute_selling_price(self):
        """Calculate selling price with ratio applied"""
        for ratio_line in self:
            if ratio_line.quote_id and ratio_line.ratio:
                ratio_line.selling_price = ratio_line.quote_id.selling_price_full * ratio_line.ratio
            else:
                ratio_line.selling_price = 0
