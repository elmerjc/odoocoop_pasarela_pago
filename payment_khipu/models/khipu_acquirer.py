# -*- coding: utf-'8' "-*-"

import time
from datetime import datetime, timedelta
import logging
from odoo import SUPERUSER_ID
from odoo import api, models, fields
from odoo.tools import float_round, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_compare, float_repr
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

try:
    from .khipu import Khipu
except:
    _logger.warning("No se puede cargar Khipu")


class PaymentAcquirerKhipu(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
            selection_add=[('khipu', 'Khipu')]
        )
    khipu_receiver_id = fields.Char(
            string="Id del Cobrador",
        )
    khipu_private_key = fields.Char(
            string="LLave",
        )

    @api.multi
    def _get_feature_support(self):
        res = super(PaymentAcquirerKhipu, self)._get_feature_support()
        res['fees'].append('khipu')
        return res

    @api.model
    def _get_khipu_urls(self, environment):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if environment == 'prod':
            return {
                'khipu_form_url': base_url +'/payment/khipu/redirect',
            }
        else:
            return {
                'khipu_form_url': base_url +'/payment/khipu/redirect',
            }

    @api.multi
    def khipu_form_generate_values(self, values):
        _logger.warning("set")
        _logger.warning(values)
        banks = self.khipu_get_banks()
        _logger.warning("banks %s" %banks)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        d = datetime.now() + timedelta(hours=1)
        values.update({
            'business': self.company_id.name,
            'subject': '%s: %s' % (self.company_id.name, values['reference']),
            'body': values['reference'],
            'amount': values['amount'],
            'payer_email': values['partner_email'],
            'banks': banks,
            'expires_date': time.mktime(d.timetuple()) ,
            'custom': values.get('custom', 'No Custom Data'),
            'notify_url': base_url + '/payment/khipu/notify',
            'return_url': base_url + '/payment/khipu/return_url',
            'cancel_url': base_url + '/payment/khipu/cancel_url',
            'picture_url': base_url + '/web/image/res.company/%s/logo' % values.get('company_id', self.env.user.company_id.id),
        })
        return values

    @api.multi
    def khipu_get_form_action_url(self):
        return self._get_khipu_urls(self.environment)['khipu_form_url']

    def khipu_get_client(self,):
        return Khipu(
                self.khipu_receiver_id,
                self.khipu_private_key,
            )

    def khipu_get_banks(self):
        client = self.khipu_get_client()
        return client.service('ReceiverBanks')

    def khipu_initTransaction(self, post):
        client = self.khipu_get_client()
        return client.service('CreatePaymentURL', **post)


class PaymentTxKhipu(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _khipu_form_get_tx_from_data(self, data):
        reference, txn_id = data.get('item_number'), data.get('txn_id')
        if not reference or not txn_id:
            error_msg = _('Khipu: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Khipu: received data for reference %s' % (reference)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    @api.multi
    def _khipu_form_validate(self, data):
        codes = {
                '0' : 'Transacción aprobada.',
                '-1' : 'Rechazo de transacción.',
                '-2' : 'Transacción debe reintentarse.',
                '-3' : 'Error en transacción.',
                '-4' : 'Rechazo de transacción.',
                '-5' : 'Rechazo por error de tasa.',
                '-6' : 'Excede cupo máximo mensual.',
                '-7' : 'Excede límite diario por transacción.',
                '-8' : 'Rubro no autorizado.',
            }
        status = data.get('payment_status')
        res = {
            'acquirer_reference': data.get('txn_id'),
            'paypal_txn_type': data.get('payment_type'),
        }
        if status in ['0']:
            _logger.info('Validated khipu payment for tx %s: set as done' % (tx.reference))
            res.update(state='done', date_validate=data.transactionDate)
            return tx.write(res)
        elif status in ['-6', '-7']:
            _logger.warning('Received notification for khipu payment %s: set as pending' % (tx.reference))
            res.update(state='pending', state_message=data.get('pending_reason', ''))
            return tx.write(res)
        else:
            error = 'Received unrecognized status for khipu payment %s: %s, set as error' % (tx.reference, codes[status].decode('utf-8'))
            _logger.warning(error)
            res.update(state='error', state_message=error)
            return tx.write(res)
