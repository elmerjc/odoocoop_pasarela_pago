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
    pool = urllib3.PoolManager()
except:
    pass


class KhipuController(http.Controller):
    _accept_url = '/payment/khipu/test/accept'
    _decline_url = '/payment/khipu/test/decline'
    _exception_url = '/payment/khipu/test/exception'
    _cancel_url = '/payment/khipu/test/cancel'

    def khipu_validate_data(self, **post):
        reference, txn_id = data.get('item_number'), data.get('txn_id')
        if not reference or not txn_id:
            error_msg = _('Khipu: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.warning(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        tx_ids = self.pool['payment.transaction'].search(cr, uid, [('reference', '=', reference)], context=context)
        if not tx_ids or len(tx_ids) > 1:
            error_msg = 'Khipu: received data for reference %s' % (reference)
            if not tx_ids:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.warning(error_msg)
            raise ValidationError(error_msg)
        return self.browse(cr, uid, tx_ids[0], context=context)

    @http.route([
        '/payment/khipu/return/<model("payment.acquirer"):acquirer_id>',
        '/payment/khipu/test/return',
    ], type='http', auth='public', csrf=False, website=True)
    def khipu_form_feedback(self, acquirer_id=None, **post):
        """ Webpay contacts using GET, at least for accept """
        _logger.info('Webpay: entering form_feedback with post data %s', pprint.pformat(post))  # debug
        cr, uid, context = request.cr, SUPERUSER_ID, request.context
        resp = request.registry['payment.transaction'].getTransaction(cr, uid, [], acquirer_id, post['token_ws'], context=context)
        request.registry['payment.transaction'].form_feedback(cr, uid, resp, 'khipu', context=context)
        urequest = urllib2.Request(resp.urlRedirection, werkzeug.url_encode({'token_ws': post['token_ws'], }))
        uopen = urllib2.urlopen(urequest)
        feedback = uopen.read()
        if resp.VCI in ['TSY'] and str(resp.detailOutput[0].responseCode) in [ '0' ]:
            values={
                'khipu_redirect': feedback,
            }
            return request.website.render('payment_khipu.khipu_redirect', values)
        return werkzeug.utils.redirect('/shop/payment')

    @http.route([
        '/payment/khipu/final',
        '/payment/khipu/test/final',
    ], type='http', auth='public', csrf=False, website=True)
    def final(self, **post):
        """ Webpay contacts using GET, at least for accept """
        _logger.info('Webpay: entering End with post data %s', pprint.pformat(post))  # debug
        cr, uid, context = request.cr, SUPERUSER_ID, request.context
        return werkzeug.utils.redirect('/shop/payment/validate')

    @http.route(['/payment/khipu/redirect'],  type='http', auth='public', methods=["POST"], csrf=False, website=True)
    def redirect_khipu(self, **post):
        acquirer_id = int(post.get('acquirer_id'))
        acquirer = request.env['payment.acquirer'].browse(acquirer_id)
        result =  acquirer.khipu_initTransaction(post)
        _logger.warning("reditect%s" %result)
        uopen = pool.request('GET', result['url'])
        resp = uopen.data
        values={
            'khipu_redirect': resp,
        }
        return request.website.render('payment_khipu.khipu_redirect', values)
