# -*- coding: utf-8 -*-
"""
:copyright: Nokia Networks
:author: Daniel Draus
:contact: daniel.draus@nokia.com
"""


class UePcError(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UePcError, self).__init__(message, *args)


class UeNotFound(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UeNotFound, self).__init__(message, *args)


class UemExtPhoneVerEmpty(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtPhoneVerEmpty, self).__init__(message, *args)


class UemExtSshNotAvaliable(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtSshNotAvaliable, self).__init__(message, *args)


class UemExtIperfNotFound(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtIperfNotFound, self).__init__(message, *args)


class UemExtSshCommandTimeout(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtSshCommandTimeout, self).__init__(message, *args)


class UemExtCmdResponseEmpty(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtCmdResponseEmpty, self).__init__(message, *args)


class UemExtSshConnectionBroken(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtSshConnectionBroken, self).__init__(message, *args)


class UemExtRilServiceException(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtRilServiceException, self).__init__(message, *args)


class UemExtPhoneException(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UemExtPhoneException, self).__init__(message, *args)


class UeThroughputError(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(UeThroughputError, self).__init__(message, *args)


class ParameterError(Exception):
    def __init__(self, message, *args):
        self.message = message
        # delegate the rest of initialization to parent
        super(ParameterError, self).__init__(message, *args)
