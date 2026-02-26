# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductCatalogueCombination(models.Model):
    _name = 'product.catalogue.combination'
    _description = 'Product Combination Layout'
    _order = 'sequence, id'
    
    product_tmpl_id = fields.Many2one(
        'product.template',
        'Series',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char('Layout Name', required=True)
    image = fields.Binary('Image', required=True, attachment=True)
    image_filename = fields.Char('Filename')
    sequence = fields.Integer('Sequence', default=10)
    
    @api.constrains('image', 'image_filename')
    def _check_image_format(self):
        """Validate image format"""
        allowed_formats = ['jpg', 'jpeg', 'png', 'gif', 'webp']
        for combination in self:
            if combination.image_filename:
                ext = combination.image_filename.split('.')[-1].lower()
                if ext not in allowed_formats:
                    raise ValidationError(
                        _(f"Invalid image format: {ext}. Allowed formats: {', '.join(allowed_formats)}")
                    )
    
    def action_save_and_close(self):
        """Save and close the form"""
        return {'type': 'ir.actions.act_window_close'}
