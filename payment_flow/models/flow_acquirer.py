# -*- coding: utf-'8' "-*-"
import time
from datetime import datetime, timedelta
from odoo import api, models, fields
from odoo.tools import float_round, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_compare, float_repr
from odoo.tools.safe_eval import safe_eval
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

#try:
from .pyflow.client import Client
#except:
#    _logger.warning("No se puede cargar Flow")


class PaymentAcquirerFlow(models.Model):
    _inherit = 'payment.acquirer'

    provider = fields.Selection(
            selection_add=[('flow', 'Flow')]
        )
    flow_api_key = fields.Char(
            string="Api Key",
        )
    flow_private_key = fields.Char(
            string="Secret Key",
        )
    flow_payment_method = fields.Selection(
        [
            ('1', 'Webpay'),
            ('2', 'Servipag'),
            ('3', 'Multicaja'),
            ('5', 'Onepay'),
            ('8', 'Cryptocompra'),
            ('9', 'Todos los medios'),
        ],
        required=True,
        default='1',
    )

    @api.multi
    def _get_feature_support(self):
        res = super(PaymentAcquirerFlow, self)._get_feature_support()
        res['fees'].append('flow')
        return res

    @api.model
    def _get_flow_urls(self, environment):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if environment == 'prod':
            return {
                'flow_form_url': base_url +'/payment/flow/redirect',
                'flow_url': "https://www.flow.cl/api",
            }
        else:
            return {
                'flow_form_url': base_url +'/payment/flow/redirect',
                'flow_url': "http://flow.tuxpan.com/api",
            }

    @api.multi
    def flow_form_generate_values(self, values):
        #banks = self.flow_get_banks()#@TODO mostrar listados de bancos
        #_logger.warning("banks %s" %banks)
        values.update({
            'acquirer_id': self.id,
            'commerceOrder': values['reference'],
            'subject': '%s: %s' % (self.company_id.name, values['reference']),
            'amount': values['amount'],
            'email': values['partner_email'],
            'paymentMethod': self.flow_payment_method,
        })
        return values

    @api.multi
    def flow_get_form_action_url(self):
        return self._get_flow_urls(self.environment)['flow_form_url']

    def flow_get_client(self,):
        return Client(
                self.flow_api_key,
                self.flow_private_key,
                self._get_flow_urls(self.environment)['flow_url'],
                (self.environment == 'test'),
            )

    def flow_get_banks(self):
        client = self.flow_get_client()
        return client.banks.get()

    def flow_initTransaction(self, post):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        tx = self.env['payment.transaction'].search([('reference', '=', post.get('transaction_id'))])
        del(post['acquirer_id'])
        del(post['transaction_id'])
        post.update({
                    'paymentMethod': int(post.get('paymentMethod')),
                    'urlConfirmation': base_url + '/payment/flow/notify/%s' % str(self.id),
                    'urlReturn': base_url + '/payment/flow/return/%s' % str(tx.id),
                    })
        #post['uf'] += '/%s' % str(self.id)
        client = self.flow_get_client()
        res = client.payments.post(post)
        if hasattr(res, 'payment_url'):
            tx.write({'state': 'pending'})
        return res

    def flow_getTransaction(self, post):
        client = self.flow_get_client()
        return client.payments.get(post['token'])


class PaymentTxFlow(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _flow_form_get_tx_from_data(self, data):
        return self
        reference, txn_id = data.payment_id, data.transaction_id
        if not reference or not txn_id:
            error_msg = _('Flow: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.warning(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        txs = self.env['payment.transaction'].search([('reference', '=', reference)])
        if not txs or len(txs) > 1:
            error_msg = 'Flow: received data for reference %s' % (reference)
            if not txs:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.info(error_msg)
            raise ValidationError(error_msg)
        return txs[0]

    @api.multi
    def _flow_form_validate(self, data):
        codes = {
                '0': 'Transacción aprobada.',
                '-1': 'Rechazo de transacción.',
                '-2': 'Transacción debe reintentarse.',
                '-3': 'Error en transacción.',
                '-4': 'Rechazo de transacción.',
                '-5': 'Rechazo por error de tasa.',
                '-6': 'Excede cupo máximo mensual.',
                '-7': 'Excede límite diario por transacción.',
                '-8': 'Rubro no autorizado.',
            }
        status = data.status
        res = {
            'acquirer_reference': data.payment_id,
        }
        if status in [2]:
            _logger.info('Validated flow payment for tx %s: set as done' % (self.reference))
            res.update(state='done', date_validate=datetime.now())
            return self.write(res)
        elif status in [1, '-7']:
            _logger.warning('Received notification for flow payment %s: set as pending' % (self.reference))
            res.update(state='pending', state_message=data.get('pending_reason', ''))
            return self.write(res)
        else: #3 y 4
            error = 'Received unrecognized status for flow payment %s: %s, set as error' % (self.reference, codes[status].decode('utf-8'))
            _logger.warning(error)
            res.update(state='error', state_message=error)
            return self.write(res)
