# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    # Dimensions with auto-conversion
    width_cm = fields.Float('Width (cm)', digits=(10, 2))
    width_inch = fields.Float('Width (inch)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    seat_width_cm = fields.Float('Seat Width (cm)', digits=(10, 2))
    seat_width_inch = fields.Float('Seat Width (inch)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    depth_cm = fields.Char('Depth (cm)', help='Supports range format: e.g., 50-91')
    depth_inch = fields.Char('Depth (inch)', compute='_compute_dimensions', store=True)
    
    seat_depth_cm = fields.Float('Seat Depth (cm)', digits=(10, 2))
    seat_depth_inch = fields.Float('Seat Depth (inch)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    back_height_cm = fields.Char('Back Height (cm)', help='Supports range format: e.g., 80-95')
    back_height_inch = fields.Char('Back Height (inch)', compute='_compute_dimensions', store=True)
    
    seat_height_cm = fields.Float('Seat Height (cm)', digits=(10, 2))
    seat_height_inch = fields.Float('Seat Height (inch)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    weight_kg = fields.Float('Weight (kg)', digits=(10, 2))
    weight_lb = fields.Float('Weight (lb)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    volume_m3 = fields.Float('Volume (m³)', digits=(10, 2))
    volume_ft3 = fields.Float('Volume (ft³)', compute='_compute_dimensions', store=True, digits=(10, 2))
    
    @api.depends('width_cm', 'seat_width_cm', 'depth_cm', 'seat_depth_cm',
                 'back_height_cm', 'seat_height_cm', 'weight_kg', 'volume_m3')
    def _compute_dimensions(self):
        """Auto-convert cm→inch, kg→lb, m³→ft³"""
        for product in self:
            # CM to INCH (1 cm = 0.393701 inch)
            product.width_inch = product.width_cm * 0.393701 if product.width_cm else 0
            product.seat_width_inch = product.seat_width_cm * 0.393701 if product.seat_width_cm else 0
            product.seat_depth_inch = product.seat_depth_cm * 0.393701 if product.seat_depth_cm else 0
            product.seat_height_inch = product.seat_height_cm * 0.393701 if product.seat_height_cm else 0
            
            # Handle ranges for depth and back_height
            product.depth_inch = product._convert_range(product.depth_cm)
            product.back_height_inch = product._convert_range(product.back_height_cm)
            
            # KG to LB (1 kg = 2.20462 lb)
            product.weight_lb = product.weight_kg * 2.20462 if product.weight_kg else 0
            
            # M³ to FT³ (1 m³ = 35.3147 ft³)
            product.volume_ft3 = product.volume_m3 * 35.3147 if product.volume_m3 else 0
    
    def _convert_range(self, cm_value):
        """Convert range like '50-91' cm to '19.69-35.83' inch"""
        if not cm_value:
            return ''
        if '-' in str(cm_value):
            try:
                parts = str(cm_value).split('-')
                min_cm, max_cm = float(parts[0]), float(parts[1])
                min_inch = min_cm * 0.393701
                max_inch = max_cm * 0.393701
                return f"{min_inch:.2f}-{max_inch:.2f}"
            except (ValueError, IndexError):
                return ''
        else:
            try:
                cm = float(cm_value)
                return f"{cm * 0.393701:.2f}"
            except ValueError:
                return ''
    
    def action_view_images(self):
        """View all images for this configuration"""
        self.ensure_one()
        return {
            'name': f'Images - {self.default_code or self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'product.image',
            'view_mode': 'kanban,tree,form',
            'domain': [('product_variant_id', '=', self.id)],
            'context': {
                'default_product_variant_id': self.id,
            },
        }
