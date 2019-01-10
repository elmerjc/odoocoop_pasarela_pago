import hmac
import json
from hashlib import sha256
from urllib.parse import quote
from .payments import Payments
#from .banks import Banks
#from .receivers import Receivers
try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    pass
import logging
_logger = logging.getLogger(__name__)


class Client(object):
    def __init__(self, api_key=None, secret=None, url=False, debug=False):
        self._api_key = api_key
        self._secret = secret
        self._url = url
        self._debug = debug

    @property
    def api_key(self):
        return self._api_key

    @property
    def secret(self):
        return self._secret

    @property
    def priv_key(self):
        return self._priv_key

    @property
    def pub_key(self):
        return self._pub_key

    @property
    def url(self):
        return self._url

    @property
    def is_debug(self):
        return self._debug

    @property
    def payments(self):
        if not hasattr(self, '_payments'):
            self._payments = Payments(self)
        return self._payments

    '''
    * Set el número de Orden del comercio
    *
    * @param string orderNumer El número de la Orden del Comercio
    *
    * @return bool (true/false)
    '''
    def setOrderNumber(orderNumber):
        if(not empty(orderNumber)):
            self.order["OrdenNumero"] = orderNumber
        self.flow_log("Asigna Orden N°: "+ self.order["OrdenNumero"], '')
        return not empty(orderNumber)


    '''
    * Set el concepto de pago
    *
    * @param string concepto El concepto del pago
    *
    * @return bool (true/false)
    '''
    def setConcept(concepto):
        if(not empty(concepto)):
            self.order["Concepto"] = concepto
        return not empty(concepto)


    '''
    * Set el monto del pago
    *
    * @param string monto El monto del pago
    *
    * @return bool (true/false)
    '''
    def setAmount(monto):
        if(not empty(monto)):
            self.order["Monto"] = monto
        return not empty(monto)


    '''
    * Set Medio de Pago, por default el Medio de Pago será el configurada en config.php
    *
    * @param string medio El Medio de Pago de esta orden
    *
    * @return bool (true/false)
    '''
    def setMedio(medio):
        if(not empty(medio)):
            self.order["MedioPago"] = medio
            return True
        return False



    '''
     * Set pagador, el email del pagador de esta orden
     *
     * @param string email El email del pagador de la orden
     *
     * @return bool (true/false)
     '''
    def setPagador(email):
        if(not empty(email)):
            self.order["Pagador"] = email
            return True
        return False


    '''
    * Get el número de Orden del Comercio
    *
    * @return string el número de Orden del comercio
    '''
    def getOrderNumber():
        return self.order["OrdenNumero"]


    '''
    * Get el concepto de Orden del Comercio
    *
    * @return string el concepto de Orden del comercio
    '''
    def getConcept():
        return self.order["Concepto"]


    '''
    * Get el monto de Orden del Comercio
    *
    * @return string el monto de la Orden del comercio
    '''
    def getAmount():
        return self.order["Monto"]


    '''
    * Get el Medio de Pago para de Orden del Comercio
    *
    * @return string el Medio de pago de esta Orden del comercio
    '''
    def getMedio():
        return self.order["MedioPago"]


    '''
    * Get el estado de la Orden del Comercio
    *
    * @return string el estado de la Orden del comercio
    '''
    def getStatus():
        return self.order["Status"]


    '''
    * Get el número de Orden de Flow
    *
    * @return string el número de la Orden de Flow
    '''
    def getFlowNumber():
        return self.order["FlowNumero"]


    '''
    * Get el email del pagador de la Orden
    *
    * @return string el email del pagador de la Orden de Flow
    '''
    def getPayer():
        return self.order["Pagador"]



    '''
    * Crea una nueva Orden para ser enviada a Flow
    *
    * @param string orden_compra El número de Orden de Compra del Comercio
    * @param string monto El monto de Orden de Compra del Comercio
    * @param string concepto El concepto de Orden de Compra del Comercio
    * @param string email_pagador El email del pagador de Orden de Compra del Comercio
    * @param mixed medioPago El Medio de Pago (1,2,9)
    *
    * @return string flow_pack Paquete de datos firmados listos para ser enviados a Flow
    '''
    def new_order(orden_compra, monto,  concepto, email_pagador, medioPago = "Non"):
        self.flow_log("Iniciando nueva Orden", "new_order")
        if(not isset(orden_compra,monto,concepto)):
            self.flow_log("Error: No se pasaron todos los parámetros obligatorios","new_order")

        if(medioPago == "Non"):
            medioPago = flow_medioPago

        if(not is_numeric(monto)):
            self.flow_log("Error: El parámetro monto de la orden debe ser numérico","new_order")
            raise UserError("El monto de la orden debe ser numérico")
        if monto < 350:
            raise 'El Monto Mínimo es de $350'
        self.order["OrdenNumero"] = orden_compra
        self.order["Concepto"] = concepto
        self.order["Monto"] = monto
        self.order["MedioPago"] = medioPago
        self.order["Pagador"] = email_pagador
        return self.flow_pack()


    '''
    * Método para responder a Flow el resultado de la confirmación del comercio
    *
    * @param bool result (true: Acepta el pago, false rechaza el pago)
    *
    * @return string paquete firmado para enviar la respuesta del comercio
    '''
    def build_response(result):
        r = "ACEPTADO" if (result) else "RECHAZADO"
        data = array()
        data["status"] = r
        data["c"] = flow_comercio
        q = http_build_query(data)
        s = self.flow_sign(q)
        self.flow_log("Orden N°: "+self.order["OrdenNumero"]+ " - Status: r","flow_build_response")
        return q+ "&s="+s


    '''
    * Método para recuperar los datos  en la página de Exito o Fracaso del Comercio
    *
    '''
    def read_result():
        if(not isset(_POST['response'])):
            self.flow_log("Respuesta Inválida", "read_result")
            raise UserError('Invalid response')

        data = _POST['response']
        params = array()
        parse_str(data, params)
        if (not isset(params['s'])):
            self.flow_log("Mensaje no tiene firma", "read_result")
            raise UserError('Invalid response (no signature)')

        if(not self.flow_sign_validate(params['s'], data)):
            self.flow_log("firma invalida", "read_result")
            raise UserError('Invalid signature from Flow')

        self.order["Comision"] = flow_tasa_default
        self.order["Status"] = ""
        self.order["Error"] = ""
        self.order['OrdenNumero'] = params['kpf_orden']
        self.order['Concepto'] = params['kpf_concepto']
        self.order['Monto'] = params['kpf_monto']
        self.order["FlowNumero"] = params["kpf_flow_order"]
        self.order["Pagador"] = params["kpf_pagador"]
        self.flow_log("Datos recuperados Orden de Compra N°: " .params['kpf_orden'], "read_result")

    def flow_get_public_key_id():
        try :
            return openssl_get_publickey(pub_key)
        except:
            self.flow_log("Error al intentar obtener la llave pública - Error+ " .e.getMessage(), "flow_get_public_key_id")
            raise UserError(e.getMessage())

    def flow_get_private_key_id():
        try :
            fp = fopen("flow_keys/comercio.pem", "r")
            priv_key = fread(fp, 8192)
            fclose(fp)
            return openssl_get_privatekey(priv_key);
        except:
            self.flow_log("Error al intentar obtener la llave privada - Error+ " .e.getMessage(), "flow_get_private_key_id")
            raise UserError(e.getMessage())

    def flow_sign(data):
        priv_key_id = self.flow_get_private_key_id();
        if(not  openssl_sign(data, signature, priv_key_id)):
            self.flow_log("No se pudo firmar", "flow_sign")
            raise UserError('It can not sign')
        return base64_encode(signature)

    def flow_sign_validate(signature, data):
        signature = base64_decode(signature)
        response = explode("&s=", data, 2)
        response = response[0]
        pub_key_id = self.flow_get_public_key_id()
        return (openssl_verify(response, signature, pub_key_id) == 1)

    def _encode_data(self, sorted_items):
        to_sign = '' #'&'.join([method_name, quote(url, safe='')])

        def quote_items(tuples):
            return ['='.join([quote(str(pair[0]), safe=''),
                str(pair[1])]) for pair in tuples]
        to_sign = '&'.join([to_sign,] + quote_items(sorted_items))
        return to_sign[1:]

    def __make_signature(self, method, url, params=None, data=None):
        #method_name = method.upper()
        to_sign = self._encode_data(data)
        hasher = hmac.new(self.secret.encode(), to_sign.encode('UTF-8'), digestmod=sha256)
        signature = hasher.hexdigest()
        if self.is_debug:
            _logger.warning(u"A firmar: {0}".format(to_sign))
            _logger.warning(u"Firma: {0}".format(signature))
        return signature

    def make_request(self, method, endpoint, params=None, data={}):
        url = self.url + endpoint
        data.update(
            {
                'apiKey': self.api_key,
            }
        )
        values = sorted(data.items(), key=lambda item: item[0])
        signature = self.__make_signature(method, url, params, values)
        values.append(('s', signature))
        response = pool.request(method, url, values)

        if self.is_debug:
            _logger.warning(u"Response: {0}".format(response.data))

        return response
