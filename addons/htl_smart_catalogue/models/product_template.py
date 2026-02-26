# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    # Catalogue flag
    is_catalogue_product = fields.Boolean(
        'Catalogue Product',
        default=False,
        help='Check this to mark as a catalogue product'
    )
    
    # Series information
    series_code = fields.Char('Series', size=10, index=True)
    style_name = fields.Char('Style', size=30)
    
    # Construction information for PDF
    construction_info = fields.Html(
        'Construction Information',
        help='Construction details, materials, frame info, etc.'
    )
    
    # Combination layouts
    combination_image_ids = fields.One2many(
        'product.catalogue.combination',
        'product_tmpl_id',
        'Combination Layouts'
    )
    
    def action_add_combination(self):
        """Open wizard to upload combination image"""
        self.ensure_one()
        return {
            'name': 'Add Combination Layout',
            'type': 'ir.actions.act_window',
            'res_model': 'product.catalogue.combination',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_tmpl_id': self.id,
            },
        }
    
    def action_export_pdf(self):
        """Export product catalogue as PDF"""
        self.ensure_one()
        return self.env.ref('htl_smart_catalogue.action_report_product_catalogue').report_action(self)
