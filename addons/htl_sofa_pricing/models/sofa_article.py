# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaArticleCategory(models.Model):
    _name = 'sofa.article.category'
    _description = 'Sofa Article Category'
    _order = 'article_type, name'

    name = fields.Char('Category', required=True, help='e.g., GP1, GP2, LTR1')
    code = fields.Char('Code')
    article_type = fields.Selection([
        ('fabric', 'Fabric'),
        ('leather', 'Leather'),
    ], string='Article Type', required=True)
    
    # Price ratio
    ratio = fields.Float('Price Ratio', default=1.0, help='Multiplier for selling price')
    is_base = fields.Boolean('Is Base Category', help='Base category for price calculation')
    
    description = fields.Text('Description')
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('name_type_unique', 'unique(name, article_type)', 'Category must be unique per article type!')
    ]


class SofaArticle(models.Model):
    _name = 'sofa.article'
    _description = 'Sofa Article'
    _order = 'category_id, name'

    name = fields.Char('Article Name', required=True, help='e.g., Cotton Blend Gray')
    code = fields.Char('Article Code', help='e.g., FAB001')
    
    category_id = fields.Many2one('sofa.article.category', 'Category', required=True)
    article_type = fields.Selection(related='category_id.article_type', store=True, readonly=True)
    
    # Link to material product
    product_id = fields.Many2one('product.product', 'Material Product',
                                 help='Odoo product for this fabric/leather')
    
    description = fields.Text('Description')
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Article code must be unique!')
    ]
