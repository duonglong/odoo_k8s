# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SofaSeries(models.Model):
    _name = 'sofa.series'
    _description = 'Sofa Series'
    _order = 'name'

    name = fields.Char('Series Code', required=True, help='e.g., 6114, 3368')
    full_name = fields.Char('Full Name', help='e.g., 6114 UP & DOWN')
    description = fields.Text('Description')
    active = fields.Boolean(default=True)
    
    # Relations
    style_ids = fields.One2many('sofa.style', 'series_id', 'Styles')
    template_ids = fields.One2many('sofa.component.template', 'series_id', 'Component Templates')
    
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Series code must be unique!')
    ]


class SofaStyle(models.Model):
    _name = 'sofa.style'
    _description = 'Sofa Style'
    _order = 'series_id, name'

    name = fields.Char('Style Code', required=True, help='e.g., 6114-A, 3368-STD')
    series_id = fields.Many2one('sofa.series', 'Series', required=True, ondelete='cascade')
    description = fields.Text('Description')
    active = fields.Boolean(default=True)
    
    _sql_constraints = [
        ('series_style_unique', 'unique(series_id, name)', 'Style code must be unique per series!')
    ]
