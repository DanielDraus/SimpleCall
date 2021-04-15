#! /usr/bin/env python
# -*- coding: utf-8
"""main library for new pronto automation
supports python3.1+ and python2.7+
iSource repo: https://svne1.access.nsn.com/isource/svnroot/BTS_T_PRONTO/trunk/pronto
wiki: https://confluence.int.net.nokia.com/pages/viewpage.action?title=Pronto+API+automation+library&spaceKey=ProntoAPI
"""
# pylint: disable=C0302
from __future__ import (absolute_import, division, print_function, unicode_literals)
try:
    str = unicode  # pylint: disable=C0103,W0622,E0602
except NameError:
    pass  # Forward compatibility with Py3k

import copy
import datetime
import json
import logging
import os
import pickle
import random
import re
import socket
import ssl
import time
import xml.etree.ElementTree
from xml.sax.saxutils import quoteattr

import six.moves.urllib as urllib  # pylint: disable=F0401,E0611
from six.moves.html_parser import HTMLParser#, HTMLParseError  # pylint: disable=F0401,E0611

__author__ = "Piotr Jankowski <piotr.jankowski@nsn.com>"


try:
    PR_USER = os.environ['PR_USER']
except KeyError:
    print('WARNING: You need to supply login credentials to PR_USER and PR_PASS')
    PR_USER = 'tambb'

try:
    __PR_PASS__ = os.environ['PR_PASS']
except KeyError:
    print('WARNING: PR_PASS environment variable is not defined!')
    __PR_PASS__ = "Nokia.19"

PR_SERVERS = [
    'https://pronto.int.net.nokia.com/pronto',
    'https://pronto.inside.nsn.com/pronto',
    #'https://bhprot52.apac.nsn-net.net/pronto',
    #'https://qa-pronto.int.net.nokia.com/pronto',
    # 'http://bhprod51.apac.nsn-net.net:8080/ngitpronto',
    # 'http://10.135.144.77:8080/NGITFMToolsWeb',
]

PR_RETRY_LIMIT = 2
PR_PROBE_TIMEOUT = 60
PR_GET_TIMEOUT = 301
PR_CHARSET = 'utf-8'
LINE_BREAK_TAG = '<BR>'
PR_ERROR_STRING = 'OOPS! Looks like this page is not avaiable for you at the moment..<br>'
PR_ERROR_STRING2 = 'You are not authorized to view/edit this problem report OR this document has been moved to archive'
PR_ERROR_STRING3 = 'There are no records for the view id'
PR_REQ_LIMITER_HTTP_CODE = 420
PR_SOCKET_LOCK_PORT = 31410


class HTMLParseError(Exception):
    """
    cant import parser error from six
    """
    pass

class ProntoException(Exception):
    """base pronto exeception class
    most exceptions are only raised if strict mode is enabled by passing strict=True to Pronto class"""
    pass


class ProntoServerException(ProntoException):
    """pronto tool connection exception"""
    pass


class ProntoAuthException(ProntoServerException):
    """raised when login/password is not accepted"""
    pass


class ProntoParseException(ProntoException):
    """exception raised on a prasing error"""
    pass


class ProntoHttpException(ProntoException):
    """base class for http exceptions"""
    pass


class ProntoHttpGetException(ProntoHttpException):
    """exception rasied on http get error and no other servers to try on timeout if strict mode is enabled"""
    pass


class ProntoHttp404(ProntoHttpGetException):
    """exception raised instead of HttpGet if error code is 404"""
    pass


class ProntoHttpPostException(ProntoHttpException):
    """exception rasied on http post error if strict mode is enabled"""
    pass


class CorrectionPolicyException(ProntoException):
    """base class for correction policy exceptions"""
    pass


class CorrectionPolicyParseException(CorrectionPolicyException):
    """exception thrown in case of an error in parsing correction policy data"""
    pass


class CorrectionPolicyDataException(CorrectionPolicyException):
    """exception thrown if policy data to create the correction policy is incomplete"""
    pass


class ProntoServer(object):
    """Class to handle authentication to the pronto server and fallback if preferred server is down"""
    def __init__(self, url_list=PR_SERVERS, skip=0, login=PR_USER, password=__PR_PASS__, verify_cert=False):  # pylint: disable=W0102
        """list shoud be the list of server urls in order of preferrence"""
        self.server = None
        self.retries = 0
        self.auth_failed = False
        self.fake_header = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:47.0) Gecko/20100101 Firefox/47.0'
        logger.info('User: ' + login)
        for url in url_list[skip:]:
            if self.try_server(url, login, password, verify_cert):
                self.server = url
                break
            else:
                logger.warning(url + ' first try failed - making a second attempt...')
                if self.try_server(url, login, password, verify_cert):
                    self.server = url
                    break
                else:
                    logger.warning(url + ' failed to login - assuming it is down...')
        if self.server is not None:
            logger.info('Using server ' + self.server)
        else:
            emsg = 'Failed to connect to any pronto server!'
            logger.error(emsg)
            if self.auth_failed:
                raise ProntoAuthException(self.auth_failed)
            else:
                raise ProntoServerException(emsg)

    def try_server(self, server, login, password, verify_cert):
        """
        server - url to the pronto server
        login - username of the pronto user
        password - password for the given user
        verify_cert - to verify https certtificate
        """
        try:
            # if python supports certificate validation use the bundled certificate
            # to update the certs:
            # 1. open pronto page in a web browser, view the certificate and go to details tab and copy to file
            # 2. choose PKCS#7 p7b format and check include all certificates in the certification path
            # 3. openssl pkcs7 -in certs.p7b -inform DER -print_certs >certs.pem
            if verify_cert:
                certs_file = os.path.join(os.path.dirname(__file__), 'certs.pem')
                context = ssl.create_default_context(cafile=certs_file)  # pylint: disable=E1101
            else:
                context = ssl._create_unverified_context()  # pylint: disable=W0212,E1101
        except AttributeError:
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor)
        else:
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor, urllib.request.HTTPSHandler(context=context))
        logger.debug(opener.handlers)
        # opener.addheaders = [('User-agent', self.fake_header)]
        try:
            resp = opener.open(server + '/', timeout=PR_PROBE_TIMEOUT)
            if not self.handle_auth(opener, server, resp, login, password):
                return False
        except (urllib.error.URLError, socket.timeout) as urlerr:
            logger.warning(urlerr)
            return False
        # install the authentication handler globally to urllib.request
        urllib.request.install_opener(opener)
        return True

    def handle_auth(self, opener, server, resp, login, password):
        """handle the login form submission"""
        lines = resp.readlines()
        resp_server = resp.url.split('/')[2]
        a_lines = []
        for line in lines:
            if '<form id="login-form" action="./login.html" method="post">' in line.decode(PR_CHARSET):
                a_resp = self._pronto_auth(opener, server, login, password)
                if a_resp is None:
                    self.auth_failed = 'HTTP error on authorization'
                    return False
                a_lines = a_resp.readlines()
                # this should handle an authentication failure message with 200 http code
                for a_line in a_lines:
                    decoded_a_line = a_line.decode(PR_CHARSET)
                    if 'User Authorization failed' in decoded_a_line or 'You are not authorized to access Pronto' in decoded_a_line:
                        logger.warning('Auth problem - user/password combination not accepted on ' + server)
                        self.auth_failed = 'Authorization failed'
                        return False
            elif 'Single Sign-On (SSO)' in line.decode(PR_CHARSET):
                a_resp = self._sso_auth(opener, server, login, password, resp_server)
                if a_resp is None:
                    self.auth_failed = 'HTTP error on authorization'
                    return False
                a_lines = a_resp.readlines()
                for a_line in a_lines:
                    decoded_a_line = a_line.decode(PR_CHARSET)
                    if '>Authentication Error</div>' in decoded_a_line:
                        logger.warning('SSO auth problem - user/password combination not accepted on ' + server)
                        self.auth_failed = 'SSO error'
                        return False
        for a_line in a_lines:
            decoded_a_line = a_line.decode(PR_CHARSET)
            if '<h1>Pronto Home Page</h1>' in decoded_a_line:
                return True
        logger.warning('Pronto Home Page not found - assuming auth/server failure')
        return False

    @staticmethod
    def _common_auth(opener, server, url, post_data):
        """return the response object of the page after auth or None on HTTP error"""
        try:
            a_resp = opener.open(url, timeout=PR_PROBE_TIMEOUT, data=post_data.encode())
        except (urllib.error.URLError) as urlerr:
            # this assumes failed auth returns a http error
            urlerr_str = str(urlerr)
            logger.warning(urlerr_str)
            if urlerr_str.startswith('HTTP Error 303: See Other - Redirection to url'):
                logger.warning('Python 3.2.2 has a bug in urllib - please use 3.2.3 or later')
                logger.warning('https://bugs.python.org/issue13696')
            logger.warning('Authorization failed with HTTP error: ' + server)
            return None
        return a_resp

    def _pronto_auth(self, opener, server, login, password):
        """auth on the pronto tool form"""
        post_data = urllib.parse.urlencode({'userId': login, 'password': password, 'Submit': 'Log In'})
        url = server + '/login.html'
        logger.info('Trying to auth to: ' + url)
        a_resp = self._common_auth(opener, server, url, post_data)
        return a_resp

    def _sso_auth(self, opener, server, login, password, sso_server):
        """auth on the single sign on form using user and password fields"""
        logger.info('SSO detected on ' + server)
        post_data = urllib.parse.urlencode({
            'PASSWORD': password,
            'SMENC': 'ISO-8859-1',
            'SMLOCALE': 'US-EN',
            'USER': login,
            'postpreservationdata': '',
            'smauthreason': '0',
            'target': server.replace('https', 'HTTPS') + '/',
            'x': '32',
            'y': '16',
        })
        url = 'https://' + sso_server + '/siteminderagent/forms/login.fcc'
        logger.info('Trying to SSO auth to: ' + url)
        a_resp = self._common_auth(opener, server, url, post_data)
        return a_resp

    def __str__(self):
        return self.server

    def __repr__(self):
        return self.server


class TopParser(HTMLParser):  # pylint: disable=R0903
    """parse the if the ProblemReport is Top"""
    def __init__(self):
        HTMLParser.__init__(self)
        self.result = False
        self.in_page_header = False

    def handle_starttag(self, tag, attrs):
        """find the top icon indicator in title"""
        if tag == 'div' and ('class', 'page_header') in attrs:
            self.in_page_header = True
        if self.in_page_header and tag == 'img' and ('src', '/pronto/images/top.gif') in attrs:
            self.result = True

    def handle_endtag(self, tag):
        """set self.in_page_header to false if div"""
        if tag == 'div':
            self.in_page_header = False


class AttachedParser(HTMLParser):  # pylint: disable=R0903
    """parse the if the ProblemReport is attched"""
    def __init__(self):
        HTMLParser.__init__(self)
        self.result = []

    def handle_starttag(self, tag, attrs):
        """find the top icon indicator in title"""
        if tag == 'a':
            for key, value in attrs:
                if key == 'href' and value.startswith('problemReport.html?prid='):
                    prid = value.partition('=')[2].partition('&')[0]
                    self.result.append(prid)


class InputParser(HTMLParser):  # pylint: disable=R0903
    """parse the edit pages for field values"""
    def __init__(self):
        self._textarea = None
        self._textarea_value = ''
        self._select = None
        self._select_first_option = None
        HTMLParser.__init__(self)
        self.result = {}

    @staticmethod
    def _get_name_value(attrs):
        """get name/id and value from the attributes"""
        name = None
        value = None
        for a_name, a_value in attrs:
            if a_name == 'name':
                name = a_value
            if a_name == 'value':
                value = a_value
            if a_name == 'id':
                if name is None:
                    name = a_value
        if ('type', 'radio') in attrs or ('type', 'checkbox') in attrs:
            if (('checked', 'checked') not in attrs) and (('checked', None) not in attrs):
                logger.debug('radion button or chekcbox not enabled detected')
                logger.debug(attrs)
                value = None
        if name is not None and name.startswith('title_') and ('type', 'hidden') in attrs:
            name = None
        return name, value

    def _handle_input(self, attrs):
        """handle the input tag"""
        current_field_name, current_field_value = self._get_name_value(attrs)
        if current_field_name is not None and current_field_value is not None:
            self.result[current_field_name] = current_field_value
        elif current_field_name is None and current_field_value is not None:
            logger.debug('Unable to find name/id for input value: ' + current_field_value)
        elif current_field_name is not None and current_field_value is None:
            logger.debug('Unable to find value for input name/id: ' + current_field_name)
        else:
            logger.debug('Input tag with no name nor value found')

    def _handle_textarea(self, attrs):
        """handle the textarea tag"""
        current_field_name = self._get_name_value(attrs)[0]
        if current_field_name is None:
            logger.debug('Unable to find name/id for textarea')
        else:
            self._textarea = current_field_name

    def _handle_select(self, attrs):
        """handle the select tag that should contain options"""
        current_field_name = self._get_name_value(attrs)[0]
        if current_field_name is None:
            logger.debug('Unable to find name/id for select')
        else:
            self._select = current_field_name

    def _handle_option(self, attrs):
        """handle the option tag withoin a select"""
        selected_option = False
        if self._select is not None:
            for a_name, a_value in attrs:
                if a_name == 'value':
                    current_field_value = a_value
                if a_name == 'selected':
                    selected_option = True
            if current_field_value is not None:
                if selected_option:
                    self.result[self._select] = current_field_value
                    return
                elif self._select_first_option is None:
                    self._select_first_option = current_field_value

    def handle_starttag(self, tag, attrs):
        """handle tags that send values on form submit"""
        if tag == 'input':
            self._handle_input(attrs)
        if tag == 'textarea':
            self._handle_textarea(attrs)
        if tag == 'select':
            self._handle_select(attrs)
        if tag == 'option':
            self._handle_option(attrs)

    def handle_endtag(self, tag):
        """stop adding data after the end of the textarea tag and add to result"""
        if tag == 'textarea':
            self.result[self._textarea] = self._textarea_value
            self._textarea = None
            self._textarea_value = ''
        if tag == 'select':
            try:
                self.result[self._select]
            except KeyError:
                # if no option is selected default to the first option on the list
                if self._select_first_option is not None:
                    self.result[self._select] = self._select_first_option
            self._select = None
            self._select_first_option = None

    def handle_data(self, data):
        """handle the data between the textarea tags"""
        if self._textarea is not None:
            self._textarea_value += data

    def handle_entityref(self, ref):
        """make sure entities like &amp; are handled correctly"""
        self.handle_data(HTMLParser.unescape(self, '&{};'.format(ref)))

    def handle_charref(self, ref):
        """make sure chars refs like &#039; are handled correctly"""
        self.handle_data(HTMLParser.unescape(self, '&#{};'.format(ref)))


class LinkParser(HTMLParser):
    """parse the links form the page
    href="viewFaultAnalysis.html?fID=PID108929ESPE04&prid=104836ESPE04"""
    def __init__(self, ignore_menus=True):
        HTMLParser.__init__(self)
        self.result = {}
        self.current_link = None
        self.ignore_menus = ignore_menus
        self.ignoring = False

    def handle_starttag(self, tag, attrs):
        """handle the a tag to get the links"""
        if tag == 'a' and not self.ignoring:
            for a_name, a_value in attrs:
                if a_name == 'href' and not a_value.startswith('#'):
                    a_value = a_value.replace(' ', '%20')
                    workaround_str = 'CR137475'
                    if workaround_str in a_value:
                        logger.warning('Ignoring ' + workaround_str)
                        break
                    self.result[a_value] = ''
                    self.current_link = a_value
                    break
        if tag == 'div' and self.ignore_menus:
            if (('class', 'leftMenu') in attrs or
                    ('class', 'footer') in attrs or
                    ('class', 'global_links f-right') in attrs or
                    ('id', 'nav-bottom_menu') in attrs):
                self.ignoring = True
                logger.debug('Ignoring ' + str(attrs))

    def handle_data(self, data):
        """handle the data between the a tags"""
        if self.current_link is not None:
            self.result[self.current_link] += data.replace('\t', '').replace('\n', '').replace('\r', '')

    def handle_endtag(self, tag):
        """stop adding data after the end of the a tag"""
        if tag == 'a':
            self.current_link = None
        if tag == 'div':
            self.ignoring = False


class TableParser(HTMLParser):  # pylint: disable=R0902
    """parse the data from a html table"""
    def __init__(self, split_br=True):
        HTMLParser.__init__(self)
        self.header = []
        self.rows = []
        self.current_header = None
        self.current_data = None
        self.current_row = None
        self.row_index = 0
        self.result = None
        self.split_br = split_br

    def handle_starttag(self, tag, attrs):  # pylint: disable=W0613
        """on tag opening prepare strings for data"""
        if tag == 'th':
            self.current_header = ''
        if tag == 'td':
            self.current_data = ''
        if tag == 'br' and self.current_data is not None:
            self.current_data += LINE_BREAK_TAG
        if tag == 'BR' and self.current_data is not None:
            self.current_data += LINE_BREAK_TAG

    def handle_data(self, data):
        """append the data to the appropriate string"""
        if self.current_data is not None:
            self.current_data += data
        elif self.current_header is not None:
            self.current_header += data

    def handle_entityref(self, ref):
        """make sure entities like &amp; are handled correctly"""
        self.handle_data(HTMLParser.unescape(self, '&{};'.format(ref)))

    def handle_charref(self, ref):
        """make sure chars refs like &#039; are handled correctly"""
        self.handle_data(HTMLParser.unescape(self, '&#{};'.format(ref)))

    def handle_endtag(self, tag):
        """append the tempporary data structures to higher level on tag end"""
        if tag == 'td':
            key = self.header[self.row_index]
            if key != '':
                if LINE_BREAK_TAG in self.current_data:
                    if self.split_br:
                        self.current_data = self.current_data.split(LINE_BREAK_TAG)
                    else:
                        self.current_data = self.current_data.replace(LINE_BREAK_TAG, '<BR>')
                if isinstance(self.current_data, str):
                    self.current_data = self.current_data.strip()
                else:
                    self.current_data = [x.strip() for x in self.current_data]
                self.current_row[key] = self.current_data
            self.row_index += 1
            self.current_data = None
        elif tag == 'tr':
            if self.current_row is not None:
                self.rows.append(self.current_row)
                logger.debug(self.current_row)
            self.current_row = self._new_row()
            self.row_index = 0
        elif tag == 'th':
            current_header = self.current_header.strip()
            if current_header in self.header:
                current_header = current_header + '2' # handle duplicate fields
            self.header.append(current_header)
            logger.debug(current_header)
            self.current_header = None
        elif tag == 'table':
            self.result = (self.header, self.rows)

    @staticmethod
    def _new_row():
        """override to use a custom class in place of the standard dict"""
        return {}


class ViewTableParser(TableParser):
    """create ViewRow in place of the dict in TableParser rows"""
    @staticmethod
    def _new_row():
        return ViewRow()


class Pronto(object):
    """Interface class to the pronto tool
    save_last_html defaults to True to save last http response as last.html file
    set strict to False not to raise exceptions and instead try to continue"""
    def __init__(self, server=None, save_last_html=True, strict=True, verify_cert=False, log_response=False, socket_lock_enabled=True): # pylint: disable=R0913
        self.skip = 0
        if server is None:
            self.server = ProntoServer(verify_cert=verify_cert)
        else:
            self.server = server
        self.save_last_html = save_last_html
        self.strict = strict
        self.log_response = log_response
        self.socket_lock_enabled = socket_lock_enabled
        self.socket_lock = None

    def _create_full_url(self, url, server=None):
        """make sure the url starts with a slash
        server should be None to use the server set in init"""
        if not url.startswith('/'):
            url = '/' + url
        if server is None:
            server = self.server
        url = str(server) + url
        return url

    @staticmethod
    def fix_html(html):
        """ugly workaround for pronto tool bugs that should be removed"""
        html = html.replace('</>', '&lt;/&gt;')
        html = html.replace('<typename Result, typename Source>', '&lt;typename Result, typename Source&gt;')
        html = html.replace('"earfcnDL"', '&quot;earfcnDL&quot;')
        html = html.replace('"<span title =', '<span title=')
        match = re.search('\w+="([^=]*?"[^=]*?)"(?= \/| \w+=")', html) # find unescaped quotes in attribute values
        if match:
            value = match.group(1)
            new_value = value.replace('"', '&quot;')
            html = html.replace(value, new_value)
            logger.error('fixed quote escaping')
            logger.error(value)
            logger.error(new_value)
            logger.error(match.group(0))
            logger.error(match.group(1))
        return html

    def _decode_and_log_resp(self, resp):
        """log the http response from the pronto tool
        used by http_get and http_post
        return the decoded utf-8 string of the response"""
        read_bytes = resp.read()
        if self.save_last_html:
            # store the last request's response in a temp file
            with open('last.html', 'wb') as last:
                last.write(read_bytes)
        response = read_bytes.decode(PR_CHARSET)
        if self.log_response:
            logger.debug(response)
        response = self.fix_html(response)
        return response

    def _handle_http_error(self, urlerr, url, fullurl, referer):
        """urlerr should be the Excetion
        url is be the relative url
        fullurl is the absolute url
        referer is the http referer hearer or None"""
        logger.debug(urlerr)
        try:
            ucode = urlerr.code
        except AttributeError:
            ucode = None
        if ucode == PR_REQ_LIMITER_HTTP_CODE and self.server.retries < PR_RETRY_LIMIT:
            self.server.retries += 1
            random_sleep = random.randint(1, 4) + (self.server.retries * 2)
            logger.warning('Too many requests! Got 420 status code. Will wait ' + str(random_sleep) + ' seconds...')
            time.sleep(random_sleep)
            return self.http_get(url, referer)
        if ((hasattr(urlerr, 'reason') and isinstance(urlerr.reason, socket.error)) or
                (hasattr(urlerr, 'reason') and isinstance(urlerr.reason, socket.timeout)) or
                (isinstance(urlerr, socket.timeout)) or
                (isinstance(urlerr, socket.error)) or
                (urlerr is None)):
            if urlerr is None:
                logger.warning('Error string found...')
            else:
                logger.warning('Socket error or timeout found...')
            if self.server.retries < PR_RETRY_LIMIT:
                self.server.retries += 1
                logger.warning('Retry in 10 seconds...')
                time.sleep(10)
                return self.http_get(url, referer)
        emsg = 'Error opening url: ' + fullurl
        logger.error(emsg)
        if self.strict:
            if ucode == 404:
                raise ProntoHttp404(emsg)  # this a ProntoHttpGetException subclass
            else:
                raise ProntoHttpGetException(emsg)
        return None

    def get_socket_lock(self):
        """bind to a localhost socket to make sure multiple requests are not run from separate scripts"""
        if self.socket_lock_enabled:
            while(1):
                self.socket_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    self.socket_lock.bind(('localhost', PR_SOCKET_LOCK_PORT))
                except socket.error:
                    logger.warning('Unable to bind to port ' + str(PR_SOCKET_LOCK_PORT) + ': This means that pronto tool overload protection got activated. Please make sure only a single view request is run at the same time. You can bypass this check by passing "socket_lock_enabled=False" but this may lead to your account being banned by the pronto tool. Will retry the bind in 1s...')
                    time.sleep(1)
                    continue
                logger.info('Socket lock bind OK')
                return

    def release_socket_lock(self):
        """release the bind for the socket lock if it is set"""
        if self.socket_lock is not None:
            self.socket_lock.close()
            self.socket_lock = None
            logger.info('Socket lock released')

    def http_get(self, url, referer=None, get_timeout=PR_GET_TIMEOUT):
        """get the html from the pronto tool for the given url thorough the http GET request
        url should be without the server part
        ex. the url should NOT contain http://10.135.144.77:8080/NGITFMToolsWeb
        it should only contain the part that comes after that"""
        fullurl = self._create_full_url(url)
        logger.info('Request GET: ' + fullurl)
        try:
            req = urllib.request.Request(fullurl)
            time.sleep(1)
            if referer is not None:
                req.add_header('Referer', referer)
            resp = urllib.request.urlopen(req, timeout=get_timeout)
        except (urllib.error.URLError, socket.timeout, socket.error) as urlerr:
            return self._handle_http_error(urlerr, url, fullurl, referer)
        logger.debug('Request: OK')
        try:
            response = self._decode_and_log_resp(resp)
        except (urllib.error.URLError, socket.timeout, socket.error) as urlerr:
            return self._handle_http_error(urlerr, url, fullurl, referer)
        if PR_ERROR_STRING in response:
            logger.warning('Error string 1 detected - not available at the moment')
            return self._handle_http_error(None, url, fullurl, referer)
        if PR_ERROR_STRING2 in response:
            logger.warning('Error string 2 detected - authorisation')
            return self._handle_http_error(None, url, fullurl, referer)
        if PR_ERROR_STRING3 in response:
            logger.warning('Error string 3 detected - no records')
            return self._handle_http_error(None, url, fullurl, referer)
        return response

    def http_post(self, url, data, referer=None):
        """post the given data to the given url
        url is the relative url (without the server part)
        ex. the url should NOT contain http://10.135.144.77:8080/NGITFMToolsWeb
        data should be a mapping object ex. a dict"""
        fullurl = self._create_full_url(url)
        logger.info('POST Request : ' + fullurl)
        post_data = urllib.parse.urlencode(data)
        # used only for debugging
        splitted_post_data = post_data.split('&')
        for pdt in splitted_post_data:
            logger.debug(pdt)
        req = urllib.request.Request(fullurl, post_data.encode())
        time.sleep(1)
        if referer is not None:
            req.add_header('Referer', referer)
        try:
            resp = urllib.request.urlopen(req)
        except (urllib.error.URLError, socket.timeout) as urlerr:
            logger.debug(urlerr)
            emsg = 'Error opening url: ' + fullurl
            logger.error(emsg)
            if self.strict:
                raise ProntoHttpPostException(emsg)
            return None
        try:
            logger.info('POST request returned ' + str(resp.status))
        except AttributeError:
            # fallback for python2
            logger.info('POST request returned ' + str(resp.code))
        response = self._decode_and_log_resp(resp)
        return response

    def problem_report(self, prid):
        """request problem report and return an instance of ProblemReport class"""
        return ProblemReport(self, prid)

    def group_html(self, groupname):
        """get the group's html page"""
        form_post_data = {
                'sortField': 'GroupName',
                'searchText': groupname,
                'pageStarts': '1',
                'itemPg': '1',
                'viewState': '',
                'viewType': '',
                'sortByDoc': '',
                'sortByCol': '',
                'sortOrder': 'Asc',
        }
        return self.http_post('Maintenance_Groups.html', form_post_data)

    def group_fc(self, groupname):
        """get the groups's fault cooordinator display name to use for ldap translation"""
        html = self.group_html(groupname)
        link = re.search('Maintenance_Group_Details\.html\?groupID=[^"]+', html).group(0)
        html = self.http_get(link)
        fault_coord = re.search('Fault Coordinator\s*</div>\s*<div class="inputBlock">\s*([^<]*)', html).group(1)
        return fault_coord

    def generic_parse(self, html, parser):
        """generic method to execute given parser on given html string
        parser should be an instance of a class that has the results property
        and the interface of HTMLParser"""
        try:
            parser.feed(html)
        except HTMLParseError as err:
            emsg = 'HTML parsing error: ' + str(err)
            logger.error(emsg)
            if self.strict:
                raise ProntoParseException(emsg)
            else:
                return None
        finally:
            try:
                parser.close()
            except HTMLParseError as err:
                emsg = 'HTML parsing error: ' + str(err)
                logger.error(emsg)
                if self.strict:
                    raise ProntoParseException(emsg)
        return parser.result

    def pr_link(self, prid):
        """create a link to the pronblem report"""
        fullurl = self._create_full_url('problemReport.html?prid=' + prid)
        return fullurl

    def new_problem_report(self, title, description, severity='B - Major', repeatability='Permanent', author_group='PT_GROUP'):
        """create a new problem report
        return the ID of the newly created report"""
        form_page = self.http_get('createNewProblemReport.html')
        form_post_data = self.generic_parse(form_page, InputParser())
        form_post_data['title'] = title
        form_post_data['description'] = description
        form_post_data['severity'] = severity
        form_post_data['repeatability'] = repeatability
        form_post_data['groupName'] = author_group
        logger.debug(form_post_data)
        response = self.http_post('saveNewProblemReport.html', form_post_data)
        response_data = self.generic_parse(response, InputParser())
        return response_data['prID']

    def new_build(self, build, release='', product='',  # pylint: disable=R0913
                  deadline='', platform_rel='', platform_build='', expires_in_pronto=''):
        """create a new build in Maintenance mode
        note that this requires power user account rights
        ensure your account can see the Maintenance link before using"""
        form_page = self.http_get('createNewBuild.html')
        form_post_data = self.generic_parse(form_page, InputParser())
        form_post_data['build'] = build
        form_post_data['relName'] = release
        form_post_data['buildProd'] = product
        form_post_data['deadLine'] = deadline
        form_post_data['platformRelease'] = platform_rel
        form_post_data['platformBuild'] = platform_build
        form_post_data['expireDate'] = expires_in_pronto
        logger.debug(form_post_data)
        return self.http_post('saveNewBuild.html', form_post_data)

    def build_exists(self, build):
        """check if a build exists in Maintenance mode
        note that this requires power user account rights
        ensure your account can see the Maintenance link before using"""
        result = True
        form_page = self.http_get('Maintenance_SW_Builds.html')
        form_post_data = self.generic_parse(form_page, InputParser())
        form_post_data['searchText'] = build
        logger.debug(form_post_data)
        resp = self.http_post('Maintenance_SW_Builds.html', form_post_data)
        if '<div class="tablePaging">Found 0</div>' in resp:
            result = False
        return result


class DictXml(dict):
    """dict with xml export support"""
    _root_tag = None
    _root_attribute = None

    def xml(self, dst_attr=None):
        """get the xml Element of the page"""
        if dst_attr is None:
            dst_attr = self._root_attribute
        src_attr = self._root_attribute
        root = xml.etree.ElementTree.Element(self._root_tag, {dst_attr: str(self[src_attr])})
        for name, value in self.items():
            xml.etree.ElementTree.SubElement(root, 'field', {'name': str(name), 'value': str(value)})
        return root


class ViewRow(DictXml):
    """class to parse the views"""
    _root_tag = 'row'
    _root_attribute = 'Problem ID'

    def xml(self, dst_attr='problem_id'):
        """provide default the dst_attr as spaces can't be used in attributes"""
        return DictXml.xml(self, dst_attr)

    def oldformat(self, header):
        """header is required to maintain the order of the fields with the header fields"""
        # this is to avoid single quotes if double quotes are in the string
        escape_quote_entity = {'"': '&quot;'}
        result = 'addrowArray(new Array('
        for fieldname in header:
            if fieldname != '':
                try:
                    result += quoteattr(self[fieldname], escape_quote_entity) + ','
                except AttributeError:
                    # to suppot split_br - list doeas not have replace so AttributeError in quoteattr
                    result += quoteattr('<BR>'.join(self[fieldname]), escape_quote_entity) + ','
        result = result.strip(',')
        result += '));\r\n'
        return result


class View(list):
    """class to handle the pronto view"""
    def __init__(self, pronto=None, view_id=None, state='OPEN', split_br=False, view_get_timeout=PR_GET_TIMEOUT):
        """state should be: OPEN, CLOSED or ALL"""
        list.__init__(self)
        if view_id is not None and pronto is not None:
            self.view_id = view_id
            params = {
                'viewsOrStatisticsId': view_id,
                'viewState': state,
            }
            pronto.get_socket_lock()
            html = pronto.http_get('fetchAPIReports.html?' + urllib.parse.urlencode(params), get_timeout=view_get_timeout)
            pronto.release_socket_lock()
            header, rowlist = pronto.generic_parse(html, ViewTableParser(split_br=split_br))
            self.extend(rowlist)
            self.header = header

    def xml(self):
        """export view to xml"""
        root = xml.etree.ElementTree.Element('view', {'id': self.view_id})
        for row in self:
            root.append(row.xml())
        return xml.etree.ElementTree.tostring(root).decode(PR_CHARSET)

    def oldformat(self):
        """export the view to the format of the old pronto view"""
        result = 'setMaxResult(5000);\r\nsetLabelsArray(new Array('
        for fieldname in self.header:
            if fieldname != '':
                result += quoteattr(fieldname) + ','
        result = result.strip(',')
        result += '));\r\n'
        for row in self:
            result += row.oldformat(self.header)
        return result

    def save(self, filename='view.pickle'):
        """save a view object to a pickle file"""
        with open(filename, 'wb') as file:
            pickle.dump(self, file)
        return

    def load(self, filename='view.pickle'):
        """load a view object by unpickling a pickle file"""
        with open(filename, 'rb') as file:
            loaded_view = pickle.load(file)
        self.extend(loaded_view)
        return

    def __sub__(self, other):
        """substract a view from this view"""
        result = copy.copy(self)
        for row in other:
            if row in result:
                result.remove(row)
        return result

    def __add__(self, other):
        """join two views"""
        result = copy.copy(self)
        for row in other:
            if row not in result:
                result.append(row)
        return result

    def filter(self, field, value, field2=None, value2=None):
        """filter view results
        field should be the dict key - the filed name from the view header
        value can be a regex object or a string or a list of strings
        """
        filtered = View()
        for record in self:
            # record[field] can be a list or a string
            if field2 is not None:
                record_f2 = record[field2]
            else:
                record_f2 = None
            if self._match_values(record[field], value, record_f2, value2):
                filtered.append(record)
        return filtered

    def _match_values(self, record_value, value, record_value2=None, value2=None, prior_index=None):
        """test for a match between the value of the record
        and the value that may be a srting a list of values or a regexp object
        the value of the record may be a string or a list of strings"""
        record_value_list = self._get_record_value_list(record_value)
        regexp = self._check_regexp(value)
        index = 0
        for record_single in record_value_list:
            index += 1
            if prior_index is not None and prior_index != index:
                continue
            if regexp:
                # value is a regexp object
                match = value.search(record_single)
                if match:
                    if self._match_second_values(record_value2, value2, index):
                        return True
            elif isinstance(value, str):
                # value is a string
                if record_single == value:
                    if self._match_second_values(record_value2, value2, index):
                        return True
            else:
                # value is a list of strings
                if record_single in value:
                    if self._match_second_values(record_value2, value2, index):
                        return True
        return False

    def _match_second_values(self, record_value2, value2, index):
        """match 2nd value that should be in the same row index"""
        if record_value2 is None or value2 is None:
            return True
        else:
            # value becomes value2 but with prior_index specified
            return self._match_values(record_value2, value2, prior_index=index)

    @staticmethod
    def _get_record_value_list(record_value):
        """make sure record value is a list"""
        # check if record value is a sigle value or multiple
        if isinstance(record_value, str):
            # if it is a string create a list containing just this string
            record_value_list = [record_value]
        else:
            record_value_list = record_value
        return record_value_list

    @staticmethod
    def _check_regexp(value):
        """check is value is a regexp"""
        try:
            value.pattern
        except AttributeError:
            logger.debug('Value \'{}\' is a string'.format(value))
            return False
        else:
            logger.debug('Value \'{}\' is a regular expression'.format(value.pattern))
            return True

    def ids(self):
        """return the ids of problem reports in the view"""
        result = []
        for row in self:
            result.append(row['Problem ID'])
        return result

    def set_appeared(self, old_data=None):
        """set the time the row appeared in the view or copy it from old_data with same Problem ID"""
        now = datetime.datetime.now()
        for row in self:
            appeared_date = now
            for old_row in old_data:
                if row['Problem ID'] == old_row['Problem ID']:
                    if 'appeared' in old_row:
                        appeared_date = old_row['appeared']
                        break
            row['appeared'] = appeared_date


class GenericPage(DictXml):
    """base class to handle the Correction Form, Fault Analysis and Problem Report pages"""
    _view_page = None
    _edit_page = None
    _update_link = None

    def __init__(self, pronto, link):
        """link is the link to the subpage (ex. correction from) from the pronto page"""
        DictXml.__init__(self)
        self.pronto = pronto
        self.referer = link
        self.edit_link = self._get_edit_link(link)
        self._html = self._get_page()
        self.history_url = None
        self.update(self._parse_fields())  # the update method of dict

    def _get_edit_link(self, link):
        """change the detail link to edit link"""
        link = link.replace(self._view_page, self._edit_page)
        link = link.partition('&prState=')[0]
        return link

    def _get_page(self):
        """get the edit link via http get request"""
        return self.pronto.http_get(self.edit_link, self.referer).replace('class=>', '>')

    def _parse_fields(self):
        """return the python dict of the input fields"""
        return self.pronto.generic_parse(self._html, InputParser())

    def _parse_links(self):
        """get the links form the page"""
        return self.pronto.generic_parse(self._html, LinkParser())

    def post(self):
        """send the contents of the dict through the post request"""
        return self.pronto.http_post(self._update_link, self, referer=self.edit_link)

    def get_history(self):
        """get revision history data"""
        result = self.pronto.http_get(self.history_url)
        return json.loads(result)


class ProblemReport(GenericPage):  # pylint: disable=R0904
    """class to handle the ProblemReport
    self.links stores a dict where href attribute is the key and link text is the value"""
    _root_tag = 'problem_report'
    _root_attribute = 'problemReportId'
    _update_link = 'updateProblemReport.html'

    def __init__(self, pronto, prid):
        """prid is the id of the problem report, pronto is an instance of the Pronto class"""
        GenericPage.__init__(self, pronto, prid)
        self.links = self._parse_links()
        self._cfs = None
        self._fault = None
        self._generics = None
        self._info = None
        self.prid = self['problemReportId']
        self.history_url = 'problemReportRevisionHistory.html?id=' + self.prid

    def _get_edit_link(self, prid):
        """get the pronto edit page html
        self.prid should be the str of Problem ID ex. 104836ESPE04"""
        return '/editProblemReport.html?prID=' + urllib.parse.quote_plus(prid)

    def get_top(self):
        """return true if the Problem Report is top"""
        return self.pronto.generic_parse(self._html, TopParser())

    def get_attached(self):
        """get the list of Problem Reports attached to this one"""
        return self.pronto.generic_parse(self._html, AttachedParser())

    def xml(self, dst_attr='id'):
        """get the xml of the problem report page"""
        root = GenericPage.xml(self, dst_attr)
        fault = self.get_fault_analysis()
        root.append(fault.xml())
        cfs = self.get_corrections()
        for correction in cfs.values():
            root.append(correction.xml())
        generics = self.get_generic_faults()
        for generic in generics.values():
            root.append(generic.xml())
        infos = self.get_information_requests()
        for info in infos.values():
            root.append(info.xml())
        return xml.etree.ElementTree.tostring(root).decode(PR_CHARSET)

    def get_corrections(self, reload=False):
        """get the corrections from problem report
        uses values from the links dict as keys in the result dict
        result is ex. 'LN4.0 2.0 LN4.0_ENB_1202_840_00@130527': {dict containing all correction fields} """
        if (self._cfs is None) or reload:
            self._cfs = {value: Correction(self.pronto, key) for (key, value) in self.links.items() if key.startswith('./detailCorrection.html')}
        return self._cfs

    def get_corrections_list(self):
        """get a list of correction objects
        this is usefull wehn key of the dict may be the same for ex. duplicated build"""
        return [Correction(self.pronto, key) for (key, value) in self.links.items() if key.startswith('./detailCorrection.html')]

    def get_fault_analysis(self, reload=False):
        """get the fault analysis"""
        if (self._fault is None) or reload:
            for key in self.links:
                if key.startswith('viewFaultAnalysis.html'):
                    self._fault = FaultAnalysis(self.pronto, key)
                    break
        return self._fault

    def get_generic_faults(self, reload=False):
        """return a dict of generic faults"""
        if (self._generics is None) or reload:
            self._generics = {value: GenericFault(self.pronto, key) for (key, value) in self.links.items() if key.startswith('viewGenericFault.html')}
        return self._generics

    # to be deleted
    def get_information_requests(self, reload=False):
        """return a information request object"""
        if (self._info is None) or reload:
            self._info = {value: InformationRequest(self.pronto, key) for (key, value) in self.links.items() if key.startswith('./detailInformationRequest.html')}
        return self._info

    def get_information_requests_list(self):
        """get a list of information requests
        this is useful when key of the dict may be the same for ex. same date"""
        return [InformationRequest(self.pronto, key) for (key, value) in self.links.items() if key.startswith('./detailInformationRequest.html')]

    def new_information_requests(self, post_data):
        """
        create new information request object
        :param post_data:data dictionary may contain key-value pair like: 'question', 'sendTo' and 'responseTo'
        :return:
        """
        form_page = self.pronto.http_get('newInformationRequest.html?prid={}&prAuthor={}&faultId={}'.format(self['problemReportId'], self['author'], self['faultId']))
        form_post_data = self.pronto.generic_parse(form_page, InputParser())
        del form_post_data['fileAttachment']
        for key in post_data:
            form_post_data[key] = post_data[key]
        self.pronto.http_post('saveInformationRequest.html', form_post_data)
        return self._info

    def detail_information_request(self, irid):
        """
        gets single information request object
        :param irid: information request object ID
        :return:
        """
        irs = self.get_information_requests_list()
        _information_request = [info for info in irs if info['irId'] == irid]
        return _information_request[0]

    # to be deleted
    def edit_information_requests(self, irid, post_data):
        """edits a information request object"""
        all_ir_data = self.get_information_requests()
        ir_data = {}
        for information_request in all_ir_data:
            if all_ir_data[information_request]['irId'] == irid:
                for ir_key in all_ir_data[information_request]:
                    if re.match('(.uestion|answer|.*userUniqueName)', str(ir_key)):
                        ir_data[ir_key] = all_ir_data[information_request][ir_key]
        for ir_key in post_data:
            ir_data[ir_key] = post_data[ir_key]
        ir_url = 'saveEditInformationRequest.html?irId={irId}'.format(irId=irid)
        self.pronto.http_post(ir_url, ir_data)
        return

    def edit_information_request(self, irid, post_data):
        """
        edits a information request object
        :param irid:
        :param post_data: dictionary with keys: 'question', 'answer', 'responseTo', 'sendTo'
        :return:
        """
        information_request = self.detail_information_request(irid)
        ir_data = {}
        for ir_key in information_request:
            if re.match('(.uestion|answer|.*userUniqueName)', str(ir_key)):
                ir_data[ir_key] = information_request[ir_key]
        for ir_key in post_data:
            ir_data[ir_key] = post_data[ir_key]
        ir_url = 'saveEditInformationRequest.html?irId={irId}'.format(irId=irid)
        self.pronto.http_post(ir_url, ir_data)
        return self._info

    def send_information_request(self, irid, post_data={}):
        """
        sends a information request object
        :param irid: information request object ID
        :param post_data: optional - dictionary with keys: 'question', 'responseTo'
        :return:
        """
        info = self.detail_information_request(irid)
        post_data['responseTo'] = info['responseTo']
        post_data['question'] = info['question']
        post_data['irId'] = irid
        post_data['selectedPRID'] = self['problemReportId']
        post_data['author'] = self['author']
        post_data['faultId'] = self['faultId']
        url = 'sendMailInformationRequest.html?irId={irId}'.format(irId=irid)
        self.pronto.http_post(url, post_data)
        return self._info

    def reply_information_request(self, irid, post_data={}):
        """
        reply action of information request object
        :param irid: information request object ID
        :param post_data: optional - dictionary with keys: 'answer'
        :return:
        """
        info = self.detail_information_request(irid)
        post_data['prID'] = self['problemReportId']
        post_data['faultId'] = self['faultId']
        post_data['irId'] = irid
        if 'answer' is not post_data:
            post_data['answer'] = info['answer']
        url = 'replyIR.html'
        self.pronto.http_post(url, post_data)
        return self._info

    def update_build(self, old_build, new_build, reload=False, release=False):
        """update the build field in the appropriate correction"""
        cfs = self.get_corrections(reload=reload)
        for correction in cfs.values():
            if correction['targetBuild'] == old_build:
                if release and release == correction['targetRelease']:
                    correction.set_build(new_build)
                elif not release:
                    correction.set_build(new_build)
                return True
            else:
                logger.info(correction['targetBuild'] + '!=' + old_build)
        return False

    def new_correction(self, release='LN0.0', build='LN0.0_ENB_0000_000_00'):
        """create a new correction object"""
        post_data = {
            'targetRelease': release,
            'targetBuild': build,
            'responsiblePerson': '',
            'correctionReason': '',
            'faultId': self['faultId'],
            'prid': self['id'],
            'target': 'New',
            'requestFrom': 'probRpt',
        }
        form_page = self.pronto.http_post('newCorrection.html', post_data)
        form_post_data = self.pronto.generic_parse(form_page, InputParser())
        self.pronto.http_post('saveCorrection.html', form_post_data)
        return

    def _parse_correction_policy_js(self, param_name, correction_policy_html_lines):
        """parse a parameter form correction policy popup javascript"""
        result = None
        pattern_str = '$("#' + param_name + '", parent.document).val(\''
        for line in correction_policy_html_lines:
            if pattern_str in line:
                result = line.replace(pattern_str, '').replace('\');', '').strip()
                logger.info('Correction policy: found ' + param_name + ': ' + result)
                break
        if result is None:
            emsg = 'Unable to parse correction policy page for ' + param_name + ' in ' + self.prid
            logger.error(emsg)
            raise CorrectionPolicyParseException(emsg)
        return result

    def get_correction_policy(self):
        """get the correction policy form data from the popup"""
        result = {}
        correction_policy_popup = 'pop_correction_policy.html?prid=' + self.prid
        correction_policy_html = self.pronto.http_get(correction_policy_popup)
        form_data = self.pronto.generic_parse(correction_policy_html, InputParser())
        correction_policy_html_lines = correction_policy_html.splitlines()
        app_rel = self._parse_correction_policy_js('appRelName', correction_policy_html_lines)
        platform_rel = self._parse_correction_policy_js('platformRelName', correction_policy_html_lines)
        try:
            result['releaseOption'] = form_data['rdRel']
        except KeyError:
            emsg = 'Unable to get correction policy for ' + self.prid + ' as rdRel was not found in form data'
            logger.error(emsg)
            raise CorrectionPolicyParseException(emsg)
        result['appRelName'] = app_rel
        result['platformRelName'] = platform_rel
        return result

    def create_correction_policy(self, responsible_person='', policy_data=None):
        """policy data can be a modified dict result from get_correction_policy
        if you need to do anything with the new correction forms call get_corrections(reload=True)"""
        if policy_data is None:
            logger.info('Correction policy data not supplied - using default')
            policy_data = self.get_correction_policy()
        for key in ['appRelName', 'releaseOption', 'platformRelName']:
            if key not in policy_data:
                emsg = 'Unable to create correction policy for ' + self.prid + ': policy data does not contain ' + key
                logger.error(emsg)
                raise CorrectionPolicyDataException(emsg)
        logger.info('Correction policy will be created:' + str(policy_data))
        post_data = {
            'prID': self['problemReportId'],
            'faultID': self['faultId'],
            'responsiblePerson': responsible_person,
        }
        post_data.update(policy_data)
        response = self.pronto.http_post('createCorrectionPolicy.html', post_data)
        logger.info('Correction policy created for ' + self.prid)
        return response

    def transfer(self, group, reason='autotransfer'):
        """transfer the problem report to a new group in charge"""
        post_data = {
            'prID': self['problemReportId'],
            'faultID': self['faultId'],
            'transferReason': reason,
            'transferGName': group,
            'currentGName': self['groupIncharge'],
            'removeResPerson': '',
        }
        response = self.pronto.http_post('pop_pr_transfer.html', post_data)
        logger.info('Problem report {id} transferred to {to} from {fr}'.format(id=self['problemReportId'], to=group, fr=self['groupIncharge']))
        return response

    def pr_link(self):
        """call pr_link from the pronto class"""
        return self.pronto.pr_link(self.prid)


class Correction(GenericPage):
    """class to handle the Correction Form"""
    _view_page = './detailCorrection.html'
    _edit_page = 'editCorrectionAdmin.html'
    _root_tag = 'correction'
    _root_attribute = 'targetBuild'
    _update_link = 'updateCorrection.html'

    def __init__(self, pronto, link):
        """setup convenience properties for Correction"""
        GenericPage.__init__(self, pronto, link)
        self.build = self['targetBuild']
        self.state = self['status']
        self.rel = self['targetRelease']
        self.history_url = 'correctionRevisionHistory.html?correctionId=' + self['correctionId']

    def set_build(self, newbuild):
        """update the target build field"""
        self['targetBuild'] = newbuild
        return self.post()

    def decline(self, reason='auto', responsible='Internal, Userthree (NSN - IN/Noida)'):
        """set correction to needless"""
        post_data = {
            'responsiblePerson': responsible,
            'correctionReason': reason,
            'correctionId': self['correctionId'],
            'faultId': self['faultId'],
            'prid': self['prid'],
        }
        self.pronto.http_post('declineCorrectionSave.html', post_data, referer=self.referer)

    def delete(self, really=False):
        """delete the CF - WARNING - this is a permament operation"""
        params = {
            'correctionId': self['correctionId'],
            'faultId': self['faultId'],
            'prid': self['prid'],
            'title': self['targetRelease'] + ' ' + self['targetBuild']
        }
        url = 'deleteCorrection.html?' + urllib.parse.urlencode(params)
        logger.info(url)
        if really:
            self.pronto.http_get(url, referer=self.referer)

    def reopen(self):
        """reopen the correction so switch from needless to correcting"""
        params = {
            'correctionId': self['correctionId'],
            'faultId': self['faultId'],
            'prid': self['prid'],
        }
        self.pronto.http_get('reOpenCorrection.html?' + urllib.parse.urlencode(params), referer=self.referer)

    def complete_tnn(self, reason='auto'):
        """complete the correction as testing not needed"""
        params = {
            'prid': self['prid'],
            'faultId': self['faultId'],
            'status': 'Testing Not Needed',
            'correctionId': self['correctionId'],
            'reason': reason,
        }
        post_data = {
            'testGroup': '',
            'testGroupVal': '',
            'prID': self['prid'],
            'faultId': self['faultId'],
            'status': self['status'],
            'correctionId': self['correctionId'],
            'testGroupUp': '',
            'popTarget': '',
            'lastTestComponentType': '',
            'buttonName': '',
            'correctionOldStatus': '',
        }
        self.pronto.http_post('completeCorrectionSave.html?' + urllib.parse.urlencode(params), post_data, referer=self.referer)

    def undefined(self):
        """return bool if CF is undefined ex. containing xxx_yy in the target build"""
        result = False
        build = self['targetBuild']
        if ('y' in build or 'x' in build or 'X' in build or 'Y' in build) and 'CNA' not in build:
            result = True
        return result


class FaultAnalysis(GenericPage):
    """class to handle the Correction Form"""
    _view_page = 'viewFaultAnalysis.html'
    _edit_page = 'editFaultAnalysis.html'
    _root_tag = 'fault_analysis'
    _root_attribute = 'id'
    _update_link = 'updateFaultAnalysis.html'

    def __init__(self, pronto, link):
        GenericPage.__init__(self, pronto, link)
        self.history_url = 'faultAnalysisRevisionHistory.html?id=' + self['id']


class InformationRequest(GenericPage):  # pylint: disable=R0921
    """class to handle the Information Request"""
    _view_page = './detailInformationRequest.html'
    _edit_page = 'detailInformationRequest.html'
    _root_tag = 'information_request'
    _root_attribute = 'irId'
    _update_link = 'saveEditInformationRequest.html'

    def __init__(self, pronto, link):
        """link is the link to the subpage (ex. correction from) from the pronto page"""
        DictXml.__init__(self)
        self.pronto = pronto
        self.referer = link
        self.edit_link = self._get_edit_link(link)
        if re.search(r'IR\d+', self.edit_link):
            self.ir_id = re.search(r'IR\d+', self.edit_link).group()
        else:
            self.ir_id = None

        if re.search(r'(\d{4,}ESPE\d{2,}|NA\d{7,}|PR\d+|CAS-\d{5,}-.{1,7}|PA-\d+)', self.edit_link):
            self.pr_id = re.search(r'(\d{4,}ESPE\d{2,}|NA\d{7,}|PR\d+|CAS-\d{5,}-.{1,7}|PA-\d+)', self.edit_link).group()
        else:
            self.pr_id = None

        self.edit_link = self.edit_link.partition('?')[0]
        self._html = self._get_page()
        self.history_url = None
        self.update(self._parse_fields())  # the update method of dict

    def post(self):
        """this causes problem with disappearing from the problem report page"""
        raise NotImplementedError()

    def _get_page(self):
        """get the edit link via http get request"""
        return self.pronto.http_get(url=self.edit_link, data={'selectedPRID': self.pr_id, 'irId': self.ir_id}, referer=self.referer).replace('class=>', '>')


class GenericFault(GenericPage):
    """class the handle the Generic Fault object"""
    _view_page = 'viewGenericFault.html'
    _edit_page = 'editGenericFault.html'
    _root_tag = 'generic_fault'
    _root_attribute = 'genericFaultID'
    _update_link = 'updateGenericFault.html'

    def __init__(self, pronto, link):
        GenericPage.__init__(self, pronto, link)
        self.history_url = 'genericFaultRevisionHistory.html?id=' + self['genericFaultID']

logger = logging.getLogger('pronto_logger')  # pylint: disable=C0103


if __name__ == "__main__":
    p = Pronto()  # login and save auth cookie

    pr = p.problem_report('123456ESPE99')
    print(pr['rdPriority'])  # pr object works as a dict
    pr['description'] += ' spam bacon sausage and spam'
    pr.post()  # save the updated description

    pr.update_build('LN9.9_ENB_1234_xxx_yy', 'LN9.9_ENB_1234_012_00')  # update the build in the correction form
