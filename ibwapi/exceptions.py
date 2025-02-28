"""Contains custom exceptions for ibwapi."""


class WAPIError(Exception):
    """Custom exception to handle WAPI errors."""

    def __init__(self, response):
        try:
            err = response.json()
            error_message = err.get('Error', 'Unknown error')
            error_code = err.get('code', None)
            error_text = err.get('text', None)
        except ValueError:
            if response.status_code == 401:
                # the most common non-JSON error is permissions or credential related
                error_message = 'Invalid credentials or insufficient permissions for the given credentials.'
            else:
                # use a generic error message
                error_message = f'Unknown error (non-JSON response): {response.text}'
            error_code = response.status_code
            error_text = response.text

        self.status_code = response.status_code
        self.error_message = error_message
        self.error_code = error_code
        self.error_text = error_text

        super().__init__(f'{self.status_code}: {self.error_message}')


class LimitExceededError(Exception):
    """Raised when the result set exceeds the specified max_results limit."""

    def __init__(self, max_results, actual_results):
        super().__init__(
            f'Result set of {actual_results} exceeds the max_results limit of {max_results}.'
        )
