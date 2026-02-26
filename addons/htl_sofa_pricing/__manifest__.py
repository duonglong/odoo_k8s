# -*- coding: utf-8 -*-
{
    'name': 'HTL Sofa Pricing Calculator',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Sofa Configuration and Pricing Calculator for HTL',
    'description': """
HTL Sofa Pricing Calculator
============================

Features:
---------
* Configure sofa components (Arm, Seat, Back, etc.)
* Calculate material costs from component templates
* Calculate selling price with FOB and pricing factors
* Support for fabric/leather grade pricing
* Export quotes to Excel (3 templates) and PDF
* Master data management for series, styles, articles, options

Phase 1: Standalone price calculator with Excel/PDF export
Phase 2: SAP integration (future)
    """,
    'author': 'HTL',
    'website': 'https://www.htl.com.my',
    'depends': [
        'base',
        'product',
        'stock',
        'web',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/sequence.xml',
        
        # Views - Master Data
        'views/sofa_series_views.xml',
        'views/sofa_component_template_views.xml',
        'views/sofa_article_views.xml',
        'views/sofa_option_views.xml',
        'views/sofa_margin_views.xml',
        
        # Wizards (must be before quote views that reference them)
        'wizards/sofa_export_wizard_views.xml',
        
        # Views - Quotes
        'views/sofa_price_quote_views.xml',
        
        # Reports
        'report/report.xml',
        'report/quote_report_template.xml',
        
        # Menus
        'views/menus.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
        'demo/demo_products.xml',
        'demo/demo_option_products.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
