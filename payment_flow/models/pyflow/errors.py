# -*- coding: utf-8 -*-
import six
from .items import ErrorItem


@six.python_2_unicode_compatible
class BaseError(Exception):
    def __init__(self, code, message):
        self._code = code
        self._message = message

    @classmethod
    def from_data(cls, data):
        return cls(data.get('code'), data.get('message'))

    @property
    def code(self):
        """
        Código del error
        """
        return self._code

    @property
    def message(self):
        """
        Mensaje del error
        """
        return self._message

    def __str__(self):
        return u'{code} {message}'\
            .format(code = self._code, message = self._message)


class AuthorizationError(BaseError):
    pass


class ServiceError(BaseError):
    pass


class ValidationError(BaseError):
    def __init__(self, code, message, errors=[]):
        self._errors = errors

    @classmethod
    def from_data(cls, data):
        errors = []# [ErrorItem.from_data(i) for i in data.get('errors')]
        return cls(data.get('code'), data.get('message'), errors)

    @property
    def errors(self):
        """
        Arreglo de ErrorItems
        """
        return self._errors
