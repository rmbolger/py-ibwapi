"""Contains the Client class for interacting with the Infoblox NIOS WAPI."""

import logging
import requests
import urllib3

from .exceptions import WAPIError, LimitExceededError

logger = logging.getLogger(__name__)


class Client:
    """
    A client for interacting with the Infoblox NIOS WAPI. This client
    manages requests to the WAPI endpoint, including authentication, and TLS
    verification.

    Attributes:
        base_url (str): The base URL for the WAPI endpoint, constructed from the host and version.
        session (requests.Session): The session object used for making HTTP requests, which
                                    stores authentication and TLS settings.
        log_api_calls (bool): When True, logs API call details at the INFO level.

    Args:
        wapi_host (str): The hostname or IP address of the Infoblox WAPI server.
        auth (tuple): A tuple containing the username and password for authentication.
        wapi_version (str): The version of the Infoblox WAPI to use (default: '2.12').
        tls_verify (bool): Whether to verify the TLS/SSL certificate (default: True).
        log_api_calls (bool): When True, logs API call details at the INFO level (default: False).
        timeout (float or tuple): (optional) How many seconds to wait for the server to send
            data before giving up, as a float, or a (connect timeout, read timeout) tuple.
            Applied to all calls unless overridden per call.
    """

    def __init__(
        self,
        wapi_host: str,
        auth,
        wapi_version: str = '2.12',  # NIOS 8.6.0 EOL 2024-04-30
        tls_verify: bool = True,
        log_api_calls: bool = False,
        timeout=None,
    ):
        """
        Initializes the Infoblox WAPI client, setting up the session and base URL.

        Args:
            wapi_host (str): The hostname or IP address of the Infoblox WAPI server.
            auth (tuple): A tuple of (username, password) for HTTP basic authentication.
            wapi_version (str): The WAPI version to use (default: '2.12').
            tls_verify (bool): If False, TLS/SSL verification is disabled (default: True).
            log_api_calls (bool): When True, logs each API request at INFO level (default: False).
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Applied to all calls unless overridden per call.
        """
        wapi_version = wapi_version.lstrip('v')  # Normalize version string
        self._wapi_host = wapi_host
        self._wapi_version = wapi_version
        self.base_url = f'https://{wapi_host}/wapi/v{wapi_version}/'

        self.session = requests.Session()
        self.session.auth = auth
        self.session.verify = tls_verify
        if not tls_verify:
            urllib3.disable_warnings()

        self.log_api_calls = log_api_calls
        self.timeout = timeout

    @property
    def tls_verify(self) -> bool:
        """
        Returns whether TLS/SSL certificate verification is enabled.

        Returns:
            bool: True if TLS verification is enabled, False otherwise.
        """
        return self.session.verify

    @tls_verify.setter
    def tls_verify(self, value: bool):
        """
        Sets the TLS/SSL verification behavior for the session.

        Args:
            value (bool): If False, TLS verification is disabled and warnings are suppressed.
        """
        self.session.verify = value
        if not value:
            urllib3.disable_warnings()

    def get(
        self,
        obj: str,
        data: dict = None,
        return_fields: list = None,
        paging: bool = True,
        page_size: int = 1000,
        max_results: int = None,
        timeout=None,
    ):
        """
        Retrieves (reads) a WAPI object by its type or reference.

        Args:
            obj (str): The type or reference of the object to retrieve (e.g., "record:host").
            data (dict): Field filters and additional query parameters.
            return_fields (list): Fields to return in the response. 'default' includes base fields.
            paging (bool): Whether to use paging.
            page_size (int): Number of records to return per page.
            max_results (int): Maximum results to return. Negative values raise an error if
                               results exceed the absolute value.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            list: The list of JSON objects representing the requested data.

        Raises:
            ValueError: If paging or max_results parameters are invalid.
            LimitExceededError: If a negative max_results is specified and the result set exceeds
                                that limit.
            WAPIError: If a request error is returned by the WAPI.
        """
        # sanity check numeric params
        if paging and page_size <= 0:
            raise ValueError(
                'page_size must be a positive integer when paging is enabled'
            )
        if max_results == 0:
            raise ValueError('max_results cannot be zero')

        url = f'{self.base_url}{obj}'

        # start building query params
        query_params = data or dict()

        # add return fields
        query_params.update(self._build_return_fields(return_fields))

        # add paging
        if paging:
            query_params['_paging'] = 1
            query_params['_return_as_object'] = 1

            # If max_results is specified, reduce page_size if necessary to avoid
            # querying more data than we need
            if max_results is not None:
                if max_results > 0 and max_results < page_size:
                    page_size = max_results
                elif max_results < 0 and abs(max_results) <= page_size:
                    page_size = abs(max_results) + 1
            query_params['_max_results'] = page_size

            # make the first call
            results = []
            rdata = self._call_wapi(url, query_params, timeout=timeout)
            results.extend(rdata.get('result'))

            # loop the rest of the pages
            while 'next_page_id' in rdata and (
                max_results is None or len(results) < abs(max_results)
            ):
                query_params = {'_page_id': rdata['next_page_id']}
                rdata = self._call_wapi(url, query_params, timeout=timeout)
                results.extend(rdata.get('result'))

            # Trim or error as necessary if the result set is larger than max_results
            if max_results is not None:
                if max_results < 0 and len(results) > abs(max_results):
                    raise LimitExceededError(abs(max_results), len(results))
                elif max_results > 0 and len(results) > max_results:
                    results = results[:max_results]
        else:
            if max_results is not None:
                # with no paging, we can use max_results as-is if specified
                query_params['_max_results'] = max_results

            results = self._call_wapi(url, query_params, timeout=timeout)

        return results

    def new(self, obj: str, data: dict, return_fields: list = None, timeout=None):
        """
        Creates a new WAPI object.

        Args:
            obj (str): The type of object to create (e.g., "record:host").
            data (dict): A dictionary of fields/values to include in the new object.
            return_fields (list): Fields to return on the new object. 'default' includes base
                                  fields.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The created object data.

        Raises:
            WAPIError: If a request error occurs.
        """
        url = f'{self.base_url}{obj}'

        query_params = self._build_return_fields(return_fields)

        rdata = self._call_wapi(url, query_params, data, method='POST', timeout=timeout)
        return rdata

    def update(self, ref: str, data: dict, return_fields: list = None, timeout=None):
        """
        Updates an existing WAPI object by its reference.

        Args:
            ref (str): The '_ref' ID of the object to update.
            data (dict): Fields/values to update.
            return_fields (list): Fields to return on the updated object. 'default' includes base
                                  fields.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The updated object data.

        Raises:
            WAPIError: If a request error occurs.
        """
        url = f'{self.base_url}{ref}'

        query_params = self._build_return_fields(return_fields)

        rdata = self._call_wapi(url, query_params, data, method='PUT', timeout=timeout)
        return rdata

    def delete(self, ref: str, delete_args: dict = None, timeout=None):
        """
        Deletes an existing WAPI object by its reference ID.

        Args:
            ref (str): The reference ID of the object to delete.
            delete_args (dict): Additional arguments related to this delete request.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The deletion response data.

        Raises:
            WAPIError: If a request error occurs.
        """
        url = f'{self.base_url}{ref}'

        rdata = self._call_wapi(url, delete_args, method='DELETE', timeout=timeout)
        return rdata

    def request(self, payload, timeout=None):
        """
        Send a generic WAPI handler request using the 'request' object. This allows for multiple
        operations in a single call. See the WAPI docs for details.

        Args:
            payload: A dict or list of dicts containing request objects.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The response data from the request.

        Raises:
            WAPIError: If a request error occurs.
        """
        url = f'{self.base_url}request'
        rdata = self._call_wapi(url, body_data=payload, method='POST', timeout=timeout)
        return rdata

    def _call_wapi(
        self,
        url: str,
        query_params: dict = None,
        body_data: dict = None,
        method: str = 'GET',
        timeout=None,
    ):
        """
        Performs a raw HTTP request with the current session.

        Args:
            url (str): The URL endpoint to send the request to.
            query_params (dict): Query parameters for the request.
            body_data (dict): JSON body data for non-GET requests.
            method (str): HTTP method for the request (default: "GET").
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The JSON response data.
        """
        if query_params is None:
            query_params = {}
        if body_data is None:
            body_data = {}
        if self.log_api_calls:
            logger.info('%s %s - %s - %s', method, url, query_params, body_data)

        request_args = {'params': query_params} if query_params else {}

        if method != 'GET' and body_data:
            request_args['json'] = body_data

        request_timeout = self.timeout if timeout is None else timeout
        if request_timeout is not None:
            request_args['timeout'] = request_timeout

        try:
            resp = self.session.request(method, url, **request_args)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as http_err:
            raise WAPIError(resp) from http_err

    def _build_return_fields(self, return_fields: list = None):
        """
        Constructs return field parameters for requests.

        Args:
            return_fields (list): The fields requested to be returned.

        Returns:
            dict: The query parameters for return fields.
        """
        query_params = {}
        if return_fields:
            if 'default' in return_fields:
                return_fields.remove('default')
                query_params['_return_fields+'] = ','.join(return_fields)
            else:
                query_params['_return_fields'] = ','.join(return_fields)

        return query_params

    def call_func(
        self,
        ref: str,
        func_name: str,
        func_args: dict = None,
        timeout=None,
    ):
        """
        Invoke a WAPI function.

        Args:
            ref (str): The reference ID of the object the function is associated with.
                       For fileop functions, this is literally 'fileop'.
            func_name (str): The name of the function to call.
            func_args (dict): Input field key/value pairs necessary to run this function.
            return_fields (list): Fields to return on the updated object. 'default' includes base
                                  fields.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The function response data.

        Raises:
            WAPIError: If a request error occurs.
        """
        url = f'{self.base_url}{ref}'

        query_params = {'_function': func_name}

        rdata = self._call_wapi(
            url, query_params, func_args, method='POST', timeout=timeout
        )
        return rdata

    def func_upload(
        self,
        func_name: str,
        file_path: str,
        func_args: dict = None,
        ref: str = 'fileop',
        no_override_host: bool = False,
        timeout=None,
    ):
        """
        Invoke a WAPI file upload function.

        Args:
            func_name (str): The name of the upload function to call.
            file_path (str): The path to the file that will be uploaded.
            func_args (dict): Input field key/value paris necessary to run this function.
            ref (str): The reference ID of the object the function is associated with. Defaults to
                       'fileop'.
            no_override_host (bool): In many WAPI versions, the server provided transfer URL uses
                                     the IP address instead of the DNS name the function call was
                                     made against. By default this function will override that IP
                                     address with the original DNS name if necessary to avoid
                                     potential TLS errors. When True, this parameter disables that
                                     override and the transfer URL will be used as-is.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.

        Returns:
            dict: The function response data.

        Raises:
            WAPIError: If a request error occurs.
        """
        # initialize the upload
        resp = self.call_func('fileop', 'uploadinit', timeout=timeout)
        token, upload_url = resp['token'], resp['url']

        # override the transfer host if necessary
        u = urllib3.util.parse_url(upload_url)
        if u.host != self._wapi_host and not no_override_host:
            logger.debug('Replacing %s with %s in upload URL.', u.host, self._wapi_host)
            upload_url = upload_url.replace(f'/{u.host}', f'/{self._wapi_host}')

        # upload the file
        with open(file_path, 'rb') as f:
            try:
                resp = self.session.post(upload_url, files={'file': f}, timeout=timeout)
                resp.raise_for_status()
            except requests.exceptions.HTTPError as http_err:
                raise WAPIError(resp) from http_err

        # call the requested function with the upload token
        if func_args is None:
            func_args = {'token': token}
        else:
            func_args['token'] = token
        resp = self.call_func(ref, func_name, func_args=func_args, timeout=timeout)
        return resp

    def func_download(
        self,
        func_name: str,
        download_path: str,
        func_args: dict = None,
        ref: str = 'fileop',
        no_override_host: bool = False,
        timeout=None,
    ):
        """
        Invoke a WAPI file download function.

        Args:
            func_name (str): The name of the download function to call.
            download_path (str): The path where the downloaded file will be saved.
            func_args (dict): Input field key/value paris necessary to run this function.
            ref (str): The reference ID of the object the function is associated with. Defaults to
                       'fileop'.
            no_override_host (bool): In many WAPI versions, the server provided transfer URL uses
                                     the IP address instead of the DNS name the function call was
                                     made against. By default this function will override that IP
                                     address with the original DNS name if necessary to avoid
                                     potential TLS errors. When True, this parameter disables that
                                     override and the transfer URL will be used as-is.
            timeout (float or tuple): (optional) How many seconds to wait for the server to
                send data before giving up, as a float, or a (connect timeout, read timeout)
                tuple. Overrides the Client default timeout for this call.
        """
        # call the function to get the download token and URL
        resp = self.call_func(ref, func_name, func_args=func_args, timeout=timeout)
        token, download_url = resp['token'], resp['url']

        # override the transfer host if necessary
        u = urllib3.util.parse_url(download_url)
        if u.host != self._wapi_host and not no_override_host:
            logger.debug(
                'Replacing %s with %s in download URL.', u.host, self._wapi_host
            )
            download_url = download_url.replace(f'/{u.host}', f'/{self._wapi_host}')

        # download the file
        try:
            resp = self.session.get(
                download_url,
                headers={'Content-Type': 'application/force-download'},
                timeout=timeout,
            )
            resp.raise_for_status()
            with open(download_path, 'wb') as f:
                f.write(resp.content)

        except requests.exceptions.HTTPError as http_err:
            raise WAPIError(resp) from http_err

        finally:
            # notify the server that the download is complete
            self.call_func(
                ref, 'downloadcomplete', func_args={'token': token}, timeout=timeout
            )
