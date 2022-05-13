# -*- coding: utf-8 -*-
# Copyright 2016, 2020 The Adepts
# License LGPL-3.0 or later (https://www.theadepts.net).

{
    "name": "BF",
    "summary": "BF",
    "version": "13.0.0.3",
    "category": "",
    "website": "https://www.theadepts.net",
	"description": """

    """,
	'images':[

	],
    "author": "The Adepts",
    "license": "LGPL-3",
    "installable": True,
    "depends": [
        'base',
        'purchase',
        'stock',
        'account',

    ],
    "data": [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/inherit_res_partner_form.xml',
        'views/inherit_account_move_form.xml',
        'views/inherit_account_move_line_tree.xml',
        'views/account_move_custom_line.xml',
        'views/inherit_stock_picking.xml',
        'views/inherit_product_template_form.xml',
        'views/server_action_product.xml',
        'views/inherit_purchase_order_view.xml',
        'views/change_action.xml',
        'views/tree_view_function_account_move.xml',

        # 'reports/py3o_reports_call.xml',
    ],

    #'live_test_url': 'https://youtu.be/JX-ntw2ORl8'

}
