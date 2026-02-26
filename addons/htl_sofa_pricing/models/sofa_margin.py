# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaMargin(models.Model):
    """Margin Master Data (from SAP in Phase 2)"""
    _name = 'sofa.margin'
    _description = 'Sofa Margin Master Data'
    _order = 'series_id, article_group'

    series_id = fields.Many2one('sofa.series', 'Series', required=True)
    article_group = fields.Selection([
        ('fabric', 'Fabric'),
        ('leather', 'Leather'),
    ], string='Article Group', required=True)
    
    margin_percent = fields.Float('Margin %', required=True, digits=(5, 2))
    
    # For Phase 2 SAP integration
    sap_synced = fields.Boolean('SAP Synced', default=False)
    sap_last_sync = fields.Datetime('Last SAP Sync')
    
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('series_article_unique', 
         'unique(series_id, article_group)', 
         'Margin must be unique per series and article group!')
    ]
