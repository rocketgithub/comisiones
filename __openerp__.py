# -*- coding: utf-8 -*-
{
    'name': "comisiones",

    'summary': """
        Comisiones""",

    'description': """
        Comisiones
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','hr_contract'],

    # always loaded
    'data': [
        'views/product_view.xml',
        'views/comisiones_view.xml',
        'views/account_invoice_view.xml',
        'views/hr_view.xml',
        'wizard/calculo.xml',
        'wizard/calculo2.xml',
    ],
}