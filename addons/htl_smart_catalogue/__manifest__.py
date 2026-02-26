# -*- coding: utf-8 -*-
{
    'name': 'HTL Smart Catalogue',
    'version': '1.0.0',
    'category': 'Sales',
    'summary': 'Digital Product Catalogue Management & PDF Generation',
    'description': """
HTL Smart Catalogue
===================
Digitize product catalogue creation and management.

Features:
---------
* Product master management (Series + Configurations)
* Dimension tracking with auto-conversion (cm ↔ inch, kg ↔ lb, m³ ↔ ft³)
* Image management for products and combinations
* PDF catalogue export
* Construction information management
* Combination layout management

Phase 1: Standalone catalogue generation
    """,
    'author': 'HTL',
    'website': 'https://www.htl.com.my',
    'depends': ['product', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/product_product_views.xml',
        'views/product_catalogue_combination_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
