# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SofaPriceQuote(models.Model):
    _name = 'sofa.price.quote'
    _description = 'Sofa Price Quote'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    # Quote identification
    name = fields.Char('Quote Number', required=True, copy=False, 
                      default=lambda self: _('New'), tracking=True)
    
    # Customer (optional - can quote without customer)
    partner_id = fields.Many2one('res.partner', 'Customer', tracking=True)
    
    # Sofa configuration
    series_id = fields.Many2one('sofa.series', 'Series', required=True, tracking=True)
    style_id = fields.Many2one('sofa.style', 'Style', required=True, tracking=True,
                              domain="[('series_id', '=', series_id)]")
    seat_number = fields.Float('Seat Number', required=True, default=3.0, tracking=True)
    
    # Additional fields from spec
    source = fields.Char('Source')
    plant_id = fields.Many2one('stock.warehouse', 'Plant')
    configuration_code = fields.Char('Configuration Code', 
                                     compute='_compute_configuration_code',
                                     store=True, readonly=True)
    package_type = fields.Char('Package Type')
    component_combination = fields.Char('Component Combination', 
                                       compute='_compute_component_combination',
                                       store=True)
    
    # Components
    component_ids = fields.One2many('sofa.quote.component', 'quote_id', 'Components')
    
    # Pricing factors - defaults from master data, can be overridden
    designer_margin = fields.Float('Designer Margin %', default=32.85, tracking=True,
                                   digits=(5, 2))
    tariff_percent = fields.Float('Tariff %', default=30.0, digits=(5, 2))
    commission_percent = fields.Float('Commission %', default=5.0, digits=(5, 2))
    loads_percent = fields.Float('Loads %', default=5.0, digits=(5, 2))
    freight_per_seat = fields.Monetary('Freight per Seat', default=30.0)
    local_charges_per_seat = fields.Monetary('Local Charges per Seat', default=8.0)
    
    # Computed costs
    material_cost_full = fields.Monetary('Total Material Cost', 
                                         compute='_compute_costs', store=True)
    freight_cost_full = fields.Monetary('Total Freight Cost',
                                       compute='_compute_costs', store=True)
    total_cost_full = fields.Monetary('Total Cost',
                                     compute='_compute_costs', store=True)
    
    # Computed pricing
    fob_net = fields.Monetary('FOB Net', readonly=True,
                              help='Calculated FOB Net price')
    selling_price_full = fields.Monetary(
        'Selling Price',
        help='Selling price. Use "Recalculate Price" button to auto-compute, or enter manually for "Calculate Margin" workflow.'
    )
    
    # Price Ratios
    ratio_ids = fields.One2many('sofa.price.ratio', 'quote_id', 'Price Ratios')
    
    # Currency
    currency_id = fields.Many2one('res.currency', 'Currency',
                                  default=lambda self: self.env.company.currency_id)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate quote number on create"""
        for vals in vals_list:
            if not vals.get('name', False) or vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('sofa.price.quote') or _('New')
        return super().create(vals_list)
    
    @api.depends('component_ids.template_id.code')
    def _compute_component_combination(self):
        """Generate component combination string"""
        for quote in self:
            codes = quote.component_ids.mapped('template_id.code')
            quote.component_combination = ', '.join(codes) if codes else ''
    
    @api.depends('series_id', 'style_id', 'seat_number', 'component_ids.article_group')
    def _compute_configuration_code(self):
        """Auto-generate configuration code from quote settings"""
        for quote in self:
            if not quote.series_id or not quote.style_id:
                quote.configuration_code = ''
                continue
            
            # Format: SERIES-STYLE-SEATS-MATERIAL
            # Example: 6114-MOD-3S-LTR or 3368-CLS-2S-FAB
            
            series_code = quote.series_id.name  # e.g., "6114"
            style_code = quote.style_id.name[:3].upper()  # e.g., "MOD" from "Modern"
            seat_code = f"{int(quote.seat_number)}S"  # e.g., "3S"
            
            # Determine material type from first component
            material_code = 'FAB'  # Default to fabric
            if quote.component_ids:
                first_comp = quote.component_ids[0]
                if first_comp.article_group == 'leather':
                    material_code = 'LTR'
            
            quote.configuration_code = f"{series_code}-{style_code}-{seat_code}-{material_code}"
    
    @api.depends('component_ids.total_cost')
    def _compute_costs(self):
        """Aggregate costs from all components"""
        for quote in self:
            components = quote.component_ids
            quote.material_cost_full = sum(components.mapped('material_cost'))
            quote.freight_cost_full = sum(components.mapped('freight_cost'))
            quote.total_cost_full = quote.material_cost_full + quote.freight_cost_full
    
    
    def _calculate_selling_price(self):
        """
        Calculate selling price using FOB formula from spec
        Formula: Selling Price = FOB Net × Factors + Per-Seat Charges
        Called by action_recalculate_price button
        """
        self.ensure_one()
        
        if not self.material_cost_full:
            self.fob_net = 0
            self.selling_price_full = 0
            return
        
        # Step 1: Calculate FOB Net
        margin_decimal = self.designer_margin / 100
        if margin_decimal >= 1:
            self.fob_net = 0
            self.selling_price_full = 0
            return
            
        fob_net = (self.material_cost_full / (1 - margin_decimal)) + self.freight_cost_full
        self.fob_net = fob_net
        
        # Step 2: Calculate Factors
        tariff_decimal = self.tariff_percent / 100
        comm_decimal = self.commission_percent / 100
        loads_decimal = self.loads_percent / 100
        
        if comm_decimal >= 1 or loads_decimal >= 1:
            self.selling_price_full = 0
            return
        
        factors = (1 + tariff_decimal + 
                  1/(1 - comm_decimal) - 1 + 
                  1/(1 - loads_decimal) - 1)
        
        # Step 3: Calculate Selling Price
        selling_price = (fob_net * factors + 
                        (self.freight_per_seat * self.seat_number) +
                        (self.local_charges_per_seat * self.seat_number))
        
        self.selling_price_full = selling_price

    
    @api.onchange('series_id')
    def _onchange_series_id(self):
        """Clear style when series changes"""
        self.style_id = False
        # Try to load default margin
        self._load_default_margin()
    
    def _load_default_margin(self):
        """Load default margin from master data"""
        self.ensure_one()
        if self.series_id:
            # Determine article group from first component's article
            article_group = 'fabric'  # Default
            if self.component_ids:
                first_comp = self.component_ids[0]
                if first_comp.article_front_id:
                    article_group = first_comp.article_front_id.category_id.article_type
            
            margin_record = self.env['sofa.margin'].search([
                ('series_id', '=', self.series_id.id),
                ('article_group', '=', article_group)
            ], limit=1)
            
            if margin_record:
                self.designer_margin = margin_record.margin_percent
    
    def _generate_price_ratios(self):
        """Auto-generate price ratio lines based on front article group (per ZCASE_Ratio spec)"""
        self.ensure_one()
        
        # Clear existing ratios
        self.ratio_ids.unlink()
        
        # Determine article group from first component's FRONT article (per spec)
        article_group = False
        if self.component_ids:
            first_comp = self.component_ids[0]
            if first_comp.article_group:
                article_group = first_comp.article_group
        
        if not article_group:
            return
        
        # Get all article categories for this group (ZCASE_Ratio structure)
        categories = self.env['sofa.article.category'].search([
            ('article_type', '=', article_group)
        ])
        
        # Create ratio lines for each category
        for category in categories:
            self.env['sofa.price.ratio'].create({
                'quote_id': self.id,
                'article_group': article_group,
                'category_id': category.id,
                'ratio': category.ratio,
            })
    
    def action_recalculate_price(self):
        """Recalculate selling price and regenerate ratios"""
        self.ensure_one()
        # Force recompute
        self._compute_costs()
        self._calculate_selling_price()
        # Generate price ratios
        self._generate_price_ratios()

    def action_calculate_margin(self):
        """Calculate margin from selling price (reverse calculation)"""
        self.ensure_one()
        if not self.selling_price_full or not self.material_cost_full:
            raise UserError(_('Please enter selling price and ensure components have costs.'))
        
        # Remove per-seat charges
        base_price = (self.selling_price_full - 
                     (self.freight_per_seat * self.seat_number) -
                     (self.local_charges_per_seat * self.seat_number))
        
        # Calculate factors
        tariff_decimal = self.tariff_percent / 100
        comm_decimal = self.commission_percent / 100
        loads_decimal = self.loads_percent / 100
        
        factors = (1 + tariff_decimal + 
                  1/(1 - comm_decimal) - 1 + 
                  1/(1 - loads_decimal) - 1)
        
        # Calculate FOB Net
        fob_net = base_price / factors
        
        # Calculate margin
        if fob_net - self.freight_cost_full == 0:
            margin = 0
        else:
            margin = (1 - (self.material_cost_full / (fob_net - self.freight_cost_full))) * 100
        
        self.designer_margin = margin
        return True
    
    def _generate_price_ratios(self):
        """Generate price ratios for all article categories"""
        self.ensure_one()
        # Clear existing ratios
        self.ratio_ids.unlink()
        
        # Get all article categories
        categories = self.env['sofa.article.category'].search([])
        
        for category in categories:
            self.env['sofa.price.ratio'].create({
                'quote_id': self.id,
                'article_group': category.article_type,
                'category_id': category.id,
                'ratio': category.ratio,
            })
