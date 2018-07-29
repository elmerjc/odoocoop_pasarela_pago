# -*- coding: utf-8 -*-
import json
import logging
import pprint

import requests
import werkzeug
from werkzeug import urls

from odoo import http
from odoo.addons.payment.models.payment_acquirer import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    import urllib3
    pool = urllib3.PoolManager()
except:
    pass


class FlowController(http.Controller):
    _accept_url = '/payment/flow/test/accept'
    _decline_url = '/payment/flow/test/decline'
    _exception_url = '/payment/flow/test/exception'
    _cancel_url = '/payment/flow/test/cancel'

    @http.route([
        '/payment/flow/notify/<int:acquirer_id>',
        '/payment/flow/test/notify',
    ], type='http', auth='none', methods=['POST'], csrf=False)
    def flow_validate_data(self, acquirer_id=None, **post):
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        tx_data = acquirer.flow_getTransaction(post)
        res = request.env['payment.transaction'].sudo().form_feedback(tx_data, 'flow')
        return ''
        return Response(status=200)

    @http.route([
        '/payment/flow/return/<model("payment.transaction"):payment_tx>',
        '/payment/flow/test/return',
    ], type='http', auth='public', csrf=False, website=True)
    def flow_form_feedback(self, payment_tx=None, **post):
        _logger.warning("post %s, pay %s" %(post, payment_tx))
        tx_data = payment_tx.acquirer_id.flow_getTransaction(post)
        tx_data._token = post['token']
        payment_tx.form_feedback(tx_data, 'flow')
        return werkzeug.utils.redirect('/shop/confirmation')

    @http.route([
        '/payment/flow/final',
        '/payment/flow/test/final',
    ], type='http', auth='none', csrf=False, website=True)
    def final(self, **post):
        return werkzeug.utils.redirect('/shop/confirmation')

    @http.route(['/payment/flow/redirect'],  type='http', auth='public', methods=["POST"], csrf=False, website=True)
    def redirect_flow(self, **post):
        acquirer_id = int(post.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        result = acquirer.flow_initTransaction(post)
        if result.token:
            return werkzeug.utils.redirect(result.url+'?token='+result.token)
        #@TODO render error
        values={
            '': '',
        }
        #return request.render('payment_flow.flow_redirect', values)
